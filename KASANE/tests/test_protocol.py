"""Typed protocol v1 and token streaming (K1-00b; ARCHITECTURE §5.3, FR-C-2)."""
from __future__ import annotations

import asyncio
import re

import pytest
from fastapi.testclient import TestClient

import app
import conversation
import hub
import paths
import protocol
import router
import session
import turns
import waifus
from audio import tts
from memory import writer
from senses import look_intent
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


def test_only_v1_frames_are_accepted():
    # The window speaks v1 only (D-062): a flat message or a non-object is a typed error.
    for raw in ({"type": "send", "text": "hi"}, "not even a dict"):
        with pytest.raises(protocol.ProtocolError) as info:
            protocol.parse_client(raw)
        assert info.value.code == "bad_message"
    assert protocol.parse_client({"v": 1, "type": "send", "data": {"text": "hi"}}).data.text == "hi"


def test_a_field_over_its_limit_is_refused_in_plain_words():
    # D-123: never pydantic's "send: text: String should have at most ..." in the window.
    with pytest.raises(protocol.ProtocolError) as info:
        protocol.parse_client({"v": 1, "type": "send", "data": {"text": "x" * 20_001}})
    assert (info.value.code, str(info.value)) == ("bad_message", "That is too long: the limit is 20,000 characters.")


def test_every_client_message_has_a_session_handler():
    # A new message type is a CLIENT_TYPES entry plus one Session.on_<type> (D-062).
    missing = [t for t in protocol.CLIENT_TYPES if not callable(getattr(session.Session, f"on_{t}", None))]
    assert missing == []


def test_a_valid_frame_is_parsed_and_trimmed():
    msg = protocol.parse_client({"v": 1, "type": "thread_rename", "id": "r1", "data": {"id": "abc", "title": "  Trip  "}})
    assert msg.type == "thread_rename" and msg.id == "r1"
    assert msg.data.model_dump() == {"id": "abc", "title": "Trip"}
    # FR-MODE-1: an empty thread_new (the client before modes) is still valid: a chat thread.
    # (It used to dump to {}; the payload gained mode and scenario with defaults, D-074, and waifu_id, D-091.)
    assert protocol.parse_client({"v": 1, "type": "thread_new"}).data.model_dump() == {"mode": "chat", "scenario": None, "waifu_id": None}


def test_thread_new_takes_a_mode_and_a_scenario_card():
    """FR-MODE-1, FR-MODE-6: a roleplay with its card; every field optional and trimmed."""
    msg = protocol.parse_client({
        "v": 1, "type": "thread_new",
        "data": {"mode": "roleplay", "scenario": {"title": "  Rain  ", "opening": "*waves*"}},
    })
    assert msg.data.mode == "roleplay"
    assert msg.data.scenario.model_dump() == {
        "title": "Rain", "setting": "", "user_role": "", "her_role": "", "rules": "", "opening": "*waves*",
    }
    blank = protocol.parse_client({"v": 1, "type": "thread_new", "data": {"mode": "roleplay"}})
    assert blank.data.mode == "roleplay" and blank.data.scenario is None


def test_scenario_card_messages_parse():
    """FR-MODE-6 (K1c-06): list, save (new, or replacing an id) and delete saved cards."""
    assert protocol.parse_client({"v": 1, "type": "scenario_list", "data": {}}).data.model_dump() == {}
    new = protocol.parse_client({"v": 1, "type": "scenario_save", "data": {"card": {"setting": " A pier. "}}})
    assert new.data.id is None and new.data.card.setting == "A pier." and new.data.card.title == ""
    edit = protocol.parse_client({"v": 1, "type": "scenario_save", "data": {"id": "abc", "card": {}}})
    assert edit.data.id == "abc"
    assert protocol.parse_client({"v": 1, "type": "scenario_delete", "data": {"id": "abc"}}).data.id == "abc"
    cards = [{"id": "abc", "title": "A pier.", "card": {"setting": "A pier."}, "updated_at": 1.0}]
    assert protocol.frame("scenarios", {"cards": cards})["data"]["cards"] == cards


@pytest.mark.parametrize(
    "raw, code",
    [
        ({"v": 2, "type": "thread_new", "data": {}}, "protocol_version"),
        ({"v": 1, "type": "launch_rockets", "data": {}}, "bad_message"),
        ({"v": 1, "type": "thread_open", "data": {}}, "bad_message"),                 # id missing
        ({"v": 1, "type": "thread_open", "data": {"id": "x", "extra": 1}}, "bad_message"),
        ({"v": 1, "type": "thread_open", "data": "x"}, "bad_message"),
        ({"v": 1, "type": "thread_search", "data": {"query": "q" * 500}}, "bad_message"),
        # FR-MODE-1, 6: an unknown mode, an oversized card field, an unknown key
        ({"v": 1, "type": "thread_new", "data": {"mode": "live"}}, "bad_message"),
        ({"v": 1, "type": "thread_new", "data": {"mode": "roleplay", "scenario": {"title": "t" * 121}}}, "bad_message"),
        ({"v": 1, "type": "thread_new", "data": {"mode": "roleplay", "scenario": {"setting": "s" * 2001}}}, "bad_message"),
        ({"v": 1, "type": "thread_new", "data": {"mode": "roleplay", "scenario": {"rules": "r" * 2001}}}, "bad_message"),
        ({"v": 1, "type": "thread_new", "data": {"mode": "roleplay", "scenario": {"opening": "o" * 4001}}}, "bad_message"),
        ({"v": 1, "type": "thread_new", "data": {"mode": "roleplay", "scenario": {"genre": "noir"}}}, "bad_message"),
        ({"v": 1, "type": "thread_new", "data": {"mode": "chat", "extra": 1}}, "bad_message"),
        # FR-MODE-6 (K1c-06): saved cards. A save needs a card; ids are bounded and non-empty.
        ({"v": 1, "type": "scenario_save", "data": {}}, "bad_message"),
        ({"v": 1, "type": "scenario_save", "data": {"id": "", "card": {}}}, "bad_message"),
        ({"v": 1, "type": "scenario_save", "data": {"id": "x" * 65, "card": {}}}, "bad_message"),
        ({"v": 1, "type": "scenario_save", "data": {"card": {"genre": "noir"}}}, "bad_message"),
        ({"v": 1, "type": "scenario_save", "data": {"card": {"opening": "o" * 4001}}}, "bad_message"),
        ({"v": 1, "type": "scenario_save", "data": {"card": {}, "mode": "roleplay"}}, "bad_message"),
        ({"v": 1, "type": "scenario_delete", "data": {}}, "bad_message"),
        ({"v": 1, "type": "scenario_delete", "data": {"id": "  "}}, "bad_message"),
        ({"v": 1, "type": "scenario_list", "data": {"all": True}}, "bad_message"),
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
    monkeypatch.setattr(conversation, "_manager", None)

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

    monkeypatch.setattr(router, "stream_with_tools", fake_stream)
    monkeypatch.setattr(tts, "synthesize", silent)
    monkeypatch.setattr(tts, "prewarm", nothing)
    monkeypatch.setattr(look_intent, "maybe_look", nothing)
    monkeypatch.setattr(turns, "log_transcript_turn", nothing)
    monkeypatch.setattr(writer, "WRITER", NoWriter())
    monkeypatch.setattr(hub, "driver", None)
    monkeypatch.setattr(hub, "shutdown_event", asyncio.Event())
    return TestClient(app.app)


def _until(ws, kind):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == kind:
            return msg, seen


def _temp_on(ws):
    """Temp Chat on (keeps memory out of the test); the kernel confirms it."""
    ws.send_json({"v": 1, "type": "set_temp", "data": {"on": True}})
    return _until(ws, "thread_updated")


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
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
        ws.send_json({"v": 1, "type": "send", "data": {"text": "hi"}})
        _, seen = _until(ws, "turn_done")
    kinds = [m["type"] for m in seen]
    start = kinds.index("turn_start")
    tokens = [m for m in seen if m["type"] == "token"]
    done = next(m for m in seen if m["type"] == "turn_done")
    assert start < kinds.index("token") < kinds.index("turn_done")
    assert "turn_end" not in kinds
    assert all(m["v"] == 1 and m["thread"] == tid for m in (seen[start], *tokens, done))
    assert "".join(t["data"]["text"] for t in tokens) == "Hello there. [happy]"
    assert protocol.strip_trailing_tag("".join(t["data"]["text"] for t in tokens)) == "Hello there."
    assert done["data"] == {"text": "Hello there.", "stopped": False, "emotion": "happy"}
