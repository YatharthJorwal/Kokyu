"""A turn in each conversation mode (K1c-03, K1c-07; FR-MODE-3, 4, 8, 9; D-074).

Roleplay turns read only the profile card, run no forget, look intent or Task Guide,
offer no tools and never reach transcript_log; a tool the turn did not offer is
refused; the delivery note is added only while voice is on; the reply is kept as the
raw text the model wrote; screen companions stay quiet in a roleplay thread.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import ambient
import hub
import prompting
import router
import tools
import turns
from audio import tts
from memory import embeddings, forget, recall, store
from senses import look_intent, ocr_watch, task_guide
from session import Session
from waifu_fixtures import make_pack
from waifus import WaifuRegistry

API = "api:airouter/deepseek/deepseek-v4-flash"
LOCAL = "local:ollama/qwen3.5:4b"


class Socket:
    def __init__(self, waifu):
        self.state = SimpleNamespace(waifu=waifu)
        self.sent: list[dict] = []

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.fixture
def waifu(tmp_path):
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha")
    return WaifuRegistry(premade, tmp_path / "user").get("alpha")


@pytest.fixture
def side_effects(monkeypatch):
    """Records every memory and sensing side effect a turn may have; voice off."""
    seen: dict[str, list] = {"forget": [], "task": [], "mark": [], "look": [], "recall": [], "log": []}

    async def fake_forget(text):
        seen["forget"].append(text)
        return None

    async def fake_task(text):
        seen["task"].append(text)
        return None

    async def fake_look(text, websocket):
        seen["look"].append(text)
        return None

    async def fake_recall(text, top_k=5, **_k):
        seen["recall"].append(text)
        return None

    async def fake_log(user_text, assistant_text, temp=False, speaker=None):
        seen["log"].append((user_text, assistant_text, temp))
        return 41

    async def silent(text, voice=None):
        return b""

    monkeypatch.setattr(forget, "maybe_forget", fake_forget)
    monkeypatch.setattr(task_guide, "maybe_update_task", fake_task)
    monkeypatch.setattr(task_guide, "enabled", lambda: True)
    monkeypatch.setattr(task_guide, "mark_interaction", lambda: seen["mark"].append(True))
    monkeypatch.setattr(look_intent, "maybe_look", fake_look)
    monkeypatch.setattr(recall, "build_recall_context", fake_recall)
    monkeypatch.setattr(turns, "log_transcript_turn", fake_log)
    monkeypatch.setattr(tts, "synthesize", silent)
    return seen


def _model(monkeypatch, *events_per_call):
    """A fake chat model: each call yields the next list of events, and is recorded."""
    calls = []
    script = iter(events_per_call)

    async def fake_stream(role, messages, offered, **kwargs):
        calls.append({"role": role, "messages": [dict(m) for m in messages], "tools": list(offered)})
        for event in next(script):
            yield event

    monkeypatch.setattr(router, "stream_with_tools", fake_stream)
    return calls


def _notes(call) -> str:
    """The turn's ephemeral system note(s): every system message after history[0]."""
    return " ".join(m["content"] for m in call["messages"][1:] if m["role"] == "system")


def _text(text):
    return {"type": "content", "text": text}


# -- FR-MODE-4: what a roleplay turn does not do ----------------------------------


@pytest.mark.asyncio
async def test_a_roleplay_turn_runs_no_forget_look_or_task_guide_and_offers_no_tools(waifu, side_effects, monkeypatch):
    calls = _model(monkeypatch, [_text("*She smiles.* Hello. [happy]")])
    history = [{"role": "system", "content": "sys"}]
    monkeypatch.setattr(recall, "build_profile_context", _profile("Name: Sam."))
    await turns.run_turn(Socket(waifu), history, "Forget that, and look at me.", False, [], mode="roleplay")
    assert side_effects["forget"] == [] and side_effects["task"] == [] and side_effects["mark"] == []
    assert side_effects["look"] == [] and side_effects["recall"] == []
    assert calls[0]["tools"] == [] and calls[0]["role"] == "chat"   # same router role in both modes
    assert side_effects["log"] == []                                 # never written to transcript_log


@pytest.mark.asyncio
async def test_a_chat_turn_still_does_all_of_it(waifu, side_effects, monkeypatch):
    # FR-MODE-3: Chat reads and writes app memory and offers tools as before.
    calls = _model(monkeypatch, [_text("Sure. [happy]")])
    history = [{"role": "system", "content": "sys"}]
    await turns.run_turn(Socket(waifu), history, "Forget that.", False, [], model_ref=LOCAL)
    assert side_effects["forget"] and side_effects["task"] and side_effects["mark"]
    assert side_effects["look"] and side_effects["recall"]
    assert calls[0]["tools"] and side_effects["log"] == [("Forget that.", "Sure.", False)]


def _profile(card):
    async def fake(framing, **_k):
        return framing.format(card=card)

    return fake


@pytest.mark.asyncio
async def test_roleplay_recall_is_the_profile_card_framed_as_the_real_person(memory_db, waifu, side_effects, monkeypatch):
    # FR-MODE-4: the card only (no facts, no episodes, no embedder call), framed as
    # the real person and not their role in the story.
    store.set_profile_card("Sam, a programmer in Delhi.")
    store.add_fact("uses an RTX 3060")

    async def no_embedder(text):
        raise AssertionError("a roleplay turn must not embed the user's line")

    monkeypatch.setattr(recall, "embed", no_embedder)
    monkeypatch.setattr(embeddings, "embed", no_embedder)
    calls = _model(monkeypatch, [_text("*She nods.* [neutral]")])
    await turns.run_turn(Socket(waifu), [{"role": "system", "content": "sys"}], "my GPU?", False, [], mode="roleplay")
    note = _notes(calls[0])
    assert note == prompting.ROLEPLAY_PROFILE_FRAMING.format(card="Sam, a programmer in Delhi.")
    assert "RTX 3060" not in note and recall.PREAMBLE.strip() not in note
    audit = json.loads(store.get_events("recall")[0]["detail"])          # audited like any recall
    assert audit["card"] is True and audit["path"] == "card" and audit["fact_ids"] == []


@pytest.mark.asyncio
async def test_build_profile_context_is_none_without_a_card_or_a_database(memory_db, monkeypatch):
    assert await recall.build_profile_context(prompting.ROLEPLAY_PROFILE_FRAMING) is None

    def unavailable():
        raise recall.MemoryUnavailableError("locked")

    monkeypatch.setattr(store, "get_profile_card", unavailable)
    assert await recall.build_profile_context(prompting.ROLEPLAY_PROFILE_FRAMING) is None


@pytest.mark.asyncio
async def test_temp_chat_in_a_roleplay_reads_nothing_not_even_the_card(waifu, side_effects, monkeypatch):
    # D-074: Temp Chat in a roleplay thread drops the profile card too.
    read = []

    async def card(framing, **_k):
        read.append(framing)
        return "About the real person: Sam."

    monkeypatch.setattr(recall, "build_profile_context", card)
    calls = _model(monkeypatch, [_text("*She waits.* [neutral]")])
    await turns.run_turn(Socket(waifu), [{"role": "system", "content": "sys"}], "Hi", True, [], mode="roleplay")
    assert read == [] and _notes(calls[0]) == ""


@pytest.mark.asyncio
async def test_an_unknown_mode_is_refused_before_anything_happens(waifu, side_effects):
    history = [{"role": "system", "content": "sys"}]
    with pytest.raises(ValueError):
        await turns.run_turn(Socket(waifu), history, "Hi", True, [], mode="poetry")
    assert history == [{"role": "system", "content": "sys"}]


# -- D-074: a tool the turn did not offer never runs ------------------------------


@pytest.mark.asyncio
async def test_a_roleplay_tool_call_is_refused_and_the_tool_never_runs(waifu, side_effects, monkeypatch):
    ran = []

    async def capture(**_k):
        ran.append(True)
        return "a desk"

    monkeypatch.setitem(tools._HANDLERS, "capture_screen", capture)
    calls = _model(
        monkeypatch,
        [{"type": "tool_calls", "calls": [{"name": "capture_screen", "arguments": {}}]}],
        [_text("*She shrugs.* [neutral]")],
    )
    await turns.run_turn(Socket(waifu), [{"role": "system", "content": "sys"}], "Look!", True, [], mode="roleplay")
    assert ran == []
    assert calls[1]["messages"][-1] == {"role": "tool", "content": tools.NOT_OFFERED_RESULT}


@pytest.mark.asyncio
async def test_an_api_model_cannot_run_a_local_only_tool_it_was_not_offered(waifu, side_effects, monkeypatch):
    # FR-R-7: the same hole closed for API models (screen, camera, clipboard are local-only).
    ran = []

    async def clipboard(**_k):
        ran.append(True)
        return "secret"

    monkeypatch.setitem(tools._HANDLERS, "read_clipboard", clipboard)
    calls = _model(
        monkeypatch,
        [{"type": "tool_calls", "calls": [{"name": "read_clipboard", "arguments": {}}]}],
        [_text("Okay. [neutral]")],
    )
    await turns.run_turn(Socket(waifu), [{"role": "system", "content": "sys"}], "paste?", True, [], model_ref=API)
    assert "read_clipboard" not in {s["function"]["name"] for s in calls[0]["tools"]}
    assert ran == [] and calls[1]["messages"][-1]["content"] == tools.NOT_OFFERED_RESULT


# -- D-097: Read aloud never changes what she writes --------------------------------


@pytest.mark.parametrize("mode", ["chat", "roleplay"])
@pytest.mark.asyncio
async def test_read_aloud_adds_no_note_and_the_turn_returns_the_reply_to_speak(waifu, side_effects, monkeypatch, read_aloud_on, mode):
    calls = _model(monkeypatch, [_text("Hi there. [happy]")])
    history = [{"role": "system", "content": "sys"}]
    reply = await turns.run_turn(Socket(waifu), history, "one", True, [], mode=mode)
    assert _notes(calls[0]) == ""                                       # the prompt is the same as with it off
    assert reply == "Hi there." == history[-1]["content"]               # what the session reads aloud


# -- FR-MODE-5 (K1c-04): the story summary joins a roleplay turn's ephemeral note ------


@pytest.mark.asyncio
async def test_a_roleplay_turn_gets_the_story_note_after_the_profile(waifu, side_effects, monkeypatch, read_aloud_on):
    calls = _model(monkeypatch, [_text("*She nods.* [neutral]")])
    monkeypatch.setattr(recall, "build_profile_context", _profile("Sam."))
    history = [{"role": "system", "content": "sys"}]
    await turns.run_turn(Socket(waifu), history, "And then?", False, [], mode="roleplay", story="They met at dusk.")
    note = prompting.STORY_NOTE.format(summary="They met at dusk.")
    assert _notes(calls[0]) == " ".join([prompting.ROLEPLAY_PROFILE_FRAMING.format(card="Sam."), note])
    assert calls[0]["messages"][0]["content"] == "sys"                 # never in history[0]
    assert all(note not in m["content"] for m in history)              # nor kept in history


@pytest.mark.parametrize(("mode", "temp"), [("chat", False), ("roleplay", True)])
@pytest.mark.asyncio
async def test_no_story_note_in_chat_or_temp_chat(waifu, side_effects, monkeypatch, mode, temp):
    # D-074: Temp Chat in a roleplay drops the story memory; a chat thread has none.
    calls = _model(monkeypatch, [_text("Hi. [happy]")])
    monkeypatch.setattr(recall, "build_profile_context", _profile("Sam."))
    await turns.run_turn(Socket(waifu), [{"role": "system", "content": "sys"}], "Hi", temp, [], mode=mode, story="Old.")
    assert "Old." not in _notes(calls[0])


@pytest.mark.asyncio
async def test_a_turn_preempts_a_running_story_summary(waifu, side_effects, monkeypatch):
    # FR-MODE-5: like the memory writer's timer pass, a story summary never holds the
    # model while she replies.
    import story

    started = asyncio.Event()

    async def slow_summary(thread_id, manager=None):
        started.set()
        await asyncio.Event().wait()

    keeper = story.StoryKeeper(is_busy=lambda: False)
    monkeypatch.setattr(keeper, "catch_up", slow_summary)
    monkeypatch.setattr(story, "KEEPER", keeper)
    monkeypatch.setattr(story, "limits", lambda: (12, 4, 2400))
    running = keeper.schedule("t1", manager=object())
    await asyncio.wait_for(started.wait(), 2)
    _model(monkeypatch, [_text("*She smiles.* [happy]")])
    await turns.run_turn(Socket(waifu), [{"role": "system", "content": "sys"}], "Hi", False, [], mode="roleplay")
    await asyncio.gather(running, return_exceptions=True)
    assert running.cancelled()


# -- D-074: the raw reply text is what is kept and shown ---------------------------


@pytest.mark.asyncio
async def test_markdown_and_paragraphs_survive_into_history_the_saved_reply_and_turn_done(waifu, side_effects, monkeypatch):
    pieces = ["Here are the steps:\n\n1. Open the settings window first.\n", "2. Click **Save** and wait a moment.\n\n",
              "```\nnpm run check\n```\n\n*She grins.* Done. [happy]"]
    _model(monkeypatch, [_text(p) for p in pieces])
    saved = []

    async def on_finished(user_text, reply, stopped, meta):
        saved.append((reply, meta))

    ws = Socket(waifu)
    history = [{"role": "system", "content": "sys"}]
    await turns.run_turn(ws, history, "How?", True, [], on_finished=on_finished, mode="roleplay")
    expected = "".join(pieces).removesuffix(" [happy]")
    assert "\n\n1. Open" in expected and expected.endswith("Done.")
    assert history[-1] == {"role": "assistant", "content": expected}
    assert saved[0][0] == expected and "log_id" not in saved[0][1]     # a roleplay turn has no transcript row
    done = ws.sent[-1]
    assert done["type"] == "turn_done" and done["data"]["text"] == expected and done["data"]["emotion"] == "happy"


@pytest.mark.asyncio
async def test_a_simple_chat_reply_is_unchanged(waifu, side_effects, monkeypatch):
    _model(monkeypatch, [_text("It was fine. "), _text("How about yours? [happy]")])
    ws = Socket(waifu)
    history = [{"role": "system", "content": "sys"}]
    await turns.run_turn(ws, history, "Day?", True, [])
    assert history[-1]["content"] == "It was fine. How about yours?" == ws.sent[-1]["data"]["text"]


# -- FR-MODE-8 (K1c-05, D-097): read aloud, a roleplay speaks only her dialogue ------


def _speak_texts(ws) -> list[str]:
    return [f["data"]["text"] for f in ws.sent if f["type"] == "speak"]


async def _turn_then_read_aloud(ws, history, user_text, mode="chat", **kwargs):
    """A turn, then what the session does with Read aloud on: speak the finished reply."""
    reply = await turns.run_turn(ws, history, user_text, True, [], mode=mode, **kwargs)
    assert not _speak_texts(ws)   # nothing is spoken while the reply is written
    await turns.speak_reply(ws, reply, mode, None)
    return reply


@pytest.mark.asyncio
async def test_a_roleplay_speaks_only_her_dialogue_but_keeps_the_whole_reply(waifu, side_effects, monkeypatch, read_aloud_on):
    # The deltas split an action, a "**" and an "(OOC" mid-token on purpose.
    pieces = ["*She looks up from her book, then sets it down. She smi", "les.*\n\n",
              "\"Oh, it is you. I was **wait", "ing** for you all afternoon,\" she says.",
              " *She stands.* (O", "OC: short reply, sorry) \"Come in, then.\" [happy]"]
    calls = _model(monkeypatch, [_text(p) for p in pieces])
    spoken: list[str] = []

    async def fake_synth(websocket, text, voice=None):
        spoken.append(text)
        return b""

    monkeypatch.setattr(turns, "synthesize_for", fake_synth)
    saved = []

    async def on_finished(user_text, reply, stopped, meta):
        saved.append(reply)

    ws = Socket(waifu)
    history = [{"role": "system", "content": "sys"}]
    await _turn_then_read_aloud(ws, history, "Hi.", "roleplay", on_finished=on_finished)
    captions = " ".join(_speak_texts(ws))
    assert captions == "Oh, it is you. I was waiting for you all afternoon, Come in, then."
    for gone in ("*", "smiles", "She", "says", "OOC", "sorry", "[happy]", "\""):
        assert gone not in captions and all(gone not in s for s in spoken), gone
    assert spoken   # the voice got the dialogue clauses
    # History, the saved reply and turn_done keep the full formatted text (D-074).
    full = "".join(pieces).removesuffix(" [happy]")
    assert history[-1] == {"role": "assistant", "content": full} and saved == [full]
    done = next(f for f in ws.sent if f["type"] == "turn_done")
    assert done["data"]["text"] == full and done["data"]["emotion"] == "happy"
    # The model still saw nothing different: the router role is chat (FR-MODE-3).
    assert calls[0]["role"] == "chat"


@pytest.mark.asyncio
async def test_an_action_only_roleplay_reply_speaks_nothing_and_is_still_kept(waifu, side_effects, monkeypatch, read_aloud_on):
    _model(monkeypatch, [_text("*She just smiles and nods.* [teasing]")])
    ws = Socket(waifu)
    history = [{"role": "system", "content": "sys"}]
    await _turn_then_read_aloud(ws, history, "Well?", "roleplay")
    assert _speak_texts(ws) == []
    assert not [f for f in ws.sent if f["type"] == "error"]
    assert ws.sent[-1]["data"]["text"] == "*She just smiles and nods.*" and ws.sent[-1]["data"]["emotion"] == "teasing"


@pytest.mark.asyncio
async def test_a_chat_turn_speaks_actions_words_as_before(waifu, side_effects, monkeypatch, read_aloud_on):
    # The dialogue cut is roleplay-only: in a chat the markers go and the words stay.
    _model(monkeypatch, [_text("*grins* Sure, that works for me. \"Quoted\" too. [happy]")])
    ws = Socket(waifu)
    await _turn_then_read_aloud(ws, [{"role": "system", "content": "sys"}], "Ok?")
    captions = " ".join(_speak_texts(ws))
    assert "grins" in captions and "Quoted" in captions and "[happy]" not in captions


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["chat", "roleplay"])
async def test_a_tag_after_a_short_last_sentence_is_never_spoken_and_sets_the_emotion(waifu, side_effects, monkeypatch, read_aloud_on, mode):
    # The chunker used to emit "... now. [happy]." mid-stream as one ready chunk.
    _model(monkeypatch, [_text("Sure thing, I can definitely do it now."), _text(" [happy]"), _text(".")])
    ws = Socket(waifu)
    history = [{"role": "system", "content": "sys"}]
    await _turn_then_read_aloud(ws, history, "Can you?", mode)
    assert _speak_texts(ws) == ["Sure thing, I can definitely do it now."]
    assert history[-1]["content"] == "Sure thing, I can definitely do it now."
    assert next(f for f in ws.sent if f["type"] == "turn_done")["data"]["emotion"] == "happy"


@pytest.mark.asyncio
async def test_a_reply_that_is_only_an_emotion_tag_is_still_an_empty_reply(waifu, side_effects, monkeypatch):
    _model(monkeypatch, [_text("  [happy]")])
    ws = Socket(waifu)
    history = [{"role": "system", "content": "sys"}]
    await turns.run_turn(ws, history, "Hm?", True, [])
    assert [f["data"]["reason"] for f in ws.sent if f["type"] == "error"] == ["EMPTY_REPLY"]
    assert history == [{"role": "system", "content": "sys"}] and ws.sent[-1]["data"]["text"] == ""


def test_reply_text_strips_only_the_trailing_tag_and_the_ends():
    assert turns.reply_text("  *She waves.*\n\nHi! [happy].  ") == "*She waves.*\n\nHi!"
    assert turns.reply_text("[sad] is a tag mid-text, not at the end") == "[sad] is a tag mid-text, not at the end"


# -- FR-MODE-9: screen companions stay quiet in a roleplay thread ------------------


def _bare_session(mode):
    session = Session.__new__(Session)
    session.ws = object()
    session.thread = SimpleNamespace(id="t1", mode=mode, scenario={})
    session.turn = None
    session.ambient_lock = asyncio.Lock()
    session.history, session.temp, session.temp_flags, session.unprompted = [], False, [], []
    return session


async def _spin(loop_coro):
    task = asyncio.create_task(loop_coro)
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize(("mode", "speaks"), [("chat", True), ("roleplay", False)])
@pytest.mark.asyncio
async def test_task_guide_never_remarks_in_a_roleplay_thread(monkeypatch, mode, speaks):
    checks = []

    async def check(*_a, **_k):
        checks.append(True)

    monkeypatch.setattr(ambient, "TASK_GUIDE_POLL_SECONDS", 0)
    monkeypatch.setattr(ambient, "run_task_guide_check", check)
    monkeypatch.setattr(task_guide, "get_state", lambda: SimpleNamespace(active=True, description="fix the build"))
    monkeypatch.setattr(task_guide, "enabled", lambda: True)
    monkeypatch.setattr(task_guide, "is_idle", lambda *_a: False)
    monkeypatch.setattr(task_guide, "due_for_check", lambda *_a: True)
    monkeypatch.setattr(hub, "drives", lambda ws: True)
    await _spin(_bare_session(mode)._task_guide_loop())
    assert bool(checks) is speaks


@pytest.mark.parametrize(("mode", "speaks"), [("chat", True), ("roleplay", False)])
@pytest.mark.asyncio
async def test_ocr_watch_never_remarks_in_a_roleplay_thread(monkeypatch, mode, speaks):
    checks = []

    async def check(*_a, **_k):
        checks.append(True)

    monkeypatch.setattr(ambient, "OCR_WATCH_POLL_SECONDS", 0)
    monkeypatch.setattr(ambient, "run_ocr_watch_check", check)
    monkeypatch.setattr(ambient, "typing_recently", lambda: False)
    monkeypatch.setattr(ocr_watch, "get_state", lambda: SimpleNamespace(active=True))
    monkeypatch.setattr(ocr_watch, "due_for_check", lambda *_a: True)
    monkeypatch.setattr(task_guide, "get_state", lambda: SimpleNamespace(active=False, description=""))
    monkeypatch.setattr(hub, "drives", lambda ws: True)
    await _spin(_bare_session(mode)._ocr_watch_loop())
    assert bool(checks) is speaks


@pytest.mark.asyncio
async def test_a_screen_check_in_flight_never_lands_in_a_roleplay_opened_meanwhile(monkeypatch):
    # FR-MODE-9 (review finding): the loop's guard runs before the check; the user
    # opens a roleplay while the check is still running (_change_thread does not wait).
    seen = {}

    async def check(*_a, still_valid, on_remark, **_k):
        session.thread = SimpleNamespace(id="story", mode="roleplay", scenario={})   # thread_open meanwhile
        seen["valid"] = still_valid()
        await on_remark("You drifted off task.")

    saved = []

    async def save_remark(text):
        saved.append(text)

    monkeypatch.setattr(ambient, "TASK_GUIDE_POLL_SECONDS", 0)
    monkeypatch.setattr(ambient, "run_task_guide_check", check)
    monkeypatch.setattr(task_guide, "get_state", lambda: SimpleNamespace(active=True, description="fix the build"))
    monkeypatch.setattr(task_guide, "enabled", lambda: True)
    monkeypatch.setattr(task_guide, "is_idle", lambda *_a: False)
    monkeypatch.setattr(task_guide, "due_for_check", lambda *_a: True)
    monkeypatch.setattr(hub, "drives", lambda ws: True)
    session = _bare_session("chat")
    session.thread = SimpleNamespace(id="work", mode="chat", scenario={})
    session.save_remark = save_remark
    await _spin(session._task_guide_loop())
    assert seen["valid"] is False and saved == []


@pytest.mark.asyncio
async def test_a_screen_check_bound_to_another_chat_thread_is_dropped_too(monkeypatch):
    session = _bare_session("chat")
    session.thread = SimpleNamespace(id="work", mode="chat", scenario={})
    saved = []

    async def save_remark(text):
        saved.append(text)

    session.save_remark = save_remark
    hooks = session._ambient_hooks()
    assert hooks["still_valid"]() is True
    await hooks["on_remark"]("kept")
    session.thread = SimpleNamespace(id="other", mode="chat", scenario={})
    assert hooks["still_valid"]() is False
    await hooks["on_remark"]("dropped")
    assert saved == ["kept"]


def test_reply_text_drops_an_unclosed_tag_only_when_stopped():
    assert turns.reply_text("Sure, right now. [hap", stopped=True) == "Sure, right now."
    assert turns.reply_text("Sure, right now. [", stopped=True) == "Sure, right now."
    assert turns.reply_text("Sure. [happy]", stopped=True) == "Sure."
    assert turns.reply_text("Sure, right now. [hap") == "Sure, right now. [hap"   # a finished reply is kept as written


@pytest.mark.asyncio
async def test_stop_inside_the_trailing_tag_keeps_no_tag_fragment(waifu, side_effects, monkeypatch):
    # D-074 (review finding): Stop pressed while the model streams "[hap" must not
    # store or show the fragment.
    streamed = asyncio.Event()

    async def fake_stream(role, messages, offered, **kwargs):
        yield _text("Sure, I can help with that right now. [hap")
        streamed.set()
        await asyncio.Event().wait()   # the rest of the tag never arrives: Stop

    monkeypatch.setattr(router, "stream_with_tools", fake_stream)
    finished = []

    async def on_finished(user_text, text, stopped, meta):
        finished.append((text, stopped))

    socket, history = Socket(waifu), [{"role": "system", "content": "sys"}]
    task = asyncio.create_task(
        turns.run_turn(socket, history, "help?", False, [], on_finished=on_finished, model_ref=LOCAL)
    )
    await asyncio.wait_for(streamed.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    want = "Sure, I can help with that right now."
    assert history[-1] == {"role": "assistant", "content": want}
    assert finished == [(want, True)]
    done = [f for f in socket.sent if f.get("type") == "turn_done"]
    assert done and done[-1]["data"]["text"] == want and done[-1]["data"]["stopped"] is True
