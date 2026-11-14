"""Conversation manager and the thread flow over the real WebSocket (K1-00; FR-C-1, FR-C-2, FR-C-10, FR-S-2, FR-MEM-5)."""
from __future__ import annotations

import asyncio
import inspect

import pytest
from fastapi.testclient import TestClient

import app
import conversation
import waifus
from conversation import ConversationManager, Speaker, history_from
from threads import ThreadStore
from waifu_fixtures import make_pack
from waifus import WaifuRegistry


@pytest.fixture
def manager(tmp_path):
    return ConversationManager(ThreadStore(tmp_path / "threads.db"), history_messages=4)


@pytest.mark.asyncio
async def test_a_fresh_install_gets_one_new_thread_and_returns_to_it(manager):
    first = await manager.open_initial(waifu_id="luna")
    again = await manager.open_initial(waifu_id="luna")
    assert first.id == again.id and first.active_waifu_id == "luna"


@pytest.mark.asyncio
async def test_the_last_opened_thread_wins_over_the_most_recent(manager):
    old = await manager.new_thread(waifu_id=None)
    await manager.new_thread(waifu_id=None)
    await manager.open(old.id)
    assert (await manager.open_initial(waifu_id=None)).id == old.id


@pytest.mark.asyncio
async def test_exchanges_are_recorded_with_speaker_model_effort_and_stop(manager):
    t = await manager.new_thread(waifu_id="yuri")
    await manager.record_exchange(
        t.id, "hi", "hey there", speaker=Speaker("yuri", "Yuri"), model_ref="local:ollama/qwen3.5:9b", effort="low"
    )
    await manager.record_exchange(t.id, "long story?", "Once upon", speaker=Speaker("yuri", "Yuri"), stopped=True)
    await manager.record_exchange(t.id, "anyone there?", "", speaker=Speaker("yuri", "Yuri"))
    msgs = await manager.messages(t.id)
    assert [(m.role, m.content) for m in msgs] == [
        ("user", "hi"), ("assistant", "hey there"),
        ("user", "long story?"), ("assistant", "Once upon"),
        ("user", "anyone there?"),
    ]
    assert msgs[1].speaker_name == "Yuri" and msgs[1].model_ref == "local:ollama/qwen3.5:9b" and msgs[1].effort == "low"
    assert msgs[3].meta == {"stopped": True}
    assert msgs[0].speaker_waifu_id is None          # the user is not a companion


@pytest.mark.asyncio
async def test_a_companion_change_writes_a_divider_and_moves_the_thread(manager):
    t = await manager.new_thread(waifu_id="luna")
    divider = await manager.record_companion_change(t.id, Speaker("yuri", "Yuri"))
    assert divider.role == "divider" and divider.content == "Yuri joined the conversation"
    assert (await manager.get(t.id)).active_waifu_id == "yuri"


def test_history_skips_dividers_keeps_the_window_and_starts_with_the_user():
    store_msgs = [
        ("user", "u1"), ("assistant", "a1"), ("divider", "Yuri joined"),
        ("user", "u2"), ("assistant", "a2"), ("user", "u3"), ("assistant", "a3"),
    ]

    class M:
        def __init__(self, role, content):
            self.role, self.content = role, content

    msgs = [M(r, c) for r, c in store_msgs]
    hist = history_from(msgs, "SYSTEM", max_messages=3)
    # window of 3 = a2, u3, a3; the leading assistant line is dropped
    assert hist == [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
    ]
    assert history_from(msgs, "S", max_messages=0) == [{"role": "system", "content": "S"}]


def test_the_conversation_manager_never_decides_on_a_waifu():
    """FR-W-3: waifu fields are only recorded. No branch reads them."""
    source = inspect.getsource(conversation)
    for needle in ("if speaker.", "if waifu_id ==", "waifu_id in (", ".waifu_id ==", "speaker.name =="):
        assert needle not in source


# -- over the real WebSocket ---------------------------------------------------


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    """The real endpoint with fake model and voice, two companions, data in tmp."""
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha", ref_text="alpha transcript")
    make_pack(premade, "beta", name="Beta", ref_text="beta transcript")
    monkeypatch.setattr(waifus.registry, "_registry", WaifuRegistry(premade, tmp_path / "user"))
    monkeypatch.setattr(app, "_conversation_manager", None)

    async def fake_stream(role, messages, tools, **kwargs):
        last_user = [m["content"] for m in messages if m["role"] == "user"][-1]
        yield {"type": "content", "text": f"You said: {last_user}. [happy]"}

    async def fake_synth(text, voice=None):
        return b""

    async def nothing(*_a, **_k):
        return None

    class NoWriter:
        async def run_pass(self, *_a, **_k):
            return None

        def preempt(self):
            return None

    monkeypatch.setattr(app.router, "stream_with_tools", fake_stream)
    monkeypatch.setattr(app.tts, "synthesize", fake_synth)
    monkeypatch.setattr(app.tts, "prewarm", nothing)
    monkeypatch.setattr(app.look_intent, "maybe_look", nothing)
    monkeypatch.setattr(app, "_log_transcript_turn_safely", nothing)
    monkeypatch.setattr(app.writer, "WRITER", NoWriter())
    monkeypatch.setattr(app, "_driver", None)
    monkeypatch.setattr(app, "_shutdown_event", asyncio.Event())   # binds to this test's loop
    return TestClient(app.app)


def _until(ws, kind):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == kind:
            return msg, seen


def _chat(ws, text):
    ws.send_json({"type": "user_text", "text": text})
    _until(ws, "turn_end")


def test_connect_opens_a_thread_and_a_reply_is_saved_to_it(kernel):
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        thread_id = opened["thread"]["id"]
        assert opened["messages"] == []
        ws.send_json({"type": "set_temp_mode", "enabled": True})   # keeps memory out of the test
        _chat(ws, "hello there")
    with kernel.websocket_connect("/ws") as ws:                   # a reload comes back to it
        opened, _ = _until(ws, "thread_opened")
    assert opened["thread"]["id"] == thread_id
    assert opened["thread"]["title"] == "hello there" and opened["thread"]["temp"] is True
    roles = [(m["role"], m["content"], m["speaker_name"]) for m in opened["messages"]]
    assert roles == [("user", "hello there", None), ("assistant", "You said: hello there.", "Alpha")]


def test_new_thread_starts_empty_and_the_old_one_keeps_its_history(kernel):
    with kernel.websocket_connect("/ws") as ws:
        first, _ = _until(ws, "thread_opened")
        ws.send_json({"type": "set_temp_mode", "enabled": True})
        _chat(ws, "first thread message")
        ws.send_json({"type": "thread_new"})
        second, _ = _until(ws, "thread_opened")
        assert second["thread"]["id"] != first["thread"]["id"] and second["messages"] == []
        listing, _ = _until(ws, "thread_list")
        assert [t["id"] for t in listing["threads"]][1] == first["thread"]["id"]
        ws.send_json({"type": "thread_open", "id": first["thread"]["id"]})
        back, _ = _until(ws, "thread_opened")
        assert [m["content"] for m in back["messages"]][0] == "first thread message"


def test_the_model_sees_only_the_open_threads_history(kernel, monkeypatch):
    seen = []

    async def recording_stream(role, messages, tools, **kwargs):
        seen.append([m["content"] for m in messages if m["role"] in ("user", "assistant")])
        yield {"type": "content", "text": "ok [neutral]"}

    monkeypatch.setattr(app.router, "stream_with_tools", recording_stream)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"type": "set_temp_mode", "enabled": True})
        _chat(ws, "about cats")
        ws.send_json({"type": "thread_new"})
        _until(ws, "thread_opened")
        ws.send_json({"type": "set_temp_mode", "enabled": True})
        _chat(ws, "about dogs")
    assert seen[-1] == ["about dogs"]


def test_switching_companion_adds_a_divider_and_reopening_restores_her(kernel):
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        tid = opened["thread"]["id"]
        ws.send_json({"type": "switch_waifu", "id": "beta"})
        divider, _ = _until(ws, "thread_message")
        assert divider["message"]["role"] == "divider" and divider["message"]["content"] == "Beta joined the conversation"
        ws.send_json({"type": "thread_new"})
        _until(ws, "thread_opened")
        ws.send_json({"type": "switch_waifu", "id": "alpha"})
        _until(ws, "thread_message")
        ws.send_json({"type": "thread_open", "id": tid})
        state, _ = _until(ws, "waifu_state")
        assert state["active"] == "beta"


def test_rename_search_and_delete(kernel):
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        tid = opened["thread"]["id"]
        ws.send_json({"type": "thread_rename", "id": tid, "title": "Garden plans"})
        listing, _ = _until(ws, "thread_list")
        while listing["threads"][0]["title"] != "Garden plans":
            listing, _ = _until(ws, "thread_list")
        ws.send_json({"type": "thread_search", "query": "garden"})
        found, _ = _until(ws, "thread_list")
        while found["query"] != "garden":
            found, _ = _until(ws, "thread_list")
        assert [t["id"] for t in found["threads"]] == [tid]
        ws.send_json({"type": "thread_delete", "id": tid})
        replacement, _ = _until(ws, "thread_opened")
        assert replacement["thread"]["id"] != tid
        ws.send_json({"type": "thread_open", "id": tid})
        err, _ = _until(ws, "error")
        assert err["code"] == "unknown_thread"
