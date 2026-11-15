"""Conversation manager and the thread flow over the real WebSocket (K1-00; FR-C-1, FR-C-2, FR-C-10, FR-S-2, FR-MEM-5)."""
from __future__ import annotations

import asyncio
import inspect
import time

import pytest
from fastapi.testclient import TestClient

import app
import conversation
import hub
import router
import turns
import waifus
from audio import tts
from conversation import ConversationManager, Speaker, history_from
from memory import writer
from senses import look_intent
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
async def test_a_screen_remark_is_shown_but_never_given_to_a_model(manager):
    # FR-SC-2 shows it in the chat; FR-SC-3/FR-R-7 keep a screen-derived line away from models.
    luna = Speaker("luna", "Luna")
    t = await manager.new_thread(waifu_id="luna")
    await manager.record_exchange(t.id, "hi", "hey", speaker=luna)
    remark = await manager.record_remark(t.id, "That code looks tangled.", speaker=luna)
    assert remark.meta == {"ambient": True} and remark.speaker_name == "Luna"
    assert [m.content for m in await manager.messages(t.id)][-1] == "That code looks tangled."
    history = await manager.history(await manager.open(t.id), "sys")
    assert [m["content"] for m in history[1:]] == ["hi", "hey"]
    assert (await manager.last_exchange(t.id))[0] == "hi"                     # Regenerate skips it


@pytest.mark.asyncio
async def test_the_last_exchange_is_found_to_run_again(manager):
    # K1-04 (FR-C-9): Regenerate replaces the line and its reply; Retry after a
    # failure replaces the lone line. Finding it deletes nothing.
    yuri = Speaker("yuri", "Yuri")
    t = await manager.new_thread(waifu_id="yuri")
    assert await manager.last_exchange(t.id) is None                          # nothing yet
    await manager.record_exchange(t.id, "hi", "hey", speaker=yuri)
    await manager.record_exchange(t.id, "joke?", "Why did…", speaker=yuri)
    again, ids, meta = await manager.last_exchange(t.id)
    assert again == "joke?" and len(ids) == 2 and meta == {}
    assert len(await manager.messages(t.id)) == 4                             # nothing deleted yet
    await manager.record_companion_change(t.id, Speaker("luna", "Luna"))
    assert (await manager.last_exchange(t.id))[0] == "joke?"                  # a divider does not end it
    await manager.delete_messages(ids)
    await manager.record_exchange(t.id, "again?", "", speaker=yuri, meta={"log_id": 7})   # a failed turn
    again, ids, meta = await manager.last_exchange(t.id)
    assert again == "again?" and len(ids) == 1 and meta == {"log_id": 7}               # its transcript row goes with it
    history = await manager.history(await manager.open(t.id), "sys", exclude=ids)
    assert [m["content"] for m in history[1:]] == ["hi", "hey"]


@pytest.mark.asyncio
async def test_a_companion_change_writes_a_divider_and_moves_the_thread(manager):
    t = await manager.new_thread(waifu_id="luna")
    divider = await manager.record_companion_change(t.id, Speaker("yuri", "Yuri"))
    assert divider.role == "divider" and divider.content == "Switched to Yuri"
    assert (await manager.get(t.id)).active_waifu_id == "yuri"


def test_history_skips_dividers_keeps_the_window_and_starts_with_the_user():
    store_msgs = [
        ("user", "u1"), ("assistant", "a1"), ("divider", "Yuri joined"),
        ("user", "u2"), ("assistant", "a2"), ("user", "u3"), ("assistant", "a3"),
    ]

    class M:
        def __init__(self, role, content):
            self.role, self.content, self.meta = role, content, {}

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
    monkeypatch.setattr(conversation, "_manager", None)

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

    monkeypatch.setattr(router, "stream_with_tools", fake_stream)
    monkeypatch.setattr(tts, "synthesize", fake_synth)
    monkeypatch.setattr(tts, "prewarm", nothing)
    monkeypatch.setattr(look_intent, "maybe_look", nothing)
    monkeypatch.setattr(turns, "log_transcript_turn", nothing)
    monkeypatch.setattr(writer, "WRITER", NoWriter())
    monkeypatch.setattr(hub, "driver", None)
    monkeypatch.setattr(hub, "shutdown_event", asyncio.Event())   # binds to this test's loop
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
    updated, _ = _until(ws, "thread_updated")
    assert updated["data"]["thread"]["temp"] is True
    return updated, _


def _chat(ws, text):
    ws.send_json({"v": 1, "type": "send", "data": {"text": text}})
    _until(ws, "turn_done")


def test_connect_opens_a_thread_and_a_reply_is_saved_to_it(kernel):
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        thread_id = opened["data"]["thread"]["id"]
        assert opened["data"]["messages"] == []
        _temp_on(ws)   # keeps memory out of the test
        _chat(ws, "hello there")
    with kernel.websocket_connect("/ws") as ws:                   # a reload comes back to it
        opened, _ = _until(ws, "thread_opened")
    assert opened["data"]["thread"]["id"] == thread_id
    assert opened["data"]["thread"]["title"] == "hello there" and opened["data"]["thread"]["temp"] is True
    roles = [(m["role"], m["content"], m["speaker_name"]) for m in opened["data"]["messages"]]
    assert roles == [("user", "hello there", None), ("assistant", "You said: hello there.", "Alpha")]


def test_new_thread_starts_empty_and_the_old_one_keeps_its_history(kernel):
    with kernel.websocket_connect("/ws") as ws:
        first, _ = _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "first thread message")
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        second, _ = _until(ws, "thread_opened")
        assert second["data"]["thread"]["id"] != first["data"]["thread"]["id"] and second["data"]["messages"] == []
        listing, _ = _until(ws, "thread_list")
        assert [t["id"] for t in listing["data"]["threads"]][1] == first["data"]["thread"]["id"]
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": first["data"]["thread"]["id"]}})
        back, _ = _until(ws, "thread_opened")
        assert [m["content"] for m in back["data"]["messages"]][0] == "first thread message"


def test_the_model_sees_only_the_open_threads_history(kernel, monkeypatch):
    seen = []

    async def recording_stream(role, messages, tools, **kwargs):
        seen.append([m["content"] for m in messages if m["role"] in ("user", "assistant")])
        yield {"type": "content", "text": "ok [neutral]"}

    monkeypatch.setattr(router, "stream_with_tools", recording_stream)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "about cats")
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "about dogs")
    assert seen[-1] == ["about dogs"]


def test_switching_companion_adds_a_divider_and_reopening_restores_her(kernel):
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        tid = opened["data"]["thread"]["id"]
        ws.send_json({"v": 1, "type": "switch_waifu", "data": {"id": "beta"}})
        divider, _ = _until(ws, "thread_message")
        assert divider["data"]["message"]["role"] == "divider" and divider["data"]["message"]["content"] == "Switched to Beta"
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "switch_waifu", "data": {"id": "alpha"}})
        _until(ws, "thread_message")
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": tid}})
        state, _ = _until(ws, "waifu_state")
        assert state["data"]["active"] == "beta"


def test_a_switch_mid_reply_waits_for_the_reply(kernel, monkeypatch):
    # FR-S-2: the turn in flight finishes with the old companion; the chip learns
    # who comes next; she takes over (divider, voice) as soon as the reply ends.
    async def slow_stream(role, messages, tools, **kwargs):
        await asyncio.sleep(0.3)
        yield {"type": "content", "text": f"{messages[0]['content'][:5]} [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", slow_stream)
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "send", "data": {"text": "first"}})
        _until(ws, "turn_start")
        ws.send_json({"v": 1, "type": "switch_waifu", "data": {"id": "beta"}})
        state, _ = _until(ws, "waifu_state")
        assert state["data"]["active"] == "alpha" and state["data"]["pending"] == "beta"
        _until(ws, "turn_done")
        divider, _ = _until(ws, "thread_message")             # as the reply ends, not at the next message
        assert divider["data"]["message"]["content"] == "Switched to Beta"
        _chat(ws, "second")
    stored = conversation.get_manager().store.messages(opened["data"]["thread"]["id"])
    assert [(m.role, m.speaker_name) for m in stored] == [
        ("user", None), ("assistant", "Alpha"), ("divider", "Beta"), ("user", None), ("assistant", "Beta"),
    ]


def test_closing_mid_reply_with_a_switch_pending_still_ends_the_session(kernel, monkeypatch):
    # Review finding: the pending switch used to write to the closed socket, and that
    # error skipped the rest of the teardown (screen loops, the session-end memory pass).
    passes = []

    async def slow_stream(role, messages, tools, **kwargs):
        await asyncio.sleep(5)
        yield {"type": "content", "text": "late [happy]"}

    class Writer:
        async def run_pass(self, reason, *_a, **_k):
            passes.append(reason)

        def preempt(self):
            return None

    monkeypatch.setattr(router, "stream_with_tools", slow_stream)
    monkeypatch.setattr(writer, "WRITER", Writer())
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "send", "data": {"text": "first"}})
        _until(ws, "turn_start")
        ws.send_json({"v": 1, "type": "switch_waifu", "data": {"id": "beta"}})
        state, _ = _until(ws, "waifu_state")
        assert state["data"]["pending"] == "beta"
        ws.close()                         # the window goes; TestClient cancels the endpoint on exit, so wait here
        for _ in range(200):
            if passes:
                break
            time.sleep(0.01)
    assert "session_end" in passes
    stored = conversation.get_manager().store.messages(opened["data"]["thread"]["id"])
    assert "divider" not in [m.role for m in stored]                    # nobody was there to switch for


def test_rename_search_and_delete(kernel):
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        tid = opened["data"]["thread"]["id"]
        ws.send_json({"v": 1, "type": "thread_rename", "data": {"id": tid, "title": "Garden plans"}})
        listing, _ = _until(ws, "thread_list")
        while listing["data"]["threads"][0]["title"] != "Garden plans":
            listing, _ = _until(ws, "thread_list")
        ws.send_json({"v": 1, "type": "thread_search", "data": {"query": "garden"}})
        found, _ = _until(ws, "thread_list")
        while found["data"]["query"] != "garden":
            found, _ = _until(ws, "thread_list")
        assert [t["id"] for t in found["data"]["threads"]] == [tid]
        ws.send_json({"v": 1, "type": "thread_delete", "data": {"id": tid}})
        replacement, _ = _until(ws, "thread_opened")
        assert replacement["data"]["thread"]["id"] != tid
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": tid}})
        err, _ = _until(ws, "error")
        assert err["data"]["code"] == "unknown_thread"


def test_another_web_page_cannot_open_the_kernel_socket(kernel):
    # review finding: CORS does not cover websockets, so any page the user had open
    # could read every thread; Kokyu's own page and local programs still connect
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with kernel.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
    with kernel.websocket_connect("/ws", headers={"origin": "http://localhost:1420"}) as ws:
        assert ws.receive_json()["type"] == "surface_status"


def test_regenerate_replaces_the_last_reply_without_repeating_the_line(kernel, monkeypatch):
    seen = []
    replies = iter(["first try [happy]", "second try [happy]"])

    async def recording_stream(role, messages, tools, **kwargs):
        seen.append([m["content"] for m in messages if m["role"] in ("user", "assistant")])
        yield {"type": "content", "text": next(replies)}

    monkeypatch.setattr(router, "stream_with_tools", recording_stream)
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "tell me something")
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        start, _ = _until(ws, "turn_start")
        assert start["data"]["user_text"] == "tell me something"
        done, _ = _until(ws, "turn_done")
        assert done["data"]["text"] == "second try"
    # the model saw the line once and not the replaced reply; the thread keeps one copy
    assert seen[1] == ["tell me something"]
    stored = conversation.get_manager().store.messages(opened["data"]["thread"]["id"])
    assert [(m.role, m.content) for m in stored] == [("user", "tell me something"), ("assistant", "second try")]


def test_regenerate_after_a_companion_switch_still_replaces_the_reply(kernel):
    # review finding: a divider after the reply must not make Regenerate refuse
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "hello")
        ws.send_json({"v": 1, "type": "switch_waifu", "data": {"id": "beta"}})
        _until(ws, "thread_message")
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        done, _ = _until(ws, "turn_done")
    stored = conversation.get_manager().store.messages(opened["data"]["thread"]["id"])
    assert [m.role for m in stored] == ["divider", "user", "assistant"]
    assert stored[-1].speaker_name == "Beta" and done["data"]["text"] == stored[-1].content


def test_a_failed_regenerate_keeps_the_old_reply(kernel, monkeypatch):
    # review finding: the old exchange goes only once a new reply exists
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "hello")

        async def silent(role, messages, tools, **kwargs):
            return
            yield  # an async generator that says nothing

        monkeypatch.setattr(router, "stream_with_tools", silent)
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        _until(ws, "turn_done")

        seen = []

        async def recording(role, messages, tools, **kwargs):
            seen.append([m["content"] for m in messages if m["role"] in ("user", "assistant")])
            yield {"type": "content", "text": "sure [happy]"}

        monkeypatch.setattr(router, "stream_with_tools", recording)
        _chat(ws, "and then?")
    stored = conversation.get_manager().store.messages(opened["data"]["thread"]["id"])
    assert [(m.role, m.content) for m in stored][:2] == [("user", "hello"), ("assistant", "You said: hello.")]
    # the model's context got the old exchange back too (review finding)
    assert seen[0] == ["hello", "You said: hello.", "and then?"]


def test_regenerate_with_nothing_to_redo_is_refused(kernel):
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        err, _ = _until(ws, "error")
    assert err["data"]["code"] == "bad_message"
