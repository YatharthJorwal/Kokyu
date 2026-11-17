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
import prompting
import router
import turns
import waifus
from audio import tts
from conversation import ConversationManager, Speaker, history_from
from memory import recall, writer
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
        yield {"type": "usage", "tokens_in": 120, "tokens_out": 8}

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
    # FR-C-10: the reply records the backend's token counts; the user line does not carry them
    user, reply = opened["data"]["messages"]
    assert (reply["tokens_in"], reply["tokens_out"]) == (120, 8)
    assert "tokens_in" not in (user["meta"] or {})


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


def test_her_profiles_chat_button_opens_a_new_thread_with_her_and_no_divider(kernel):
    # D-091 (FR-W-9): nobody switched in the open thread, so it gets no divider line
    with kernel.websocket_connect("/ws") as ws:
        first, _ = _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "thread_new", "data": {"waifu_id": "beta"}})
        opened, seen = _until(ws, "thread_opened")
        assert opened["data"]["thread"]["active_waifu_id"] == "beta" and opened["data"]["messages"] == []
        assert [m["data"]["active"] for m in seen if m["type"] == "waifu_state"] == ["beta"]
        assert not any(m["type"] == "thread_message" for m in seen)
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": first["data"]["thread"]["id"]}})
        back, _ = _until(ws, "thread_opened")
        assert back["data"]["messages"] == []                          # still no divider there
        ws.send_json({"v": 1, "type": "thread_new", "data": {"waifu_id": "nobody"}})
        refused, _ = _until(ws, "error")
        assert refused["data"]["code"] == "unknown_waifu"


def test_a_chosen_picture_reaches_every_window(kernel, monkeypatch):
    import base64
    import io

    from PIL import Image

    class OtherWindow:                                            # a second window, as the hub sees it
        def __init__(self):
            self.frames = []

        async def send_json(self, frame):
            self.frames.append(frame)

    other = OtherWindow()
    monkeypatch.setattr(hub, "connections", {other})
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (1, 2, 3)).save(buf, format="JPEG")
    picture = base64.b64encode(buf.getvalue()).decode()
    with kernel.websocket_connect("/ws") as one:
        _until(one, "thread_opened")
        one.send_json({"v": 1, "type": "set_portrait", "data": {"waifu_id": "alpha", "image_b64": picture}})
        roster, _ = _until(one, "waifu_roster")
        alpha = {w["id"]: w for w in roster["data"]["waifus"]}["alpha"]
        assert alpha["portrait_chosen"] is True and alpha["portrait"].startswith("c")
        assert [f["type"] for f in other.frames] == ["waifu_roster"]
        one.send_json({"v": 1, "type": "set_portrait", "data": {"waifu_id": "alpha", "image_b64": None}})
        roster, _ = _until(one, "waifu_roster")
        assert {w["id"]: w for w in roster["data"]["waifus"]}["alpha"]["portrait_chosen"] is False
        for bad in ("not base64!", base64.b64encode(b"<html>").decode()):
            one.send_json({"v": 1, "type": "set_portrait", "data": {"waifu_id": "alpha", "image_b64": bad}})
            refused, _ = _until(one, "error")
            assert refused["data"]["code"] == "picture_unreadable"
        one.send_json({"v": 1, "type": "set_portrait", "data": {"waifu_id": "nobody", "image_b64": None}})
        refused, _ = _until(one, "error")
        assert refused["data"]["code"] == "unknown_waifu"


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


def test_pin_and_unpin_a_thread(kernel):
    # UI1-09 (D-094)
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        tid = opened["data"]["thread"]["id"]

        def pinned_after(on):
            ws.send_json({"v": 1, "type": "thread_pin", "data": {"id": tid, "on": on}})
            # an earlier list (from opening) may still be on its way: wait for the change
            for _ in range(5):
                listing, _ = _until(ws, "thread_list")
                flags = [t["pinned"] for t in listing["data"]["threads"] if t["id"] == tid]
                if flags == [on]:
                    return True
            return False

        assert pinned_after(True) and pinned_after(False)
        ws.send_json({"v": 1, "type": "thread_pin", "data": {"id": "nope", "on": True}})
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


def test_an_edited_last_line_replaces_the_exchange_with_the_new_words(kernel, monkeypatch):
    # UI1-07 (FR-C-9, D-092): edit and resend the last message
    seen = []

    async def recording(role, messages, tools, **kwargs):
        seen.append([m["content"] for m in messages if m["role"] in ("user", "assistant")])
        yield {"type": "content", "text": "reply %d [happy]" % len(seen)}

    monkeypatch.setattr(router, "stream_with_tools", recording)
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "first")
        _chat(ws, "tell me abuot cats")
        ws.send_json({"v": 1, "type": "regenerate", "data": {"text": "  tell me about cats  "}})
        start, _ = _until(ws, "turn_start")
        done, _ = _until(ws, "turn_done")
    assert start["data"]["user_text"] == "tell me about cats" and start["data"]["file"] is False
    assert seen[2] == ["first", "reply 1", "tell me about cats"]          # the typo never reaches the model
    stored = conversation.get_manager().store.messages(opened["data"]["thread"]["id"])
    assert [m.content for m in stored] == ["first", "reply 1", "tell me about cats", done["data"]["text"]]


def test_a_line_with_a_file_cannot_be_edited(kernel, monkeypatch):
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "send_file", "data": {"filename": "a.txt", "kind": "text", "content": "milk"}})
        start, _ = _until(ws, "turn_start")
        _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "regenerate", "data": {"text": "something else"}})
        err, _ = _until(ws, "error")
    assert start["data"]["file"] is True
    assert err["data"]["code"] == "bad_message" and "file" in err["data"]["message"]


def test_regenerate_with_nothing_to_redo_is_refused(kernel):
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        err, _ = _until(ws, "error")
    assert err["data"]["code"] == "bad_message"


# -- conversation modes over the socket (FR-MODE-1, 2, 4; D-074) --------------

CARD = {"title": "Rain at the station", "setting": "A station at night.", "user_role": "  ", "opening": "*She waves.*"}


def _systems(monkeypatch):
    """Records each turn's system message and tool list."""
    seen = []

    async def recording(role, messages, tools, **kwargs):
        seen.append({"role": role, "system": messages[0]["content"], "tools": list(tools)})
        yield {"type": "content", "text": "Mm. [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", recording)
    return seen


def _new_roleplay(ws, scenario=CARD):
    ws.send_json({"v": 1, "type": "thread_new", "data": {"mode": "roleplay", "scenario": scenario}})
    opened, _ = _until(ws, "thread_opened")
    return opened["data"]["thread"]


def test_a_roleplay_thread_starts_from_its_card_and_keeps_its_layer(kernel, monkeypatch):
    """FR-MODE-1, 2, 4, 6: the mode and the filled-in card are the thread's; the card's
    title names it; the system message carries the roleplay layer and the card."""
    seen = _systems(monkeypatch)
    with kernel.websocket_connect("/ws") as ws:
        first, _ = _until(ws, "thread_opened")
        assert first["data"]["thread"]["mode"] == "chat" and first["data"]["thread"]["scenario"] == {}
        _temp_on(ws)   # Temp is not carried into the new thread (as before modes)
        thread = _new_roleplay(ws)
        assert thread["mode"] == "roleplay" and thread["temp"] is False
        assert thread["title"] == "Rain at the station"
        assert thread["scenario"] == {"title": "Rain at the station", "setting": "A station at night.", "opening": "*She waves.*"}
        _temp_on(ws)
        _chat(ws, "Hi!")
    system = seen[-1]["system"]
    assert prompting.ROLEPLAY_LAYER in system and prompting.CHAT_LAYER not in system
    assert "Setting: A station at night." in system and "The user plays" not in system
    assert prompting.TOOL_GUIDANCE not in system
    assert seen[-1]["role"] == "chat"   # the same router role in both modes (D-074)
    stored = conversation.get_manager().store.get_thread(thread["id"])
    assert stored.title == "Rain at the station"   # the first user line does not rename it


def test_a_blank_roleplay_has_no_card_and_a_new_thread_after_it_is_chat(kernel, monkeypatch):
    seen = _systems(monkeypatch)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        blank = _new_roleplay(ws, scenario={"title": " ", "opening": ""})
        assert blank["mode"] == "roleplay" and blank["scenario"] == {} and blank["title"] == ""
        _temp_on(ws)
        _chat(ws, "Once upon a time")
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        chat, _ = _until(ws, "thread_opened")
        assert chat["data"]["thread"]["mode"] == "chat"
        _temp_on(ws)
        _chat(ws, "What is 2 + 2?")
    assert prompting.ROLEPLAY_LAYER in seen[0]["system"] and prompting.SCENARIO_HEADING not in seen[0]["system"]
    assert prompting.CHAT_LAYER in seen[1]["system"] and prompting.TOOL_GUIDANCE in seen[1]["system"]


def test_a_chat_thread_ignores_a_card_sent_with_it(kernel):
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "thread_new", "data": {"mode": "chat", "scenario": CARD}})
        opened, _ = _until(ws, "thread_opened")
    assert opened["data"]["thread"]["mode"] == "chat" and opened["data"]["thread"]["scenario"] == {}
    assert opened["data"]["thread"]["title"] == ""


def test_a_companion_switch_and_a_regenerate_keep_the_roleplay_layer(kernel, monkeypatch):
    """FR-MODE-2: every place history[0] is rebuilt uses the thread's mode, so neither
    a switch nor a regenerate drops a roleplay back to chat."""
    seen = _systems(monkeypatch)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        thread = _new_roleplay(ws)
        _temp_on(ws)
        _chat(ws, "Hello")
        ws.send_json({"v": 1, "type": "switch_waifu", "data": {"id": "beta"}})
        _until(ws, "thread_message")
        _chat(ws, "Who are you now?")
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": thread["id"]}})
        _until(ws, "thread_opened")
        _chat(ws, "Back again")
    assert len(seen) == 4
    for turn in seen:
        assert prompting.ROLEPLAY_LAYER in turn["system"] and "Title: Rain at the station" in turn["system"]
        assert prompting.TOOL_GUIDANCE not in turn["system"]
    assert seen[0]["system"].startswith("You are Alpha")
    assert all(turn["system"].startswith("You are Beta") for turn in seen[1:])
    # only the persona changed with the switch (FR-W-3)
    registry = waifus.get_registry()
    alpha, beta = registry.get("alpha").prompt.rstrip(), registry.get("beta").prompt.rstrip()
    assert seen[0]["system"].removeprefix(alpha) == seen[1]["system"].removeprefix(beta)


def test_a_roleplay_thread_keeps_its_story_out_of_the_transcript_and_regenerates(kernel, monkeypatch):
    """FR-MODE-4 (K1c-03): over the socket, a roleplay turn (Temp off) gets the profile
    card and no tools, is never written to transcript_log, keeps its paragraphs in the
    saved reply, and Regenerate replaces it with no transcript row to drop."""
    logged, dropped, seen = [], [], []
    replies = iter(["*She looks up.*\n\nOh, it's you. [happy]", "*She waves.*\n\n\"Over here!\" [happy]",
                    "Two. [neutral]"])

    async def recording_log(user_text, assistant_text, temp=False, speaker=None):
        logged.append(user_text)
        return 7

    async def recording_drop(row_id):
        dropped.append(row_id)

    async def card(framing, **_k):
        return framing.format(card="Sam.")

    async def recording(role, messages, offered, **kwargs):
        seen.append({"role": role, "tools": list(offered), "notes": [m["content"] for m in messages[1:] if m["role"] == "system"]})
        yield {"type": "content", "text": next(replies)}

    monkeypatch.setattr(turns, "log_transcript_turn", recording_log)
    monkeypatch.setattr(turns, "drop_transcript_turn", recording_drop)
    monkeypatch.setattr(recall, "build_profile_context", card)
    monkeypatch.setattr(router, "stream_with_tools", recording)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        thread = _new_roleplay(ws)
        _chat(ws, "Hello?")
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        done, _ = _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "1 + 1?")
    assert done["data"]["text"] == "*She waves.*\n\n\"Over here!\""
    stored = conversation.get_manager().store.messages(thread["id"])
    # Since K1c-06 (FR-MODE-6) CARD's opening line is stored first as her opening
    # message; Regenerate replaced only the exchange after it.
    assert [(m.role, m.content) for m in stored] == [
        ("assistant", "*She waves.*"), ("user", "Hello?"), ("assistant", "*She waves.*\n\n\"Over here!\""),
    ]
    assert stored[0].meta == {"opening": True}
    assert "log_id" not in (stored[-1].meta or {})
    assert logged == ["1 + 1?"] and dropped == []          # only the chat thread's turn reached the transcript
    assert seen[0]["tools"] == [] and seen[0]["role"] == "chat" and seen[0]["notes"] == [
        prompting.ROLEPLAY_PROFILE_FRAMING.format(card="Sam.")
    ]
    assert seen[2]["tools"]                                # the chat thread offers tools again


# -- the opening line and saved scenario cards (FR-MODE-6, K1c-06; D-074) -----


@pytest.mark.asyncio
async def test_the_opening_line_is_her_first_message_but_never_history_or_an_exchange(manager):
    """FR-MODE-6: the opening is stored as her first message, flagged; history_from leaves
    it out (the system message carries it) and Regenerate never targets it."""
    alpha = Speaker("alpha", "Alpha")
    t = await manager.new_thread(waifu_id="alpha", mode="roleplay", scenario={"opening": "*She waves.*"})
    opening = await manager.record_opening(t.id, "*She waves.*", speaker=alpha)
    assert opening.role == "assistant" and opening.meta == {"opening": True}
    assert opening.speaker_name == "Alpha" and opening.model_ref is None and opening.effort is None
    assert await manager.last_exchange(t.id) is None                           # nothing to regenerate
    assert await manager.history(t, "sys") == [{"role": "system", "content": "sys"}]
    await manager.record_exchange(t.id, "Hi!", "", speaker=alpha)              # a failed turn
    again, ids, _ = await manager.last_exchange(t.id)
    assert again == "Hi!" and opening.id not in ids and len(ids) == 1
    await manager.delete_messages(ids)
    await manager.record_exchange(t.id, "Hi!", "Hello. *smiles*", speaker=alpha)
    again, ids, _ = await manager.last_exchange(t.id)
    assert again == "Hi!" and opening.id not in ids and len(ids) == 2
    history = await manager.history(t, "sys")
    assert [m["content"] for m in history[1:]] == ["Hi!", "Hello. *smiles*"]


def test_history_leaves_out_an_opening_wherever_it_sits():
    """FR-MODE-6: dropped by its flag, not only because it leads, so it never takes a
    slot in the history window either."""

    class M:
        def __init__(self, role, content, meta=None):
            self.role, self.content, self.meta = role, content, meta or {}

    msgs = [M("assistant", "*waves*", {"opening": True}), M("user", "u1"), M("assistant", "a1")]
    assert [m["content"] for m in history_from(msgs, "S", max_messages=2)[1:]] == ["u1", "a1"]


def _model_messages(monkeypatch):
    """Records every message list the model is given."""
    seen = []

    async def recording(role, messages, tools, **kwargs):
        seen.append([dict(m) for m in messages])
        yield {"type": "content", "text": "Mm. [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", recording)
    return seen


def test_a_roleplay_opening_is_shown_stored_and_in_the_system_message_only(kernel, monkeypatch):
    """FR-MODE-6 over the socket: thread_opened shows the opening as her first message;
    the model gets it in the scenario block, never as a history line; Regenerate with
    only the opening is refused, and later replaces only the exchange."""
    seen = _model_messages(monkeypatch)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "thread_new", "data": {"mode": "roleplay", "scenario": CARD}})
        opened, _ = _until(ws, "thread_opened")
        thread_id = opened["data"]["thread"]["id"]
        [first] = opened["data"]["messages"]
        assert (first["role"], first["content"], first["speaker_name"]) == ("assistant", "*She waves.*", "Alpha")
        assert first["meta"] == {"opening": True}
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        err, _ = _until(ws, "error")
        assert err["data"]["code"] == "bad_message"                     # the opening is not a reply to redo
        _temp_on(ws)
        _chat(ws, "Hi!")
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": thread_id}})
        reopened, _ = _until(ws, "thread_opened")
        _chat(ws, "Again")
    assert len(seen) == 3
    for messages in seen:
        assert "The scene opened with your line: *She waves.*" in messages[0]["content"]
        assert all(m["content"] != "*She waves.*" for m in messages[1:])
        assert messages[1]["role"] == "user"
    assert [m["content"] for m in seen[1][1:]] == ["Hi!"]                # the regenerate: the opening stays out
    stored = conversation.get_manager().store.messages(thread_id)
    assert [(m.role, m.content) for m in stored] == [
        ("assistant", "*She waves.*"), ("user", "Hi!"), ("assistant", "Mm."), ("user", "Again"), ("assistant", "Mm."),
    ]
    assert [m["content"] for m in reopened["data"]["messages"]][:1] == ["*She waves.*"]


def test_no_opening_line_without_one_in_the_card(kernel):
    """FR-MODE-6: a card without an opening, a blank roleplay and a chat thread sent a
    card all start empty."""
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        for data in (
            {"mode": "roleplay", "scenario": {"title": "Quiet", "opening": "   "}},
            {"mode": "roleplay"},
            {"mode": "chat", "scenario": CARD},
        ):
            ws.send_json({"v": 1, "type": "thread_new", "data": data})
            opened, _ = _until(ws, "thread_opened")
            assert opened["data"]["messages"] == []


def _scenarios(ws, type_, data=None):
    ws.send_json({"v": 1, "type": type_, "data": data or {}})
    frame, _ = _until(ws, "scenarios")
    return frame["data"]["cards"]


def test_scenario_cards_are_listed_saved_edited_and_deleted_over_the_socket(kernel):
    """FR-MODE-6: every save and delete answers with the fresh list, newest first; an
    empty title is named from the setting, else "Untitled scenario"; the card keeps
    only its filled-in fields."""
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        assert _scenarios(ws, "scenario_list") == []
        cards = _scenarios(ws, "scenario_save", {"card": CARD})
        assert len(cards) == 1 and cards[0]["title"] == "Rain at the station"
        rain = cards[0]
        assert rain["card"] == {"title": "Rain at the station", "setting": "A station at night.", "opening": "*She waves.*"}
        assert set(rain) == {"id", "title", "card", "updated_at"}
        cards = _scenarios(ws, "scenario_save", {"card": {"setting": "A library at dusk."}})
        assert [c["title"] for c in cards] == ["A library at dusk.", "Rain at the station"]
        cards = _scenarios(ws, "scenario_save", {"card": {}})
        assert cards[0]["title"] == "Untitled scenario" and cards[0]["card"] == {}
        cards = _scenarios(ws, "scenario_save", {"id": rain["id"], "card": {"title": "Rain, later"}})
        assert len(cards) == 3 and cards[0]["id"] == rain["id"] and cards[0]["card"] == {"title": "Rain, later"}
        cards = _scenarios(ws, "scenario_delete", {"id": rain["id"]})
        assert rain["id"] not in [c["id"] for c in cards] and len(cards) == 2
        assert len(_scenarios(ws, "scenario_delete", {"id": rain["id"]})) == 2   # already gone: the list still answers
    # saved in threads.db, not kept by the window
    saved = conversation.get_manager().store.list_scenarios()
    assert [c.title for c in saved] == ["Untitled scenario", "A library at dusk."]


def test_only_a_saves_answer_names_the_saved_card(kernel):
    """FR-MODE-6: the dialog ties its pending save to the answer naming the card, so a
    list or delete answer can never be taken for it (and Update cannot be pointed at
    another card). A new card and a replaced one are both named."""

    def answer(ws, type_, data=None):
        ws.send_json({"v": 1, "type": type_, "data": data or {}})
        return _until(ws, "scenarios")[0]["data"]

    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        first = answer(ws, "scenario_save", {"card": CARD})
        assert first["saved_id"] == first["cards"][0]["id"]
        other = answer(ws, "scenario_save", {"card": {"setting": "A library at dusk."}})
        again = answer(ws, "scenario_save", {"id": first["saved_id"], "card": {"title": "Rain, later"}})
        assert again["saved_id"] == first["saved_id"] != other["saved_id"]
        assert "saved_id" not in answer(ws, "scenario_list")
        assert "saved_id" not in answer(ws, "scenario_delete", {"id": other["saved_id"]})


def test_a_scenario_store_failure_is_reported_not_fatal(kernel, monkeypatch):
    async def broken(*_a, **_k):
        raise RuntimeError("disk full")

    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        monkeypatch.setattr(conversation.get_manager(), "save_scenario", broken)
        ws.send_json({"v": 1, "type": "scenario_save", "data": {"card": CARD}})
        err, _ = _until(ws, "error")
        assert err["data"]["code"] == "threads_unavailable"
        assert _scenarios(ws, "scenario_list") == []                       # the connection is still fine
