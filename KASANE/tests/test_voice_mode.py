"""Voice mode (D-061): GPT-SoVITS and faster-whisper start only when the user turns
voice on; turned off, replies go silent at once and the server stops after idle."""
from __future__ import annotations

import asyncio
import dataclasses

import pytest
from fastapi.testclient import TestClient

import app
import config
from audio import stt, tts, voice_mode


@pytest.fixture
def voice(monkeypatch):
    seen: dict[str, list] = {"start": [], "preload": [], "stop": [], "status": []}
    result = {"up": True}

    async def ensure_server():
        seen["start"].append(1)
        return result["up"]

    async def preload():
        seen["preload"].append(1)

    monkeypatch.setattr(tts, "ensure_server", ensure_server)
    monkeypatch.setattr(tts, "stop_server", lambda: seen["stop"].append(1))
    monkeypatch.setattr(stt, "preload", preload)
    mode = voice_mode.VOICE

    async def listener(status):
        seen["status"].append((status["on"], status["state"]))

    mode.subscribe(listener)
    return mode, seen, result


def idle_after(monkeypatch, seconds):
    cfg = config.CONFIG
    monkeypatch.setattr(voice_mode, "CONFIG", dataclasses.replace(cfg, tts=dataclasses.replace(cfg.tts, idle_stop_s=seconds)))


async def settle(mode):
    if mode.loader.busy():
        await mode.loader._task


@pytest.mark.asyncio
async def test_voice_starts_off_and_starts_both_engines_when_turned_on(voice):
    mode, seen, _ = voice
    assert mode.status() == {"on": False, "state": "idle", "message": None, "elapsed_s": None}
    assert not mode.speaking()
    await mode.set(True)
    await settle(mode)
    assert mode.speaking() and seen["start"] == [1] and seen["preload"] == [1]
    assert seen["status"][0] == (True, "idle") and seen["status"][-1] == (True, "ready")
    assert (True, "loading") in seen["status"]           # the window's "voice is waking up"
    await mode.set(True)                                  # already up: nothing starts again
    await settle(mode)
    assert seen["start"] == [1]


@pytest.mark.asyncio
async def test_a_failed_start_is_shown_and_turning_it_on_again_retries(voice):
    mode, seen, result = voice
    result["up"] = False
    await mode.set(True)
    await settle(mode)
    status = mode.status()
    assert status["state"] == "failed" and "logs/gpt_sovits.log" in status["message"]
    assert seen["preload"] == []                          # no speech model without a voice
    result["up"] = True
    await mode.set(True)
    await settle(mode)
    assert mode.status()["state"] == "ready" and seen["start"] == [1, 1]


@pytest.mark.asyncio
async def test_off_is_silent_at_once_and_stops_the_server_only_after_idle(voice, monkeypatch):
    mode, seen, _ = voice
    idle_after(monkeypatch, 0.05)
    await mode.set(True)
    await settle(mode)
    await mode.set(False)
    assert not mode.speaking() and seen["stop"] == []    # not yet: a quick on/off must not reload
    await mode.set(True)                                  # back on before the idle time: kept
    await asyncio.sleep(0.1)
    assert seen["stop"] == [] and seen["start"] == [1]
    await mode.set(False)
    await asyncio.sleep(0.1)
    assert seen["stop"] == [1]
    assert mode.status() == {"on": False, "state": "idle", "message": None, "elapsed_s": None}
    await mode.set(True)                                  # after the stop, on starts it again
    await settle(mode)
    assert seen["start"] == [1, 1]


@pytest.mark.asyncio
async def test_off_before_anything_started_has_nothing_to_stop(voice, monkeypatch):
    mode, seen, _ = voice
    idle_after(monkeypatch, 0)
    await mode.set(False)
    await asyncio.sleep(0.02)
    assert seen["stop"] == [] and seen["start"] == []


@pytest.mark.asyncio
async def test_replies_are_not_synthesized_while_voice_is_off(voice, monkeypatch):
    mode, _, _ = voice

    async def synth(text, voice_params=None):
        return b"WAV"

    monkeypatch.setattr(tts, "synthesize", synth)
    monkeypatch.setattr(app, "_voice_of", lambda ws: None)
    assert await app._synthesize_for(object(), "hello") == b""
    await mode.set(True)
    await settle(mode)
    assert await app._synthesize_for(object(), "hello") == b"WAV"


def _until(ws, type_):
    while True:
        msg = ws.receive_json()
        if msg.get("type") == type_:
            return msg


def test_a_window_sees_voice_off_and_turns_it_on(voice, monkeypatch, tmp_path):
    mode, seen, _ = voice
    monkeypatch.setattr(app, "_shutdown_event", asyncio.Event())
    monkeypatch.setattr(app, "_driver", None)
    monkeypatch.setattr(app, "_conversation_manager", None)
    with TestClient(app.app) as client, client.websocket_connect("/ws") as ws:
        first = _until(ws, "voice_status")
        assert first["data"] == {"on": False, "state": "idle", "message": None, "elapsed_s": None}
        assert seen["start"] == []                        # opening the window started nothing
        ws.send_json({"v": 1, "type": "voice_mode", "data": {"on": True}})
        while _until(ws, "voice_status")["data"]["state"] != "ready":
            pass
    assert seen["start"] == [1]
