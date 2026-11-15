"""The speak path: panel wording preserved, voice text normalized."""

import pytest

import turns
from audio import speech, tts, voice_mode


class FakeWebSocket:
    def __init__(self):
        self.payloads = []

    async def send_json(self, payload):
        self.payloads.append(payload)


@pytest.mark.asyncio
async def test_send_speak_normalizes_only_the_voice(monkeypatch):
    voice_mode.VOICE.on = True   # these exercise the spoken path (voice mode on, D-061)
    heard = {}

    async def fake_synth(text):
        heard["text"] = text
        return b"RIFF"

    monkeypatch.setattr(tts, "synthesize", fake_synth)
    ws = FakeWebSocket()
    raw = "Wait\u2014what? \u201cReally\u201d \U0001F600"

    await turns.send_speak(ws, raw)

    assert speech.banned_chars_in(heard["text"]) == set()
    assert ws.payloads[0]["data"]["text"] == raw          # caption keeps the original
    assert ws.payloads[0]["data"]["mime"] == "audio/wav"
    assert ws.payloads[0]["data"]["audio_b64"]


@pytest.mark.asyncio
async def test_send_speak_skips_empty_text(monkeypatch):
    called = {"n": 0}

    async def fake_synth(text):
        called["n"] += 1
        return b""

    monkeypatch.setattr(tts, "synthesize", fake_synth)
    ws = FakeWebSocket()

    await turns.send_speak(ws, "   ")

    assert called["n"] == 0
    assert ws.payloads == []


@pytest.mark.asyncio
async def test_send_audio_payload_shape():
    ws = FakeWebSocket()
    await turns.send_audio(ws, "hello", b"abc")
    payload = ws.payloads[0]
    assert payload["type"] == "speak"
    assert payload["data"]["text"] == "hello"
    assert payload["data"]["audio_b64"] == "YWJj"
