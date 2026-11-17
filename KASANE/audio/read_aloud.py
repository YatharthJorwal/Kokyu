"""Read aloud (D-097): she speaks each reply once it has finished, in Chat and
Roleplay. Replaces D-061's voice mode, whose mic half is now dictation (F9).

One kernel-wide switch, kept between restarts in settings.json (`tts.read_aloud`,
D-070), every window shown the same state. The voice server (GPT-SoVITS, about
47 s to answer after a cold start) starts only while Read aloud is on: when it is
turned on, or once a window is up if it was left on. Every window sees it wake up
the way a chat model does (the loader's `idle | loading | ready | failed` states).
Turned off, replies stop being spoken at once; the voice server we started stops
after `tts.idle_stop_s` seconds, so a quick off/on does not reload it.

Speech-to-text is not part of this: dictation loads it on first use (stt.py).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import config
import model_loader
import settings_file
from audio import tts

log = logging.getLogger(__name__)

VOICE_REF = "voice"
Listener = Callable[[dict[str, Any]], Awaitable[None]]


class VoiceStartError(RuntimeError):
    pass


async def _start(_ref: str) -> None:
    if not await tts.ensure_server():
        raise VoiceStartError(
            "The voice server did not start. Check tts.gpt_sovits.launch in config.yaml and logs/gpt_sovits.log."
        )


class ReadAloud:
    def __init__(self) -> None:
        # Looked up at call time, so tests can replace `_start`.
        self.loader = model_loader.ModelLoader(warm=lambda ref: _start(ref), label=lambda _ref: "Voice")
        self.loader.subscribe(self._loader_changed)
        self._listeners: list[Listener] = []
        self._stop_task: asyncio.Task[None] | None = None

    @property
    def on(self) -> bool:
        """Read at call time: settings.json may have changed it (D-070)."""
        return config.CONFIG.tts.read_aloud

    def status(self) -> dict[str, Any]:
        loader = self.loader.status()
        return {
            "on": self.on,
            "state": loader["state"],
            "message": loader["message"],
            "elapsed_s": loader["elapsed_s"],
        }

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    async def _publish(self) -> None:
        status = self.status()
        await asyncio.gather(*(fn(status) for fn in list(self._listeners)), return_exceptions=True)

    async def _loader_changed(self, _status: dict[str, Any]) -> None:
        await self._publish()

    async def set(self, on: bool) -> None:
        """The composer's Read aloud item. Saved first: if settings.json cannot be
        written, nothing changes (the error reaches the caller)."""
        async with settings_file.LOCK:
            saved = await asyncio.to_thread(settings_file.read)
            await settings_file.save(settings_file.change(saved, {"read_aloud": on}))
        log.info(f"read aloud: {'on' if on else 'off'}")
        if on:
            self.start()
        else:
            self._schedule_stop()
        await self._publish()

    def start(self) -> None:
        """Wake the voice if Read aloud is on. Nothing to do when it is up or waking;
        after a failure this tries again."""
        if not self.on:
            return
        self._cancel_stop()
        self.loader.request(VOICE_REF)

    async def ready(self) -> bool:
        """Waits while the voice wakes up. True once it answers; False when Read
        aloud is off or the start failed (the reply then stays text-only, FR-V-7).
        A failed start is not retried here, once per reply: Try again does that."""
        if not self.on or self.loader.state == model_loader.FAILED:
            return False
        if self.loader.state != model_loader.READY:
            pending = self.loader.request(VOICE_REF)
            if pending is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait({pending})
        return self.on and self.loader.state == model_loader.READY

    def _cancel_stop(self) -> None:
        if self._stop_task is not None and not self._stop_task.done():
            self._stop_task.cancel()
        self._stop_task = None

    def _schedule_stop(self) -> None:
        self._cancel_stop()
        if self.loader.state == model_loader.IDLE:
            return
        self._stop_task = asyncio.create_task(
            self._stop_after(config.CONFIG.tts.idle_stop_s), name="voice-idle-stop"
        )

    async def _stop_after(self, delay_s: float) -> None:
        await asyncio.sleep(max(0.0, delay_s))
        if self.on:
            return
        await self.loader.stop()
        tts.stop_server()
        self.loader.reset()
        log.info("read aloud: idle, voice server stopped")
        await self._publish()

    async def shutdown(self) -> None:
        self._cancel_stop()
        with contextlib.suppress(Exception):
            await self.loader.stop()


# One switch for the kernel.
READ_ALOUD = ReadAloud()
