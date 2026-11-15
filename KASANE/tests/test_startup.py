"""Boot behaviour (D-060): nothing heavy before a window is up, then one step at a
time; the speech model is loaded once, without racing a first turn."""

from __future__ import annotations

import asyncio
import dataclasses
import threading
import time

import pytest

import boot
import config
from audio import stt, tts


@pytest.fixture
def boot_steps(monkeypatch):
    """Records the boot steps; each waits for its own release."""
    seen: list[str] = []

    def step(name):
        async def run():
            seen.append(name)

        return run

    async def no_voice():
        raise AssertionError("voice must not start at launch (D-061)")

    monkeypatch.setattr(boot, "_first_window", None)
    monkeypatch.setattr(boot, "check_router", step("router"))
    monkeypatch.setattr(boot, "check_chat_model", step("chat"))
    monkeypatch.setattr(boot, "startup_memory_pass", step("memory"))
    monkeypatch.setattr(tts, "ensure_server", no_voice)
    monkeypatch.setattr(stt, "preload", no_voice)
    return seen


@pytest.mark.asyncio
async def test_nothing_heavy_loads_before_a_window_is_up(boot_steps):
    # D-060: the window paints on an idle PC; only the cached catalog is read
    task = asyncio.create_task(boot.boot_sequence())
    await asyncio.sleep(0.05)
    assert boot_steps == ["router"]
    boot.first_window_event().set()
    await task
    # then one heavy thing at a time, the chat model first; voice never (D-061)
    assert boot_steps == ["router", "chat", "memory"]


@pytest.mark.asyncio
async def test_one_failing_boot_step_does_not_stop_the_others(monkeypatch, boot_steps):
    async def boom():
        raise RuntimeError("ollama exploded")

    monkeypatch.setattr(boot, "check_chat_model", boom)
    boot.first_window_event().set()
    await boot.boot_sequence()  # must not raise
    assert boot_steps == ["router", "memory"]


def _with_stt(**overrides):
    return dataclasses.replace(config.CONFIG, stt=dataclasses.replace(config.CONFIG.stt, **overrides))


@pytest.fixture(autouse=True)
def _fresh_model_state(monkeypatch):
    monkeypatch.setattr(stt, "_model", None)


@pytest.mark.asyncio
async def test_preload_loads_the_model_once(monkeypatch):
    loads = []
    monkeypatch.setattr(stt, "WhisperModel", lambda *a, **k: loads.append(1) or object())
    await stt.preload()
    await stt.preload()  # already loaded: no second load
    assert len(loads) == 1


@pytest.mark.asyncio
async def test_a_failed_warm_up_never_raises_and_the_next_use_can_retry(monkeypatch, caplog):
    attempts = []

    def flaky(*a, **k):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("no network for the download")
        return object()

    monkeypatch.setattr(stt, "WhisperModel", flaky)
    await stt.preload()  # swallowed
    assert "preload failed" in caplog.text
    assert stt._get_model() is not None and len(attempts) == 2


def test_concurrent_first_uses_load_the_model_exactly_once(monkeypatch):
    loads = []

    def slow_load(*a, **k):
        loads.append(1)
        time.sleep(0.05)
        return object()

    monkeypatch.setattr(stt, "WhisperModel", slow_load)
    threads = [threading.Thread(target=stt._get_model) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(loads) == 1


def test_the_old_stt_warm_up_key_is_ignored():
    # D-061: the speech model never loads at launch; old configs still parse
    old = config.VoiceConfig(stt={**config.VoiceConfig().stt, "warm_up_on_start": True})
    assert not hasattr(config._derive_stt({}, old), "warm_up_on_start")
