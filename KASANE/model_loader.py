"""Loads the chat model in the background and tells every window how it is going
(K1-10; FR-M-6; D-054).

The 35B on llama.cpp takes about two minutes to load, so a load must never sit
silently in front of the first message. The kernel asks this loader for a model
at boot (the model the last thread used), when the user picks a model, and when
a thread with another model is opened. The loader runs one load at a time; a
newer request cancels the older one (the user changed their mind). Each change
of state is pushed to every connected window as a `model_status` frame, which the
chat view turns into the "waking up" card and the chip's loading state.

What "loading" means per backend lives in the `warm` function the kernel
configures (`boot.load_chat_model`): llama.cpp starts `llama-server` and reads
the persona once, Ollama loads the weights, an API model needs nothing.

States: `idle` (nothing asked yet), `loading`, `ready`, `failed` (with a
message; the window offers *Try again* and *Switch model*). A turn does not wait
for the loader; it simply goes to the same backend, which finishes the load
first.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger(__name__)

IDLE, LOADING, READY, FAILED = "idle", "loading", "ready", "failed"
STATES = (IDLE, LOADING, READY, FAILED)

Warm = Callable[[str], Awaitable[None]]
Listener = Callable[[dict[str, Any]], Awaitable[None]]


def failure_text(exc: BaseException) -> str:
    """One line a person can read: the error's first line, else its type."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return text[:240]


class ModelLoader:
    def __init__(
        self,
        warm: Warm | None = None,
        *,
        label: Callable[[str], str] | None = None,
        instant: Callable[[str], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._warm = warm
        self._label = label or (lambda ref: ref)
        self._instant = instant or (lambda ref: False)
        self._clock = clock
        # Tests switch this off globally (KASANE/conftest.py) so no test loads a
        # real model by opening a WebSocket.
        self.enabled = True
        self._listeners: list[Listener] = []
        self._task: asyncio.Task[None] | None = None
        self._wanted: str | None = None     # newest request, possibly still waiting for its delay
        self._ref: str | None = None        # the model the published state is about
        self._state = IDLE
        self._message: str | None = None
        self._unload: tuple[Any, ...] = ()    # vram.Resident: what a failed card may unload
        self._started: float | None = None
        self._finished: float | None = None

    def configure(
        self,
        *,
        warm: Warm,
        label: Callable[[str], str] | None = None,
        instant: Callable[[str], bool] | None = None,
    ) -> None:
        self._warm = warm
        if label is not None:
            self._label = label
        if instant is not None:
            self._instant = instant

    def reset(self) -> None:
        """Forget everything (tests). Does not touch a running task's loop."""
        self._task = None
        self._wanted = self._ref = self._message = None
        self._unload = ()
        self._state = IDLE
        self._started = self._finished = None

    # -- state -------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def model_ref(self) -> str | None:
        return self._ref

    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> dict[str, Any]:
        """The `model_status` frame's data, with the time spent so far."""
        elapsed = None
        if self._started is not None:
            end = self._clock() if self._state == LOADING else (self._finished or self._clock())
            elapsed = round(max(0.0, end - self._started), 1)
        try:
            label = self._label(self._ref) if self._ref else None
        except Exception:  # noqa: BLE001 -- a label is cosmetic
            label = self._ref
        return {
            "model_ref": self._ref,
            "label": label,
            "state": self._state,
            "message": self._message,
            "elapsed_s": elapsed,
            # K1-09b (D-071): the models the failed card may offer to unload
            "unload": [{"ref": r.ref, "label": r.label} for r in self._unload],
        }

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    async def _publish(self) -> None:
        status = self.status()
        listeners = list(self._listeners)
        if listeners:
            # A closed window must not stop the others from hearing about it.
            await asyncio.gather(*(fn(status) for fn in listeners), return_exceptions=True)

    async def _set(self, ref: str, state: str, message: str | None = None, unload: tuple[Any, ...] = ()) -> None:
        self._ref, self._state, self._message, self._unload = ref, state, message, unload
        if state == LOADING:
            self._started, self._finished = self._clock(), None
        elif self._started is not None and self._finished is None:
            self._finished = self._clock()
        await self._publish()

    # -- requests ----------------------------------------------------------

    def request(self, ref: str, *, delay_s: float = 0.0, force: bool = False) -> asyncio.Task[None] | None:
        """Make `ref` the loaded chat model. Asking for the model that is already
        loaded or loading does nothing (unless `force`, used by *Try again*); a
        different model cancels the load in progress. `delay_s` lets quick clicks
        through old threads settle before anything heavy starts. Returns the
        task doing the work, if any."""
        if not self.enabled or self._warm is None or not ref:
            return None
        if not force:
            if ref == self._wanted and self.busy():
                return self._task
            if ref == self._ref and self._state == READY:
                # Back to the model that is already up: drop a pending switch.
                self._cancel_task()
                self._wanted = ref
                return None
        self._cancel_task()
        self._wanted = ref
        self._task = asyncio.create_task(self._run(ref, delay_s), name=f"model-load:{ref}")
        return self._task

    def _cancel_task(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _run(self, ref: str, delay_s: float) -> None:
        if delay_s > 0:
            await asyncio.sleep(delay_s)
        if self._instant(ref):
            self._started = None
            await self._set(ref, READY)
            try:
                await self._warm(ref)   # nothing to load; it frees what other models hold (D-072)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- the model is usable either way
                log.warning(f"freeing memory for {ref} failed: {type(exc).__name__}: {exc}")
            return
        await self._set(ref, LOADING)
        assert self._warm is not None
        try:
            await self._warm(ref)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 -- shown to the user, with Try again
            # stderr like the rest of the kernel's log lines (logging is not configured).
            log.warning(f"loading {ref} failed: {type(exc).__name__}: {exc}")
            await self._set(ref, FAILED, failure_text(exc), tuple(getattr(exc, "unload", ())))
            return
        log.info(f"model ready: {ref} after {self.status()['elapsed_s']} s")
        await self._set(ref, READY)

    async def mark_ready(self, ref: str) -> None:
        """A turn on `ref` just produced a reply, so a stale *failed* state (for
        example Ollama was started after the boot warm-up gave up) is wrong now."""
        if ref == self._ref and self._state == FAILED and not self.busy():
            await self._set(ref, READY)

    async def stop(self) -> None:
        """Cancel a load in progress and wait for it to unwind (kernel shutdown)."""
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=10)


# One loader for the kernel; boot.py configures its `warm` function at import.
LOADER = ModelLoader()
