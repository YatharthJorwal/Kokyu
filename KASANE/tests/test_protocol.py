"""Typed protocol v1 and token streaming (K1-00b; ARCHITECTURE §5.3, FR-C-2)."""
from __future__ import annotations

import asyncio
import re

import pytest
from fastapi.testclient import TestClient

import app
import paths
import protocol
import waifus
from waifu_fixtures import make_pack
from waifus import WaifuRegistry


def test_a_frame_has_the_envelope():
    f = protocol.frame("token", {"text": "hi"}, thread="t1")
    assert set(f) == {"v", "type", "id", "thread", "data"}
    assert f["v"] == 1 and f["type"] == "token" and f["thread"] == "t1" and f["data"] == {"text": "hi"}
    with pytest.raises(ValueError):
        protocol.frame("not_a_type")
    with pytest.raises(ValueError):
        protocol.error_frame("made_up_code", "x")


def test_legacy_flat_messages_pass_through_untouched():
    assert protocol.parse_client({"type": "user_text", "text": "hi"}) is None
    assert protocol.parse_client("not even a dict") is None


def test_a_valid_frame_is_parsed_and_trimmed():
    msg = protocol.parse_client({"v": 1, "type": "thread_rename", "id": "r1", "data": {"id": "abc", "title": "  Trip  "}})
    assert msg.type == "thread_rename" and msg.id == "r1"
    assert msg.data.model_dump() == {"id": "abc", "title": "Trip"}
    assert protocol.parse_client({"v": 1, "type": "thread_new"}).data.model_dump() == {}


@pytest.mark.parametrize(
    "raw, code",
    [
        ({"v": 2, "type": "thread_new", "data": {}}, "protocol_version"),
        ({"v": 1, "type": "launch_rockets", "data": {}}, "bad_message"),
        ({"v": 1, "type": "thread_open", "data": {}}, "bad_message"),                 # id missing
        ({"v": 1, "type": "thread_open", "data": {"id": "x", "extra": 1}}, "bad_message"),
        ({"v": 1, "type": "thread_open", "data": "x"}, "bad_message"),
        ({"v": 1, "type": "thread_search", "data": {"query": "q" * 500}}, "bad_message"),
    ],
)
def test_bad_frames_are_typed_errors(raw, code):
    with pytest.raises(protocol.ProtocolError) as info:
        protocol.parse_client(raw)
    assert info.value.code == code


@pytest.mark.parametrize(
    "text, shown",
    [
        ("Hello there. [happy]", "Hello there."),
        ("Hello there. [hap", "Hello there."),
        ("Hello there. [", "Hello there."),
        ("See [the docs](http://x) now", "See [the docs](http://x) now"),
        ("A list [one two] here", "A list [one two] here"),
        ("No tag at all", "No tag at all"),
    ],
)
def test_the_trailing_emotion_tag_is_hidden_while_streaming(text, shown):
    assert protocol.strip_trailing_tag(text) == shown


def test_the_typescript_mirror_lists_the_same_types_and_codes():
    ts = (paths.repo_root() / "src" / "net" / "protocol.ts").read_text(encoding="utf-8")

    def ts_list(name):
        block = re.search(rf"export const {name} = \[(.*?)\] as const", ts, re.S)
        assert block, name
        return re.findall(r'"([a-z_]+)"', block.group(1))

    assert ts_list("CLIENT_TYPES") == list(protocol.CLIENT_TYPES)
    assert ts_list("SERVER_TYPES") == list(protocol.SERVER_TYPES)
    assert ts_list("ERROR_CODES") == list(protocol.ERROR_CODES)
    assert f"PROTOCOL_VERSION = {protocol.PROTOCOL_VERSION}" in ts


# -- over the real WebSocket ---------------------------------------------------


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha", ref_text="alpha transcript")
    monkeypatch.setattr(waifus.registry, "_registry", WaifuRegistry(premade, tmp_path / "user"))
    monkeypatch.setattr(app, "_conversation_manager", None)

    async def fake_stream(role, messages, tools, **kwargs):
        for piece in ("Hel", "lo ", "there. ", "[hap", "py]"):
            yield {"type": "content", "text": piece}

    async def nothing(*_a, **_k):
        return None

    async def silent(text, voice=None):
        return b""

    class NoWriter:
        async def run_pass(self, *_a, **_k):
            return None

        def preempt(self):
            return None

    monkeypatch.setattr(app.router, "stream_with_tools", fake_stream)
    monkeypatch.setattr(app.tts, "synthesize", silent)
    monkeypatch.setattr(app.tts, "prewarm", nothing)
    monkeypatch.setattr(app.look_intent, "maybe_look", nothing)
    monkeypatch.setattr(app, "_log_transcript_turn_safely", nothing)
    monkeypatch.setattr(app.writer, "WRITER", NoWriter())
    monkeypatch.setattr(app, "_driver", None)
    monkeypatch.setattr(app, "_shutdown_event", asyncio.Event())
    return TestClient(app.app)


def _until(ws, kind):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == kind:
            return msg, seen


def test_hello_and_errors_come_back_as_frames(kernel):
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "hello", "id": "h1", "data": {"client": "main", "protocol": 1}})
        hello, _ = _until(ws, "hello")
        assert hello["v"] == 1 and hello["id"] == "h1" and hello["data"]["protocol"] == 1
        ws.send_json({"v": 9, "type": "hello", "id": "h2", "data": {}})
        err, _ = _until(ws, "error")
        assert err["data"]["code"] == "protocol_version" and err["data"]["reply_to"] == "h2"


def test_a_reply_streams_token_by_token_then_finishes(kernel):
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        tid = opened["thread"]
        ws.send_json({"type": "set_temp_mode", "enabled": True})
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})          # versioned and legacy mix freely
        _until(ws, "thread_list")
        ws.send_json({"type": "user_text", "text": "hi"})
        _, seen = _until(ws, "turn_end")
    kinds = [m["type"] for m in seen]
    start = kinds.index("turn_start")
    tokens = [m for m in seen if m["type"] == "token"]
    done = next(m for m in seen if m["type"] == "turn_done")
    assert start < kinds.index("token") < kinds.index("turn_done") < kinds.index("turn_end")
    assert all(m["v"] == 1 and m["thread"] == tid for m in (seen[start], *tokens, done))
    assert "".join(t["data"]["text"] for t in tokens) == "Hello there. [happy]"
    assert protocol.strip_trailing_tag("".join(t["data"]["text"] for t in tokens)) == "Hello there."
    assert done["data"] == {"text": "Hello there.", "stopped": False}
