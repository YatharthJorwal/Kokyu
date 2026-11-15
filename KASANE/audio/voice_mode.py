"""Voice mode: the voice server and the speech model start only when the user
turns voice on (D-061).

Plain text chat never loads either one. Turning voice mode on starts GPT-SoVITS
(through `tts.ensure_server`) and loads faster-whisper, and every window sees
it wake up the same way a chat model does (the loader's `idle | loading | ready
| failed` states). Turning it off stops replies from being spoken at once. The
voice server we started is stopped only after `tts.idle_stop_s` seconds, so a
quick off/on does not reload it.

Kernel-wide, like the screen companions (D-056): one voice server for the PC,
one switch, every window shown the same state. It always starts off.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import model_loader
from audio import stt, tts
from config import CONFIG

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
    await stt.preload()


class VoiceMode:
    def __init__(self) -> None:
        self.on = False
        # Looked up at call time, so tests can replace `_start`.
        self.loader = model_loader.ModelLoader(warm=lambda ref: _start(ref), label=lambda _ref: "Voice")
        self.loader.subscribe(self._loader_changed)
        self._listeners: list[Listener] = []
        self._stop_task: asyncio.Task[None] | None = None

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

    def speaking(self) -> bool:
        """Whether replies are spoken now."""
        return self.on

    async def set(self, on: bool) -> None:
        if on:
            self._cancel_stop()
            self.on = True
            # Nothing to do when it is already up or waking; after a failure this tries again.
            self.loader.request(VOICE_REF)
        else:
            self.on = False
            self._schedule_stop()
        await self._publish()

    def _cancel_stop(self) -> None:
        if self._stop_task is not None and not self._stop_task.done():
            self._stop_task.cancel()
        self._stop_task = None

    def _schedule_stop(self) -> None:
        self._cancel_stop()
        if self.loader.state == model_loader.IDLE:
            return
        self._stop_task = asyncio.create_task(self._stop_after(CONFIG.tts.idle_stop_s), name="voice-idle-stop")

    async def _stop_after(self, delay_s: float) -> None:
        await asyncio.sleep(max(0.0, delay_s))
        if self.on:
            return
        await self.loader.stop()
        tts.stop_server()
        self.loader.reset()
        log.info("voice: idle, voice server stopped")
        await self._publish()

    async def shutdown(self) -> None:
        self._cancel_stop()
        with contextlib.suppress(Exception):
            await self.loader.stop()


# One switch for the kernel.
VOICE = VoiceMode()
