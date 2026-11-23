"""Story memory (K1c-04; FR-MODE-5, D-074).

A roleplay thread keeps a running summary in threads.db, written by the local
memory_writer role in batches: never below story.summarize_every waiting lines,
never the newest story.keep_recent lines (so Regenerate cannot touch summarized
text), never for Temp Chat or chat threads, and a failing model keeps the old
summary. The summary reaches the next turn's ephemeral note and goes with its thread.
No test here reaches a real model: router.stream_text is always a fake.
"""
from __future__ import annotations

import asyncio
import dataclasses
import itertools
import time

import pytest

import boot
import conversation
import llm
import model_loader
import prompting
import router
import story
from audio import arbiter
from config import CONFIG, StoryConfig
from conversation import ConversationManager, Speaker
from test_conversation import _chat, _new_roleplay, _until, kernel  # noqa: F401 -- the socket fixture
from threads import Message, ThreadStore

ALPHA = Speaker("alpha", "Alpha")


@pytest.fixture
def manager(tmp_path):
    ticks = itertools.count(1000)
    return ConversationManager(ThreadStore(tmp_path / "threads.db", clock=lambda: float(next(ticks))))


@pytest.fixture
def limits(monkeypatch):
    """Sets story.* config for the test: limits(summarize_every=4, keep_recent=2)."""

    def set_limits(**values):
        monkeypatch.setattr(story, "CONFIG", dataclasses.replace(CONFIG, story=StoryConfig(**values)))

    set_limits(summarize_every=4, keep_recent=2, max_chars=2400)
    return set_limits


@pytest.fixture
def model(monkeypatch):
    """A fake memory_writer: records each call and answers from `replies` (default text)."""
    calls: list[dict] = []
    state = {"replies": [], "fail": None}

    async def fake_stream_text(role, messages, **kwargs):
        calls.append({"role": role, "messages": [dict(m) for m in messages], "kwargs": dict(kwargs)})
        if state["fail"] is not None:
            raise state["fail"]
        reply = state["replies"].pop(0) if state["replies"] else f"Summary {len(calls)}."
        for piece in (reply[: len(reply) // 2], reply[len(reply) // 2 :]):
            yield piece

    monkeypatch.setattr(router, "stream_text", fake_stream_text)
    return calls, state


@pytest.fixture
def keeper():
    return story.StoryKeeper(is_busy=lambda: False)


async def _roleplay(manager, exchanges: int, *, temp: bool = False, mode: str = "roleplay"):
    thread = await manager.new_thread(waifu_id="alpha", mode=mode, temp=temp)
    for n in range(1, exchanges + 1):
        await manager.record_exchange(thread.id, f"line {n}", f"reply {n}", speaker=ALPHA)
    return thread


# -- the store: one row per thread, deleted with it -------------------------------


def test_a_story_round_trips_and_goes_with_its_thread(tmp_path):
    """FR-MODE-5: story_memory cascades with the thread; a summary for a deleted
    thread is never written."""
    store = ThreadStore(tmp_path / "threads.db")
    thread = store.create_thread(mode="roleplay")
    assert store.get_story(thread.id) is None
    for n in range(10):
        store.add_message(thread.id, "user", f"line {n}")   # ids 1..10: a summary reaches a real message
    assert store.set_story(thread.id, "They met at the station.", 6) is True
    kept = store.get_story(thread.id)
    assert (kept.summary, kept.through_message_id) == ("They met at the station.", 6) and kept.updated_at
    assert store.set_story(thread.id, "They met, then left.", 10) is True   # replaced, not added
    assert store.get_story(thread.id).through_message_id == 10
    assert store.delete_thread(thread.id)
    assert store.get_story(thread.id) is None
    assert store.set_story(thread.id, "too late", 12) is False
    assert store.get_story(thread.id) is None


# -- what is folded ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_summary_below_the_threshold(manager, limits, model, keeper):
    """FR-MODE-5: 3 exchanges = 6 lines; the newest 2 are kept back, so 4 wait, which
    is below summarize_every=5: no model call and no row."""
    calls, _ = model
    limits(summarize_every=5, keep_recent=2, max_chars=2400)
    thread = await _roleplay(manager, 3)
    assert await keeper.catch_up(thread.id, manager) == 0
    assert calls == [] and await manager.story(thread.id) is None


@pytest.mark.asyncio
async def test_a_summary_is_written_and_through_message_id_advances(manager, limits, model, keeper):
    """FR-MODE-5: at the threshold the waiting lines are folded with the memory_writer
    role; the next fold starts from the old summary and only the newer lines."""
    calls, state = model
    state["replies"] = ["Sam met Alpha at the station.", "Sam and Alpha took the last train."]
    thread = await _roleplay(manager, 3)     # 6 lines: 4 foldable
    assert await keeper.catch_up(thread.id, manager) == 4
    messages = await manager.messages(thread.id)
    kept = await manager.story(thread.id)
    assert kept.summary == "Sam met Alpha at the station." and kept.through_message_id == messages[3].id
    assert calls[0]["role"] == "memory_writer"   # local-only role (D-015)
    system, user = (m["content"] for m in calls[0]["messages"])
    assert system == story.INSTRUCTION.format(words=story.words_for(2400))
    assert "the user: line 1" in user and "Alpha: reply 2" in user and "line 3" not in user
    assert story.NO_SUMMARY_YET in user

    for n in (4, 5):
        await manager.record_exchange(thread.id, f"line {n}", f"reply {n}", speaker=ALPHA)
    assert await keeper.catch_up(thread.id, manager) == 4
    messages = await manager.messages(thread.id)
    kept = await manager.story(thread.id)
    assert kept.summary == "Sam and Alpha took the last train." and kept.through_message_id == messages[7].id
    second = calls[1]["messages"][1]["content"]
    assert "Sam met Alpha at the station." in second
    assert "line 2" not in second and "line 3" in second and "reply 4" in second and "line 5" not in second


@pytest.mark.asyncio
async def test_the_newest_lines_are_never_folded_so_regenerate_cannot_reach_the_summary(
    manager, limits, model, keeper
):
    """FR-MODE-5 (D-074): the newest keep_recent lines stay out of every fold, and
    keep_recent below 2 still keeps the last exchange (what Regenerate replaces)."""
    calls, _ = model
    limits(summarize_every=1, keep_recent=0, max_chars=2400)   # clamped to 2
    thread = await _roleplay(manager, 4)
    await keeper.catch_up(thread.id, manager)
    messages = await manager.messages(thread.id)
    kept = await manager.story(thread.id)
    assert kept.through_message_id == messages[-3].id
    folded = " ".join(c["messages"][1]["content"] for c in calls)
    assert "line 4" not in folded and "reply 4" not in folded

    # Regenerate drops the last exchange and records a new one: the summary is untouched.
    _, old_ids, _ = await manager.last_exchange(thread.id)
    assert min(old_ids) > kept.through_message_id
    await manager.delete_messages(old_ids)
    await manager.record_exchange(thread.id, "line 4", "a better reply", speaker=ALPHA)
    assert (await manager.story(thread.id)).through_message_id == kept.through_message_id


def test_dividers_and_screen_remarks_are_not_part_of_the_story():
    lines = [
        Message(1, "t", 1.0, "user", "hi"),
        Message(2, "t", 2.0, "divider", "Switched to Beta"),
        Message(3, "t", 3.0, "assistant", "a remark", meta={"ambient": True}),
        Message(4, "t", 4.0, "assistant", "hello", speaker_name="Beta"),
        Message(5, "t", 5.0, "assistant", "   "),
        Message(6, "t", 6.0, "user", "and then?"),
    ]
    assert [m.id for m in story.foldable(lines, 0, 1)] == [1, 4]
    assert [m.id for m in story.foldable(lines, 1, 1)] == [4]
    assert story.format_line(lines[3]) == "Beta: hello"
    assert story.format_line(Message(7, "t", 7.0, "assistant", "x")) == f"{story.HER_FALLBACK}: x"


@pytest.mark.asyncio
async def test_a_long_backlog_is_folded_in_batches(manager, limits, model, keeper, monkeypatch):
    calls, _ = model
    monkeypatch.setattr(story, "MAX_BATCH_CHARS", 40)   # about two lines per call
    limits(summarize_every=2, keep_recent=2, max_chars=2400)
    thread = await _roleplay(manager, 4)   # 8 lines, 6 foldable
    assert await keeper.catch_up(thread.id, manager) == 6
    assert len(calls) == 3
    assert "Summary 2." in calls[2]["messages"][1]["content"]   # each call starts from the last summary
    assert (await manager.story(thread.id)).summary == "Summary 3."


# -- who has a story -----------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["temp", "chat"])
async def test_temp_chat_and_chat_threads_are_never_summarized(manager, limits, model, keeper, kind):
    """FR-MODE-5: Temp Chat keeps no story memory, and a chat thread has none."""
    calls, _ = model
    thread = await _roleplay(manager, 6, temp=kind == "temp", mode="roleplay" if kind == "temp" else "chat")
    assert await keeper.catch_up(thread.id, manager) == 0
    assert calls == [] and await manager.story(thread.id) is None


@pytest.mark.asyncio
async def test_a_failing_model_leaves_the_old_summary(manager, limits, model, keeper):
    """FR-MODE-5: an unreachable model, or an empty answer, writes nothing."""
    calls, state = model
    thread = await _roleplay(manager, 3)
    await keeper.catch_up(thread.id, manager)
    before = await manager.story(thread.id)
    for n in (4, 5):
        await manager.record_exchange(thread.id, f"line {n}", f"reply {n}", speaker=ALPHA)
    state["fail"] = llm.LLMUnreachableError("down")
    assert await keeper.catch_up(thread.id, manager) == 0
    state["fail"], state["replies"] = None, ["   "]
    assert await keeper.catch_up(thread.id, manager) == 0
    assert await manager.story(thread.id) == before and len(calls) == 3


@pytest.mark.asyncio
async def test_nothing_runs_while_the_model_is_busy_or_when_story_memory_is_off(manager, limits, model):
    calls, _ = model
    thread = await _roleplay(manager, 4)
    busy = story.StoryKeeper(is_busy=lambda: True)
    assert await busy.catch_up(thread.id, manager) == 0
    limits(summarize_every=0, keep_recent=2, max_chars=2400)
    idle = story.StoryKeeper(is_busy=lambda: False)
    assert idle.schedule(thread.id, manager) is None
    assert await idle.catch_up(thread.id, manager) == 0
    assert calls == []


def test_the_default_busy_signal_is_the_arbiter_like_the_memory_writer(monkeypatch):
    keeper = story.StoryKeeper()
    monkeypatch.setattr(arbiter.ARBITER, "state", arbiter.IDLE)
    assert keeper._is_busy() is False
    for state in (arbiter.LISTENING, arbiter.THINKING, arbiter.SPEAKING):
        monkeypatch.setattr(arbiter.ARBITER, "state", state)
        assert keeper._is_busy() is True


def test_a_chat_model_load_in_progress_counts_as_busy(monkeypatch):
    """D-065, D-072: a fold beside a chat-model load would load a second local model."""
    keeper = story.StoryKeeper()
    monkeypatch.setattr(arbiter.ARBITER, "state", arbiter.IDLE)
    monkeypatch.setattr(model_loader.LOADER, "busy", lambda: True)
    assert keeper._is_busy() is True


@pytest.mark.asyncio
async def test_the_kernels_keeper_waits_for_boots_chat_model_step(manager, limits, model, monkeypatch):
    """D-060: a roleplay opened at start-up that is behind does not fold beside the
    chat-model load; it folds once boot's chat-model step is over."""
    calls, _ = model
    monkeypatch.setattr(boot, "_chat_model_settled", None)
    keeper = story.StoryKeeper(is_busy=lambda: False, ready=story._after_boot)
    thread = await _roleplay(manager, 3)
    task = keeper.schedule(thread.id, manager)
    await asyncio.sleep(0.05)
    assert calls == [] and not task.done()
    boot.chat_model_settled_event().set()
    await asyncio.wait_for(task, 2)
    assert len(calls) == 1 and (await manager.story(thread.id)).summary == "Summary 1."


def test_the_running_kernels_keeper_is_gated_on_boot():
    """conftest swaps story.KEEPER per test; a fresh copy of the module shows the real one."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("story_fresh_copy", story.__file__)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    assert fresh.KEEPER._ready is fresh._after_boot


def test_the_story_config_has_the_agreed_defaults():
    assert StoryConfig() == StoryConfig(summarize_every=12, keep_recent=4, max_chars=2400)
    assert CONFIG.story.summarize_every >= 0


# -- the cap -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_long_summary_is_cut_at_a_sentence_end(manager, limits, model, keeper):
    calls, state = model
    limits(summarize_every=4, keep_recent=2, max_chars=60)
    state["replies"] = ["Sam met Alpha. They argued about the map. Then the storm came and it rained for days."]
    thread = await _roleplay(manager, 3)
    await keeper.catch_up(thread.id, manager)
    assert (await manager.story(thread.id)).summary == "Sam met Alpha. They argued about the map."
    assert "at most 40 words" in calls[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_the_fold_asks_for_room_for_a_whole_summary(manager, limits, model, keeper):
    """A local call otherwise stops at llm.max_tokens (512), below a summary near
    max_chars (400 words): the newest scenes would be cut off while
    through_message_id moved past them. The fold asks for its own cap."""
    calls, _ = model
    thread = await _roleplay(manager, 3)
    await keeper.catch_up(thread.id, manager)
    cap = calls[0]["kwargs"]["max_tokens"]
    assert cap == story.tokens_for(2400) and cap > llm.CONFIG.llm.max_tokens
    assert cap >= story.words_for(2400) * 2      # 400 words fit with room to spare
    assert story.tokens_for(60) >= story.words_for(60) * 2   # the 40-word floor too


def test_cut_keeps_a_closing_quote_and_falls_back_to_a_word():
    assert story.cut('She said "Go." Then she left the room quietly.', 20) == 'She said "Go."'
    assert story.cut("no sentence end here at all", 12) == "no sentence"
    assert story.cut("  short.  ", 100) == "short."


# -- one at a time, never raising, cancelled by a turn --------------------------------


@pytest.mark.asyncio
async def test_one_pass_per_thread_a_turn_preempts_it_and_nothing_is_written(manager, limits, monkeypatch, keeper):
    started, release = asyncio.Event(), asyncio.Event()

    async def slow(role, messages, **kwargs):
        started.set()
        await release.wait()
        yield "never saved."

    monkeypatch.setattr(router, "stream_text", slow)
    thread = await _roleplay(manager, 3)
    first = keeper.schedule(thread.id, manager)
    assert keeper.schedule(thread.id, manager) is first        # one at a time per thread
    await asyncio.wait_for(started.wait(), 2)
    keeper.preempt()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert keeper.running(thread.id) is None
    assert await manager.story(thread.id) is None


@pytest.mark.asyncio
async def test_a_background_failure_is_logged_and_never_raised(manager, limits, keeper, monkeypatch, caplog):
    async def broken(thread_id):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(manager, "story", broken)
    thread = await _roleplay(manager, 3)
    task = keeper.schedule(thread.id, manager)
    await task   # does not raise
    assert "disk on fire" in caplog.text


@pytest.mark.asyncio
async def test_listeners_hear_each_new_summary(manager, limits, model, keeper):
    heard = []
    unsubscribe = keeper.subscribe(lambda thread_id, summary: heard.append((thread_id, summary)))
    thread = await _roleplay(manager, 3)
    await keeper.catch_up(thread.id, manager)
    unsubscribe()
    for n in (4, 5):
        await manager.record_exchange(thread.id, f"line {n}", f"reply {n}", speaker=ALPHA)
    await keeper.catch_up(thread.id, manager)
    assert heard == [(thread.id, "Summary 1.")]


# -- over the real socket: after an exchange, on opening, and into the next turn --------


def _wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def story_kernel(monkeypatch, limits, model):
    """With test_conversation's `kernel`: a story keeper that may run, and the fake model."""
    monkeypatch.setattr(story, "KEEPER", story.StoryKeeper(is_busy=lambda: False))
    return model


def test_the_summary_is_written_after_exchanges_and_reaches_the_next_turn(kernel, story_kernel, monkeypatch):
    """FR-MODE-5 over the socket: after a roleplay exchange is saved the summary is
    written in the background, and the next turn's ephemeral note carries it."""
    calls, state = story_kernel
    state["replies"] = ["Sam asked Alpha to wait at the station."]
    notes = []

    async def recording(role, messages, offered, **kwargs):
        notes.append(" ".join(m["content"] for m in messages[1:] if m["role"] == "system"))
        yield {"type": "content", "text": "Mm. [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", recording)
    with kernel.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        thread = _new_roleplay(ws)
        _chat(ws, "Wait for me.")
        _chat(ws, "I mean it.")
        _chat(ws, "Ready?")   # 6 lines: the first 4 wait; summarize_every=4
        store = conversation.get_manager().store
        assert _wait_for(lambda: store.get_story(thread["id"]) is not None)
        assert _wait_for(lambda: story.KEEPER.running(thread["id"]) is None)
        _chat(ws, "Let's go.")
    note = prompting.STORY_NOTE.format(summary="Sam asked Alpha to wait at the station.")
    assert note not in notes[0] and note in notes[-1]
    assert calls and all(c["role"] == "memory_writer" for c in calls)


def test_opening_a_roleplay_thread_that_is_behind_catches_it_up(kernel, story_kernel, monkeypatch):
    """FR-MODE-5: a roleplay thread opened with lines waiting is summarized in the
    background; a Temp Chat roleplay is not, and its turns get no story note."""
    calls, state = story_kernel
    state["replies"] = ["They crossed the bridge."]
    manager = conversation.get_manager()

    def roleplay(**kwargs):
        thread = manager.store.create_thread(mode="roleplay", active_waifu_id="alpha", **kwargs)
        for n in range(1, 4):
            manager.store.add_message(thread.id, "user", f"line {n}")
            manager.store.add_message(thread.id, "assistant", f"reply {n}", speaker_name="Alpha")
        return thread

    temp = roleplay(temp=True)
    manager.store.set_story(temp.id, "An old summary.", 0)
    behind = roleplay()
    manager.store.set_kv(conversation.LAST_THREAD_KEY, behind.id)
    notes = []

    async def recording(role, messages, offered, **kwargs):
        notes.append(" ".join(m["content"] for m in messages[1:] if m["role"] == "system"))
        yield {"type": "content", "text": "Mm. [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", recording)
    with kernel.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        assert opened["data"]["thread"]["id"] == behind.id
        assert _wait_for(lambda: manager.store.get_story(behind.id) is not None)
        assert _wait_for(lambda: story.KEEPER.running(behind.id) is None)
        before = len(calls)
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": temp.id}})
        _until(ws, "thread_opened")
        _chat(ws, "Hello?")
    assert manager.store.get_story(behind.id).summary == "They crossed the bridge."
    assert len(calls) == before == 1 and manager.store.get_story(temp.id).summary == "An old summary."
    assert "An old summary." not in notes[-1]


def test_a_summary_reaching_a_rewound_message_is_not_written(tmp_path):
    # audit: a fold finishing after a Rewind must not bring the deleted scenes back.
    store = ThreadStore(tmp_path / "threads.db")
    thread = store.create_thread(mode="roleplay")
    store.add_message(thread.id, "user", "kept")
    assert store.set_story(thread.id, "Scenes that were rewound.", 99) is False
    assert store.get_story(thread.id) is None
