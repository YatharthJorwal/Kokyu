"""Switching waifus: persona text and voice change, nothing else (FR-S-2, FR-S-5, FR-V-1, FR-V-7)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app
import prompting
import waifus
from waifu_fixtures import make_pack
from waifus import WaifuRegistry


class FakeWebSocket:
    def __init__(self):
        self.payloads: list[dict] = []
        self.state = SimpleNamespace(waifu=None)

    async def send_json(self, payload):
        self.payloads.append(payload)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha", ref_text="alpha transcript")
    make_pack(premade, "beta", name="Beta", ref_text="beta transcript")
    reg = WaifuRegistry(premade, tmp_path / "user")
    monkeypatch.setattr(waifus.registry, "_registry", reg)
    return reg


def _history(waifu):
    return [
        {"role": "system", "content": app._system_message(waifu)},
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer [happy]"},
    ]


@pytest.mark.asyncio
async def test_switch_replaces_only_the_system_prompt_and_the_voice(registry, monkeypatch):
    prewarmed = []

    async def fake_prewarm(voice):
        prewarmed.append(voice)
        return True

    monkeypatch.setattr(app.tts, "prewarm", fake_prewarm)
    ws = FakeWebSocket()
    ws.state.waifu = registry.get("alpha")
    history = _history(registry.get("alpha"))
    before_tail = [dict(m) for m in history[1:]]

    result = await app._apply_waifu_switch(ws, history, registry, "beta")

    assert result.id == "beta" and ws.state.waifu.id == "beta"
    assert history[0]["content"] == prompting.build_system_prompt(registry.get("beta").prompt)
    assert history[1:] == before_tail                       # the conversation itself is untouched
    state = ws.payloads[-1]
    assert state["type"] == "waifu_state" and state["active"] == "beta"
    assert {w["id"] for w in state["waifus"]} == {"alpha", "beta"}
    assert app._load_active_id() == "beta"                  # remembered for the next launch
    import asyncio
    await asyncio.sleep(0)                                  # let the pre-warm task run
    assert prewarmed and prewarmed[0].prompt_text == "beta transcript"


@pytest.mark.asyncio
async def test_unknown_waifu_changes_nothing(registry):
    ws = FakeWebSocket()
    ws.state.waifu = registry.get("alpha")
    history = _history(registry.get("alpha"))
    snapshot = [dict(m) for m in history]
    assert await app._apply_waifu_switch(ws, history, registry, "nobody") is None
    assert history == snapshot and ws.state.waifu.id == "alpha" and ws.payloads == []


@pytest.mark.asyncio
async def test_speech_uses_the_active_waifus_clip_and_transcript(registry, monkeypatch):
    heard = []

    async def fake_synth(text, voice=None):
        heard.append((text, voice))
        return b"RIFF"

    monkeypatch.setattr(app.tts, "synthesize", fake_synth)
    ws = FakeWebSocket()
    ws.state.waifu = registry.get("alpha")
    await app._send_speak(ws, "Same sentence.")
    ws.state.waifu = registry.get("beta")
    await app._send_speak(ws, "Same sentence.")

    (t1, v1), (t2, v2) = heard
    assert t1 == t2
    assert v1.prompt_text == "alpha transcript" and v2.prompt_text == "beta transcript"
    assert v1.ref_audio_path != v2.ref_audio_path
    assert (v1.prompt_lang, v1.text_lang) == (v2.prompt_lang, v2.text_lang)


@pytest.mark.asyncio
async def test_no_waifu_means_the_legacy_voice_call(monkeypatch):
    calls = []

    async def fake_synth(text):          # one-argument stub, as the older tests use
        calls.append(text)
        return b"RIFF"

    monkeypatch.setattr(app.tts, "synthesize", fake_synth)
    await app._send_speak(FakeWebSocket(), "Hello.")
    assert calls == ["Hello."]


@pytest.mark.asyncio
async def test_dead_voice_backend_leaves_a_text_only_reply(registry, monkeypatch):
    async def down(text, voice=None):
        raise app.tts.TTSUnreachableError("backend down")

    monkeypatch.setattr(app.tts, "synthesize", down)
    ws = FakeWebSocket()
    ws.state.waifu = registry.get("alpha")
    await app._send_speak(ws, "Still here.")
    payload = ws.payloads[0]
    assert payload["type"] == "speak" and payload["text"] == "Still here." and payload["audio_b64"] == ""


def test_system_message_is_the_legacy_prompt_without_a_waifu():
    assert app._system_message(None) == app.SYSTEM_PROMPT


def test_vrm_endpoint_serves_a_known_waifu_and_only_a_known_waifu(registry):
    client = TestClient(app.app)
    ok = client.get("/waifus/alpha/vrm", headers={"Origin": "http://localhost:1420"})
    assert ok.status_code == 200 and ok.content == b"glTF-not-really"
    assert ok.headers["access-control-allow-origin"] == "http://localhost:1420"
    assert client.get("/waifus/nobody/vrm").status_code == 404
    assert client.get("/waifus/..%2F..%2Fsecret/vrm").status_code == 404


def test_vrm_endpoint_does_not_allow_other_origins(registry):
    resp = TestClient(app.app).get("/waifus/alpha/vrm", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in resp.headers
