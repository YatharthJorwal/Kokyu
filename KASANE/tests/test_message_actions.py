"""A message's actions (D-100): Rewind to here, roleplay pins, swipes (Regenerate keeps
the old replies), New chat from here, and the stored ids a turn reports."""
from __future__ import annotations

import dataclasses

import pytest

import conversation
import prompting
import router
import session
from config import CONFIG
from conversation import ConversationManager, Speaker, next_swipe
from test_conversation import CARD, _chat, _new_roleplay, _temp_on, _until, kernel  # noqa: F401 -- the fixture
from threads import ThreadStore

ALPHA = Speaker("alpha", "Alpha")


@pytest.fixture
def store(tmp_path):
    return ThreadStore(tmp_path / "threads.db")


def _thread_with(store, lines, **kwargs):
    t = store.create_thread(**kwargs)
    ids = [store.add_message(t.id, role, text, meta=meta).id for role, text, meta in lines]
    return t, ids


def test_rewind_deletes_everything_after_the_message_and_a_summary_past_it(store):
    t, ids = _thread_with(store, [("user", "a", None), ("assistant", "b", None), ("user", "c", {"log_id": 7}), ("assistant", "d", None)])
    store.set_story(t.id, "they met", ids[3])
    gone = store.rewind(t.id, ids[1])
    assert [m.content for m in gone] == ["c", "d"] and gone[0].meta["log_id"] == 7
    assert [m.content for m in store.messages(t.id)] == ["a", "b"]
    assert store.get_story(t.id) is None   # it reached past the rewind: rebuilt from what is left


def test_rewind_keeps_a_summary_that_ends_before_it(store):
    t, ids = _thread_with(store, [("user", "a", None), ("assistant", "b", None), ("user", "c", None)])
    store.set_story(t.id, "they met", ids[0])
    store.rewind(t.id, ids[1])
    assert store.get_story(t.id).through_message_id == ids[0]


def test_a_branch_copies_the_thread_up_to_the_message_in_the_same_mode(store):
    scenario = {"title": "Rain", "setting": "A station."}
    t, ids = _thread_with(
        store,
        [("user", "a", {"log_id": 3, "pinned": True}), ("assistant", "b", None), ("user", "c", None), ("assistant", "d", None)],
        mode="roleplay",
        scenario=scenario,
        active_waifu_id="alpha",
        model_ref="local:ollama/x",
    )
    store.set_story(t.id, "they met", ids[1])
    copy = store.branch(t.id, ids[1])
    assert copy.id != t.id and copy.mode == "roleplay" and copy.scenario == scenario
    assert copy.active_waifu_id == "alpha" and copy.model_ref == "local:ollama/x" and copy.title == store.get_thread(t.id).title == "a"
    copied = store.messages(copy.id)
    assert [m.content for m in copied] == ["a", "b"]
    assert copied[0].meta == {"pinned": True}   # the pin comes along, the original's log row does not
    assert store.get_story(copy.id).through_message_id == copied[1].id
    assert [m.content for m in store.messages(t.id)] == ["a", "b", "c", "d"]   # the original is untouched


@pytest.mark.asyncio
async def test_swipes_keep_every_reply_and_show_the_chosen_one(tmp_path):
    manager = ConversationManager(ThreadStore(tmp_path / "threads.db"))
    t = await manager.new_thread(waifu_id="alpha")
    _, first = await manager.record_exchange(t.id, "hi", "one", speaker=ALPHA, model_ref="m1")
    _, second = await manager.record_exchange(t.id, "hi", "two", speaker=ALPHA, model_ref="m2", reply_meta=next_swipe(first))
    assert second.meta == {"swipes": [conversation.candidate_of(first), None], "swipe": 1}
    _, third = await manager.record_exchange(t.id, "hi", "three", speaker=ALPHA, reply_meta=next_swipe(second))
    assert len(third.meta["swipes"]) == 3 and third.meta["swipe"] == 2
    back = await manager.swipe_to(third, 0)
    assert (back.content, back.model_ref, back.meta["swipe"]) == ("one", "m1", 0)
    assert back.meta["swipes"][0] is None and back.meta["swipes"][2]["content"] == "three"
    forward = await manager.swipe_to(back, 1)
    assert (forward.content, forward.model_ref) == ("two", "m2")
    with pytest.raises(ValueError):
        await manager.swipe_to(forward, 1)   # already shown
    with pytest.raises(ValueError):
        await manager.swipe_to(forward, 5)


# ── over the socket ───────────────────────────────────────────────────────


def _send(ws, type_, data):
    ws.send_json({"v": 1, "type": type_, "data": data})


def _recording(monkeypatch, replies=None):
    """Records each turn's messages; answers from `replies` in turn, else 'Mm.'."""
    seen = []
    queue = list(replies or [])

    async def stream(role, messages, tools, **kwargs):
        seen.append([dict(m) for m in messages])
        yield {"type": "content", "text": (queue.pop(0) if queue else "Mm.") + " [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", stream)
    return seen


def test_a_turn_reports_its_stored_ids_before_turn_done(kernel):
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        _send(ws, "send", {"text": "hello"})
        saved, _ = _until(ws, "exchange_saved")
        _, after = _until(ws, "turn_done")
    data = saved["data"]
    assert data["user"]["content"] == "hello" and data["reply"]["content"] == "You said: hello."
    assert data["reply"]["id"] > data["user"]["id"]
    assert after[-1]["type"] == "turn_done"


def test_regenerate_swipes_and_the_model_sees_the_reply_shown(kernel, monkeypatch):
    seen = _recording(monkeypatch, ["first", "second", "after"])
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        _chat(ws, "tell me")
        _send(ws, "regenerate", {})
        saved, _ = _until(ws, "exchange_saved")
        _until(ws, "turn_done")
        reply = saved["data"]["reply"]
        assert reply["content"] == "second" and reply["meta"]["swipe"] == 1
        assert reply["meta"]["swipes"][0]["content"] == "first"
        _send(ws, "message_swipe", {"id": reply["id"], "to": 0})
        updated, _ = _until(ws, "message_updated")
        assert updated["data"]["message"]["content"] == "first"
        _chat(ws, "and then?")
    # the next turn's history carries the reply that was swiped back to
    assert [m["content"] for m in seen[-1] if m["role"] == "assistant"] == ["first"]


def test_only_her_latest_reply_can_be_swiped(kernel, monkeypatch):
    _recording(monkeypatch)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        _send(ws, "send", {"text": "one"})
        first, _ = _until(ws, "exchange_saved")
        _until(ws, "turn_done")
        _chat(ws, "two")
        _send(ws, "message_swipe", {"id": first["data"]["reply"]["id"], "to": 0})
        refused, _ = _until(ws, "error")
    assert refused["data"]["code"] == "bad_message"


def test_rewind_to_here_deletes_what_came_after(kernel, monkeypatch):
    seen = _recording(monkeypatch)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        _send(ws, "send", {"text": "one"})
        first, _ = _until(ws, "exchange_saved")
        _until(ws, "turn_done")
        _chat(ws, "two")
        _send(ws, "message_rewind", {"id": first["data"]["reply"]["id"]})
        opened, _ = _until(ws, "thread_opened")
        assert [m["content"] for m in opened["data"]["messages"]] == ["one", "Mm."]
        _chat(ws, "three")
    assert [m["content"] for m in seen[-1] if m["role"] in ("user", "assistant")] == ["one", "Mm.", "three"]


def test_pins_are_for_roleplay_only(kernel):
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        _send(ws, "send", {"text": "remember this"})
        saved, _ = _until(ws, "exchange_saved")
        _until(ws, "turn_done")
        _send(ws, "message_pin", {"id": saved["data"]["user"]["id"], "on": True})
        refused, _ = _until(ws, "error")
    assert refused["data"]["code"] == "bad_message"


def test_a_pinned_roleplay_message_is_always_in_her_note_up_to_the_limit(kernel, monkeypatch):
    monkeypatch.setattr(session, "CONFIG", dataclasses.replace(CONFIG, story=dataclasses.replace(CONFIG.story, max_pins=1)))
    seen = _recording(monkeypatch)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _new_roleplay(ws)
        _temp_on(ws)
        _send(ws, "send", {"text": "The key is under the mat."})
        saved, _ = _until(ws, "exchange_saved")
        _until(ws, "turn_done")
        _send(ws, "message_pin", {"id": saved["data"]["user"]["id"], "on": True})
        updated, _ = _until(ws, "message_updated")
        assert updated["data"]["message"]["meta"]["pinned"] is True
        _send(ws, "message_pin", {"id": saved["data"]["reply"]["id"], "on": True})
        refused, _ = _until(ws, "error")
        assert refused["data"]["code"] == "pin_limit"
        _chat(ws, "Where is it?")
    notes = [m["content"] for m in seen[-1] if m["role"] == "system"][1:]
    pins_prefix = prompting.PINS_NOTE.split("{")[0]
    assert any(pins_prefix in n and "The user: The key is under the mat." in n for n in notes)


def test_new_chat_from_here_opens_a_copy_in_the_same_mode(kernel, monkeypatch):
    _recording(monkeypatch)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        story = _new_roleplay(ws)
        _temp_on(ws)
        _send(ws, "send", {"text": "one"})
        first, _ = _until(ws, "exchange_saved")
        _until(ws, "turn_done")
        _chat(ws, "two")
        _send(ws, "message_branch", {"id": first["data"]["reply"]["id"]})
        opened, _ = _until(ws, "thread_opened")
    copy = opened["data"]["thread"]
    assert copy["id"] != story["id"] and copy["mode"] == "roleplay" and copy["scenario"] == story["scenario"]
    assert [m["content"] for m in opened["data"]["messages"]] == [CARD["opening"], "one", "Mm."]
    original = conversation.get_manager().store.messages(story["id"])
    assert [m.content for m in original][-2:] == ["two", "Mm."]
