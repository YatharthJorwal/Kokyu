"""Dictation (D-097): the mic button (F9) records, the engine writes it down on this
PC (faster-whisper on the CPU) and the words go back to that window's input box.
Nothing is sent to a model, nothing is saved; a failure says so in the box's line."""
from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app
import conversation
import hub
import protocol
from audio import stt
from session import Session


class Socket:
    def __init__(self):
        self.sent = []

    async def send_json(self, frame):
        self.sent.append(frame)

    def dictations(self):
        return [f["data"] for f in self.sent if f["type"] == "dictation"]


def _session():
    session = Session.__new__(Session)
    session.ws = Socket()
    session.dictating = None
    return session


def _msg(audio: bytes | str):
    b64 = audio if isinstance(audio, str) else base64.b64encode(audio).decode()
    return SimpleNamespace(data=SimpleNamespace(audio_b64=b64, mime="audio/webm"))


@pytest.fixture
def heard(monkeypatch):
    got = []

    async def transcribe(audio):
        got.append(audio)
        return "remind me to water the plants"

    monkeypatch.setattr(stt, "transcribe", transcribe)
    return got


@pytest.mark.asyncio
async def test_a_recording_comes_back_as_words_for_the_input_box(heard):
    session = _session()
    await session.on_dictate(_msg(b"OggS-webm-bytes"))
    await session.dictating
    assert heard == [b"OggS-webm-bytes"]
    assert session.ws.dictations() == [{"text": "remind me to water the plants", "error": None}]
    assert [f["type"] for f in session.ws.sent] == ["dictation"]   # no turn, nothing sent to a model


@pytest.mark.asyncio
async def test_silence_is_empty_words_not_an_error(monkeypatch):
    async def transcribe(audio):
        return ""

    monkeypatch.setattr(stt, "transcribe", transcribe)
    session = _session()
    await session.on_dictate(_msg(b"quiet"))
    await session.dictating
    assert session.ws.dictations() == [{"text": "", "error": None}]


@pytest.mark.asyncio
async def test_a_speech_to_text_failure_says_so(monkeypatch):
    async def transcribe(audio):
        raise stt.STTError("model failed to load")

    monkeypatch.setattr(stt, "transcribe", transcribe)
    session = _session()
    await session.on_dictate(_msg(b"audio"))
    await session.dictating
    [out] = session.ws.dictations()
    assert out["text"] == "" and "Doctor" in out["error"]


@pytest.mark.asyncio
async def test_unreadable_audio_is_refused_without_loading_anything(heard):
    session = _session()
    await session.on_dictate(_msg("not base64 at all!!"))
    assert session.dictating is None and heard == []
    assert session.ws.dictations() == [{"text": "", "error": "That recording could not be read."}]


@pytest.mark.asyncio
async def test_one_recording_at_a_time(monkeypatch):
    gate = asyncio.Event()

    async def slow(audio):
        await gate.wait()
        return "first"

    monkeypatch.setattr(stt, "transcribe", slow)
    session = _session()
    await session.on_dictate(_msg(b"one"))
    await session.on_dictate(_msg(b"two"))
    assert session.ws.dictations() == [{"text": "", "error": "Still writing down the last recording."}]
    gate.set()
    await session.dictating
    assert session.ws.dictations()[-1] == {"text": "first", "error": None}


@pytest.mark.asyncio
async def test_recording_starts_loading_the_speech_model_in_the_background(monkeypatch):
    loaded = []

    async def preload():
        loaded.append(1)

    monkeypatch.setattr(stt, "preload", preload)
    await _session().on_dictate_start(SimpleNamespace(data=None))
    await asyncio.sleep(0)
    assert loaded == [1]


def test_the_protocol_caps_a_recording():
    ok = protocol.parse_client({"v": 1, "type": "dictate", "data": {"audio_b64": "QUJD"}})
    assert ok.data.audio_b64 == "QUJD" and ok.data.mime == "audio/webm"
    for data in ({"audio_b64": ""}, {"audio_b64": "A" * (protocol.DICTATION_B64_MAX + 1)}, {}):
        with pytest.raises(protocol.ProtocolError):
            protocol.parse_client({"v": 1, "type": "dictate", "data": data})


def _until(ws, type_):
    while True:
        msg = ws.receive_json()
        if msg.get("type") == type_:
            return msg


def test_a_window_dictates_over_the_socket(heard, monkeypatch):
    monkeypatch.setattr(hub, "shutdown_event", asyncio.Event())
    monkeypatch.setattr(hub, "driver", None)
    monkeypatch.setattr(conversation, "_manager", None)
    with TestClient(app.app) as client, client.websocket_connect("/ws") as ws:
        _until(ws, "read_aloud_status")
        audio = base64.b64encode(b"webm").decode()
        ws.send_json({"v": 1, "type": "dictate", "data": {"audio_b64": audio, "mime": "audio/webm;codecs=opus"}})
        assert _until(ws, "dictation")["data"] == {"text": "remind me to water the plants", "error": None}
    assert heard == [b"webm"]
