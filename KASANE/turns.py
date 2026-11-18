"""One model turn: the user's line in, the reply streamed token by token (FR-C-2).
Tools run here, the exchange is logged for the memory writer, and a failure
becomes an error frame with Retry and Switch model (FR-R-5). With Read aloud on
(D-097), speak_reply says the finished reply afterwards. Also the pieces every
spoken path shares (send_speak) and the limits on what the model is sent
(fit_for_llm, trim_history).
"""

import asyncio
import base64
import contextlib
import logging
import re
import sys
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

from fastapi import WebSocket

import companions
import context_budget
import context_fit
import hub
import llm
import model_loader
import prompting
import protocol
import router
import story as story_memory
import tools
from audio import arbiter, latency, read_aloud, speech, speech_stream, tts
from config import CONFIG
from memory import forget, recall, store, writer
from memory.db import MemoryUnavailableError
from persona import apply_persona_pass, extract_emotion_tag
from router import listing as model_listing
from router import model_ref as model_refs
from senses import look_intent, task_guide

log = logging.getLogger(__name__)


# One recorder for the process; every turn appends one row.
LATENCY = latency.LatencyRecorder()


async def synthesize_for(websocket: Any, spoken: str, *, voice: Any = ..., once: bool = False) -> bytes:
    """Speak in the active waifu's voice, or in `voice` when given (a reply read
    aloud keeps the voice of the companion who wrote it). With Read aloud off
    (D-097) or a dead TTS backend this yields empty audio: the reply stays
    text-only (FR-V-7). `once`: a message read on request (D-099) speaks with Read
    aloud off."""
    if not (read_aloud.READ_ALOUD.on or once):
        return b""
    voice_params = companions.voice_of(websocket) if voice is ... else voice
    try:
        if voice_params is None:
            return await tts.synthesize(spoken)
        return await tts.synthesize(spoken, voice_params)
    except tts.TTSUnreachableError as exc:
        log.warning(f"voice backend unavailable, reply stays text-only: {exc}")
        return b""


# What the chat shows when a model call fails and the router has nothing more
# specific (FR-R-5). Plain words, the same for every companion.
LLM_UNREACHABLE_LINE = "Could not reach the model server. Is Ollama running?"


LLM_SERVER_ERROR_LINE = "The model server answered with an error. The details are in logs/kasane.log."


LLM_TIMEOUT_LINE = "The model took too long to answer; it may still be loading. Try again in a moment."


def llm_failure_line(exc: Exception) -> str:
    """The message for an LLM failure, by what actually went wrong."""
    if isinstance(exc, llm.LLMTimeoutError):
        return LLM_TIMEOUT_LINE
    if isinstance(exc, llm.LLMServerError):
        return LLM_SERVER_ERROR_LINE
    return LLM_UNREACHABLE_LINE


def failure_frame(exc: Exception, thread_id: str | None) -> dict[str, Any]:
    """The `error` frame for a failed turn: the router's typed failure when there is
    one, else a plain one. Either way the chat offers Retry and Switch model."""
    failure = protocol.model_failure(exc) or {
        "code": "model_failed",
        "reason": type(exc).__name__,
        "message": llm_failure_line(exc),
        "model_ref": None,
        "actions": ["retry", "switch_model"],
        "reply_to": None,
    }
    return protocol.frame("error", failure, thread=thread_id)


# Phase 4 -- how many rounds of "model calls a tool, gets a result, tries
# again" one turn allows before giving up. 3 is generous for the two
# tools that exist today (capture_screen, read_clipboard chained at most
# once or twice in a row is a realistic real request; anything beyond
# that is almost certainly a model stuck re-calling a tool rather than
# answering) and small enough to guarantee a turn can't hang forever on a
# local 9B model that won't stop. Said if that cap is actually hit --
# should be rare; **not verified** how often qwen3.5:9b actually needs
# this in practice, since real tool-calling behavior against this
# project's own Ollama instance hasn't been tested yet (see
# docs/DECISIONS.md).
MAX_TOOL_ROUNDS = 3


TOOL_STUCK_LINE = "The model kept calling tools and never answered. Try again."
EMPTY_REPLY_LINE = (
    "The model finished without saying anything. If it thinks first, it may have "
    "spent the whole reply thinking: lower the effort or raise llm.reasoning_tokens."
)


async def send_audio(websocket: WebSocket, display: str, audio_bytes: bytes) -> None:
    """One already-synthesized clause. `display` is what the caption shows;
    the audio may be a normalized version of it (see send_speak)."""
    await websocket.send_json(
        protocol.frame(
            "speak",
            {"text": display, "audio_b64": base64.b64encode(audio_bytes).decode("ascii"), "mime": "audio/wav"},
        )
    )


async def send_speak(websocket: WebSocket, text: str) -> None:
    """Speak one whole line: normalize it for the voice, keep the panel's
    wording. Every spoken path (a turn, an ambient remark, a fallback line)
    goes through here, so no em dash or quote ever reaches TTS regardless of
    what the model wrote."""
    prepared = speech.prepare(text)
    if not prepared.spoken:
        return
    await send_audio(websocket, prepared.display, await synthesize_for(websocket, prepared.spoken))


async def speak_reply(
    websocket: WebSocket, text: str, mode: str, voice: "tts.VoiceParams | None", *, ref: str | None = None
) -> None:
    """Read aloud (D-097): say one finished reply, in Chat and Roleplay. What is said
    is speech.speakable's cut (no code, tables, links or tags; her dialogue only in a
    roleplay), clause by clause, synthesizing one clause ahead, in `voice`: the
    voice of whoever wrote it, taken when the reply ended. Waits while the voice
    wakes up; the session cancels it when the user sends, stops or leaves the thread.
    Never raises: a reply that cannot be spoken stays text (FR-V-7).

    `ref`: one message read on request, its speaker button (D-099): it speaks with
    Read aloud off too, and `spoken {ref}` tells the window when it has all been sent."""
    once = ref is not None
    try:
        spoken = speech.speakable(text, mode)
        if spoken and await read_aloud.READ_ALOUD.ready(once=once):
            await _say(websocket, spoken, voice, once)
    finally:
        if once:
            read_aloud.READ_ALOUD.done_once()
            with contextlib.suppress(Exception):
                await websocket.send_json(protocol.frame("spoken", {"ref": ref}))


async def _say(websocket: WebSocket, spoken: str, voice: "tts.VoiceParams | None", once: bool) -> None:
    clauses = speech.split_segments(
        apply_persona_pass(spoken), CONFIG.speech.max_segment_chars, CONFIG.speech.min_segment_chars
    )
    stream = speech_stream.SpeechStream(
        send=lambda display, audio: send_audio(websocket, display, audio),
        synth=lambda clause: synthesize_for(websocket, clause, voice=voice, once=once),
        # already speakable: each clause goes out as it is
        prepare=lambda clause: speech.PreparedSpeech(display=clause, spoken=clause, segments=(clause,)),
        on_first_audio=arbiter.ARBITER.on_first_audio,
    )
    arbiter.ARBITER.on_turn_started()   # one mouth: ambient remarks and the memory writer wait
    try:
        for clause in clauses:
            await stream.push(clause)
        await stream.close()
    except Exception:  # noqa: BLE001 -- speech must never take the window down
        log.exception("read aloud failed; the reply stays text")
    finally:
        stream.abort()
        arbiter.ARBITER.on_turn_finished()


async def log_transcript_turn(user_text: str, assistant_text: str, temp: bool = False, speaker: str | None = None) -> int | None:
    """Best-effort -- a DB hiccup here shouldn't take down the turn itself
    (turn_done still needs to reach the frontend either way), same
    degrade-gracefully pattern recall.py/forget.py already use for the
    same underlying DB."""
    try:
        return await asyncio.to_thread(partial(store.add_transcript_turn, user_text, assistant_text, temp=temp, speaker=speaker))
    except MemoryUnavailableError as exc:
        log.warning(f"transcript log: write failed, skipping: {exc}")
        return None


def is_local_ref(model_ref: str | None) -> bool:
    """Whether the turn's model runs on this PC. Unreadable counts as not local:
    the safe side for anything that may only stay on the machine."""
    try:
        return model_refs.parse(model_listing.effective_ref(model_ref, CONFIG)).is_local
    except model_refs.ModelRefError:
        return False


async def drop_transcript_turn(row_id: int) -> None:
    try:
        await asyncio.to_thread(store.drop_transcript_turn, row_id)
    except MemoryUnavailableError as exc:
        log.warning(f"transcript log: could not drop the replaced turn: {exc}")


def fit_for_llm(
    messages: list[dict[str, Any]],
    tools_list: list[dict[str, Any]] | None = None,
    extra: list[dict[str, Any]] | None = None,
    num_ctx: int | None = ...,  # type: ignore[assignment]
) -> list[dict[str, Any]]:
    """The messages actually sent to the model: `messages` with the oldest
    history dropped (from this copy only) until prompt + reserved reply fit
    `num_ctx` (the model's Chat memory, D-098; llm.num_ctx when not given). See
    context_budget.py for why -- replies were being cut off with done_reason
    'length' because nothing bounded the prompt by size."""
    if num_ctx is ...:
        num_ctx = CONFIG.llm.num_ctx
    fitted, dropped, est_tokens, budget = context_budget.fit_messages(
        messages,
        num_ctx=num_ctx,
        reply_reserve=CONFIG.llm.max_tokens,
        tools=tools_list,
        extra=extra,
    )
    if dropped:
        log.info(
            f"context: left out the {dropped} oldest history message(s) this call "
            f"to fit num_ctx={num_ctx} (estimated prompt {est_tokens} tokens, "
            f"budget {budget}).",
        )
    if budget and est_tokens > budget:
        log.warning(
            f"the persona prompt + memory block alone (~{est_tokens} tokens) "
            f"exceed the prompt budget ({budget}) for num_ctx={num_ctx}; give the model "
            "more Chat memory in the picker.",
        )
    return fitted


def record_unprompted(
    history: list[dict[str, str]],
    text: str,
    temp_mode: bool,
    temp_turn_flags: list[bool] | None,
    unprompted: list[dict[str, str]] | None,
) -> None:
    """Appends one of her unprompted comments (a Task Guide chide or an OCR
    remark -- an assistant turn with no user turn before it) to history,
    keeps temp_turn_flags in lockstep, then caps how many such comments stay
    in history (session.max_unprompted_in_history). `unprompted` None =
    don't track or cap (direct callers/tests)."""
    message = {"role": "assistant", "content": text}
    history.append(message)
    if temp_turn_flags is not None:
        temp_turn_flags.append(temp_mode)
    if unprompted is not None:
        unprompted.append(message)
        context_budget.cap_unprompted(
            history, temp_turn_flags, unprompted, CONFIG.session.max_unprompted_in_history
        )
    trim_history(history, temp_turn_flags)


def trim_history(history: list[dict[str, str]], temp_turn_flags: list[bool] | None = None) -> None:
    """Keeps the system prompt plus the last N (user, assistant) turns.
    Session memory only (Phase 3 adds durable memory), but still needs a
    cap so a long session doesn't grow the LLM's context unbounded.

    temp_turn_flags, when given, is trimmed the same way and by the same
    amount -- it's kept in lockstep with history[1:] (see run_turn's own
    docstring), so whatever gets dropped from the front of `turns` here
    has to be dropped from its front too, or every flag after the cut
    would silently point at the wrong history entry."""
    system, turns = history[0], history[1:]
    max_messages = CONFIG.session.max_history_turns * 2
    if len(turns) > max_messages:
        turns = turns[-max_messages:]
        if temp_turn_flags is not None:
            temp_turn_flags[:] = temp_turn_flags[-max_messages:]
    history[:] = [system] + turns


_UNCLOSED_TAG = re.compile(r"\[\w*$")   # the text is already stripped; rstrip after


def reply_text(raw: str, stopped: bool = False) -> str:
    """The reply as it is kept and shown (D-074): the raw streamed text with the
    trailing emotion tag removed and the ends trimmed. Line breaks inside stay.
    `stopped`: Stop cut the stream, possibly inside the tag; a fragment like "[hap"
    is part of the tag, not of the reply, so it goes too."""
    text = extract_emotion_tag(raw)[0].strip()
    return _UNCLOSED_TAG.sub("", text).rstrip() if stopped else text


async def run_turn(
    websocket: WebSocket,
    history: list[dict[str, str]],
    user_text: str,
    temp_mode: bool = False,
    temp_turn_flags: list[bool] | None = None,
    on_finished: "Callable[[str, str, bool, dict[str, Any]], Awaitable[None]] | None" = None,
    thread_id: str | None = None,
    model_ref: str | None = None,
    effort: str | None = None,
    unprompted: list[dict[str, str]] | None = None,
    attachment: str | None = None,
    *,
    mode: str = "chat",
    story: str | None = None,
) -> str:
    """The actual agent turn: append user_text to history, stream the LLM
    reply, commit (or roll back) history. Returns the reply to read aloud
    (D-097): the finished reply, or "" when it failed, was stopped (Stop raises
    CancelledError instead) or said nothing. Typed and dictated lines are
    the same by the time this runs (dictation only fills the input box).

    Also writes one row to Phase 9's persistent transcript_log table
    (memory/store.py) per call, regardless of how the turn ends (normal
    completion, LLM-unreachable fallback, or stopped mid-sentence): the
    reply as it was kept, with the voice's spelling rules applied.

    temp_mode/temp_turn_flags (quick-action menu's Temp Chat toggle):
    temp_turn_flags is a list kept in lockstep with history[1:] (one
    entry per history.append(), True if temp_mode was active for that
    append) -- see Session.temp_flags (session.py) on why this is tracked
    per-turn rather than as a single per-session flag, and consolidation
    time (Session.saver) for where it actually gets used. None
    means "don't bother" (there's nowhere to track it, or this call site
    doesn't care) -- every real call site passes a real list.

    mode: the thread's conversation mode (FR-MODE-1, D-074), from the THREAD only.
    A roleplay turn reads only the profile card, runs no forget, Task Guide or look
    intent, offers no tools and is not written to transcript_log, so nothing from a
    story reaches app memory (FR-MODE-4). Read aloud says only her dialogue
    (speech.speakable, FR-MODE-8); history keeps the whole reply. The router role
    is "chat" in both modes.

    story: the thread's story summary (FR-MODE-5), passed by the session for a
    roleplay thread; it joins the turn's ephemeral note, never history[0]. Dropped
    in Temp Chat, like the profile card (D-074)."""
    if mode not in prompting.MODE_LAYERS:
        raise ValueError(f"unknown conversation mode: {mode!r}")
    roleplay = mode == "roleplay"
    history.append({"role": "user", "content": user_text})
    if temp_turn_flags is not None:
        temp_turn_flags.append(temp_mode)
    # K1-00b: the chat view streams the reply token by token (FR-C-2).
    local_model = is_local_ref(model_ref)
    # FR-R-7: an attached file or image may go to the chosen API model, with a badge saying so.
    # shortcut: badged before the router decides, so a blocked call is badged too (over-warns); fine until routing reports back.
    sent_to = model_listing.effective_ref(model_ref, CONFIG) if attachment and not local_model else None
    with contextlib.suppress(Exception):
        await websocket.send_json(
            protocol.frame("turn_start", {"user_text": user_text, "sent_to": sent_to, "file": bool(attachment)}, thread=thread_id)
        )
    timings = LATENCY.begin()
    arbiter.ARBITER.on_turn_started()
    writer.WRITER.preempt()  # a timer-driven memory pass must not hold the model during a reply
    story_memory.KEEPER.preempt()  # nor a story summary (FR-MODE-5)
    # Phase 4 Round 2: any real user turn counts as "they're still here,"
    # regardless of whether it's about the tracked task at all -- resets
    # Task Guide Mode's idle clock (see task_guide.is_idle/_task_guide_loop
    # below). A no-op if nothing's actually being tracked. Not in a roleplay
    # (FR-MODE-4): a story is not work on the tracked task.
    if not roleplay:
        task_guide.mark_interaction()
    # K1-10 (FR-M-6): the turn runs on the loaded model. A pending or running load
    # of it finishes first (at most chat.load_delay_s extra), so an Ollama turn never
    # starts while llama-server still holds the memory; with nothing loaded yet
    # (warm_up_on_start off) the first message is what loads it.
    pending_load = model_loader.LOADER.request(model_listing.effective_ref(model_ref, CONFIG))
    if pending_load is not None:
        await asyncio.wait({pending_load})

    # Phase 3: forget first, then recall -- so a fact just removed this
    # turn can't immediately resurface in the same turn's recall block.
    # Both are ephemeral system messages built fresh per turn, spliced
    # into the LLM call only -- never written into `history` itself (see
    # memory/recall.py's docstring for why: history is the real
    # conversation, and this would otherwise go stale, double up every
    # turn, and get fed back into the memory writer as if it were something
    # someone actually said). Falls back to plain `history` unchanged if
    # neither has anything to add -- a turn should never fail or even
    # look different structurally just because memory had nothing to do.
    # Skipped entirely in temp_mode -- Temp Chat's whole point is "read
    # nothing from persistent memory, write nothing to it," and
    # maybe_update_task counts here too even though task state isn't
    # SQLite-persisted: it's still a live, carry-forward side effect
    # (a task tracked from a "this doesn't count" conversation chiding
    # the user later in a normal one would defeat the point).
    if temp_mode:
        # Temp Chat reads nothing, in a roleplay too: not even the profile card (D-074).
        forget_hint = None
        task_hint = None
        memory_block = None
    elif roleplay:
        # FR-MODE-4: a "forget that" or a task said inside a story is fiction, so it
        # must not retire real facts or start a Task Guide task. Recall is the profile
        # card alone, framed as the real person and not their role in the story.
        forget_hint = None
        task_hint = None
        memory_block = await recall.build_profile_context(prompting.ROLEPLAY_PROFILE_FRAMING)
    else:
        forget_hint = await forget.maybe_forget(user_text)
        # Phase 4 Round 2 fix -- see task_guide.py's own comment on why this
        # is a dedicated classification call rather than left to the model's
        # own set_active_task tool call: real testing showed the latter
        # doesn't fire reliably for this model. Same ephemeral-hint treatment
        # as forget_hint right above.
        # FR-SC-1: only while the user has Task Guide on.
        task_hint = await task_guide.maybe_update_task(user_text) if task_guide.enabled() else None
        if task_hint:
            await hub.broadcast_screen_status()
        memory_block = await recall.build_recall_context(user_text, CONFIG.memory.recall_top_k)
    # Explicit "look at my screen / camera" requests, handled here in Python
    # instead of trusting the model to call capture_screen/capture_camera
    # itself -- see look_intent.py for the real-log evidence (2 of ~9
    # explicit requests actually fired the tool). Deliberately NOT gated on
    # temp_mode: this is live sensing that gets spliced in for this one
    # turn, not a read from or write to persistent memory. Never in a roleplay:
    # "look at me" in a story must not capture the camera (FR-MODE-4).
    look_hint = None if roleplay else await look_intent.maybe_look(user_text, websocket)
    # Read aloud never changes what she writes (D-097): speech.speakable cuts the
    # finished reply instead, so there is no spoken-delivery layer in the prompt.
    # FR-MODE-5: the story so far, for a roleplay only and never in Temp Chat (D-074).
    story_note = prompting.STORY_NOTE.format(summary=story) if story and roleplay and not temp_mode else None
    memory_parts = [part for part in (forget_hint, task_hint, look_hint, memory_block, story_note) if part]

    if memory_parts:
        combined = " ".join(memory_parts)
        messages_for_llm = history[:-1] + [{"role": "system", "content": combined}] + history[-1:]
    else:
        messages_for_llm = history

    # Everything the model wrote, untouched (D-074): history, the saved message and
    # turn_done use it, so Markdown and paragraph breaks survive the stream.
    raw_text = ""
    # The reply Read aloud may say, set only when the reply ended normally (D-097).
    to_speak = ""
    detected_emotion: str | None = None
    tool_messages: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}   # the reply round's token counts, where the backend reports them (FR-C-10)
    if unprompted and not local_model:
        # Her Task Guide and OCR remarks were written from screen captures: ambient
        # content an API model never sees (FR-SC-3, FR-R-7). `unprompted` holds them by identity.
        messages_for_llm = [m for m in messages_for_llm if not any(m is u for u in unprompted)]
    # FR-MODE-4: a roleplay offers no tools; the router role stays "chat" in both modes.
    offered_tools = [] if roleplay else tools.offered_schemas(already_looked=bool(look_hint), local_model=local_model)
    offered_names = {schema["function"]["name"] for schema in offered_tools}
    # D-098: the history budget follows this model's Chat memory, the same value its requests use.
    chat_memory = context_fit.context_for(model_listing.effective_ref(model_ref, CONFIG))
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            saw_tool_call = False
            # K1-00c (D-025): the conversation runs as the `chat` role on the
            # thread's chosen model and effort. A camera/screen capture this
            # turn is ambient content and may only go to a local model.
            async for event in router.stream_with_tools(
                "chat",
                fit_for_llm(messages_for_llm, offered_tools, tool_messages, num_ctx=chat_memory) + tool_messages,
                offered_tools,
                model_ref=model_ref,
                effort=effort,
                ambient=bool(look_hint),
            ):
                if event["type"] == "tool_calls":
                    saw_tool_call = True
                    # Dispatched and appended one at a time, in order --
                    # if the model asked for more than one tool in the
                    # same turn (untested whether qwen3.5:9b actually
                    # does this), each one's result needs to already be
                    # in tool_messages before the next round re-calls the
                    # model, same as a real multi-tool exchange would.
                    for call in event["calls"]:
                        result_text = await tools.dispatch_tool_call(
                            call["name"], call["arguments"], websocket=websocket, offered=offered_names
                        )
                        tool_messages.append(
                            {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": call["name"],
                                            "arguments": call["arguments"],
                                        }
                                    }
                                ],
                            }
                        )
                        tool_messages.append({"role": "tool", "content": result_text})
                    if raw_text and not raw_text[-1].isspace():
                        raw_text += "\n\n"   # what she said before the tool and after it stay apart
                    break  # re-enter the outer for-loop with results appended
                if event["type"] == "usage":
                    usage = event
                    continue
                if event["type"] == "notice":
                    notice = {"code": "price_unknown", "message": event["text"], "reply_to": None}
                    await websocket.send_json(protocol.frame("error", notice, thread=thread_id))
                    continue
                raw_text += event["text"]
                if event["text"]:
                    await websocket.send_json(protocol.frame("token", {"text": event["text"]}, thread=thread_id))
                timings.mark("first_token")
            if not saw_tool_call:
                # A normal reply, not another tool call -- stream's fully
                # done now, not mid-flight, so this is the only safe point
                # to check for a trailing [emotion] tag (see
                # extract_emotion_tag()'s own docstring on why mid-stream
                # would risk a false match).
                detected_emotion = extract_emotion_tag(raw_text)[1]
                to_speak = reply_text(raw_text)
                if not to_speak:
                    # The model ended without a word (often a thinking model out of
                    # room): say so, never a silent turn (FR-R-5, D-064).
                    with contextlib.suppress(Exception):
                        failure = {"code": "model_failed", "reason": "EMPTY_REPLY", "message": EMPTY_REPLY_LINE,
                                   "model_ref": model_ref, "actions": ["retry", "switch_model"], "reply_to": None}
                        await websocket.send_json(protocol.frame("error", failure, thread=thread_id))
                break
        else:
            # Used up every round still calling tools, never landed on an
            # actual reply -- a model stuck re-calling a tool (or hitting
            # one that keeps failing) shouldn't hang the turn forever.
            # Distinct from LLMUnreachableError below: the server itself
            # is fine, she just never got to a real answer.
            with contextlib.suppress(Exception):
                failure = {"code": "model_failed", "reason": "TOOL_LOOP", "message": TOOL_STUCK_LINE,
                           "model_ref": None, "actions": ["retry"], "reply_to": None}
                await websocket.send_json(protocol.frame("error", failure, thread=thread_id))
    except llm.LLMUnreachableError as exc:
        # Logged: this branch used to swallow the exception completely, so a
        # 400/500 or a timeout from a server that was running looked exactly
        # like "server not running" and left nothing to diagnose from.
        log.warning(f"LLM call failed ({type(exc).__name__}): {exc}")
        # FR-R-5: the chosen model failed or may not run. Say so plainly with a
        # typed error the chat view turns into Retry / Switch model; never
        # quietly answer from another model.
        with contextlib.suppress(Exception):
            await websocket.send_json(failure_frame(exc, thread_id))
        # Half a reply is still what she said: it is kept (below), but not read aloud.
    except Exception:  # noqa: BLE001 -- deliberate catch-all, see below
        # Anything else (a TTS failure, a socket error, a plain bug) used to
        # kill this task silently: the finally block below still recorded
        # whatever had been spoken so far -- which reads exactly like a
        # reply that cut itself off -- and then the exception escaped
        # without turn_done ever being sent, leaving the frontend's stop
        # button stuck on. The traceback goes to the log so the cause is
        # finally visible, and the flow falls through to the normal
        # turn_done. CancelledError (the stop button) is a BaseException and
        # deliberately NOT caught here -- stop must still cancel the turn.
        log.exception("turn failed with an unexpected error (reply cut off)")
        to_speak = ""
    finally:
        # In `finally`, not just after the try block, so a stop-button
        # cancellation (asyncio.CancelledError, raised into whichever
        # await this task happens to be sitting on when the session's
        # on_stop cancels it) still records whatever was actually
        # said up to that point -- matching reality (she got cut off
        # mid-sentence) instead of silently dropping the whole turn.
        # CancelledError propagates on through after this, same as any
        # other exception would through a finally block. The failure card's
        # words are never added: she never said them.
        final_text = reply_text(raw_text, stopped=isinstance(sys.exc_info()[1], asyncio.CancelledError))
        if final_text:
            history.append({"role": "assistant", "content": final_text})
            if temp_turn_flags is not None:
                temp_turn_flags.append(temp_mode)
        else:
            # Nothing usable came back (LLM unreachable, or stopped before a
            # single token arrived) -- drop the dangling user turn rather
            # than leave a one-sided exchange in context for next time.
            history.pop()
            if temp_turn_flags is not None:
                temp_turn_flags.pop()
        trim_history(history, temp_turn_flags)
        arbiter.ARBITER.on_turn_finished()
        LATENCY.finish(timings)
        # Awaiting here, inside `finally`, after a possible cancellation
        # above is safe: the cancellation that got us here already fired
        # once (at whichever `await` this task was sitting on), and
        # nothing cancels it a second time while this runs -- the session's
        # on_stop only calls turn.cancel() once, then
        # awaits the task's own unwinding. Logged unconditionally (not
        # just on normal completion) so the log panel matches reality even
        # for a stopped-mid-sentence turn, same reasoning as the
        # history.append() above.
        # FR-MODE-4: a roleplay exchange never reaches transcript_log, so the memory
        # writer never distils a story into facts about the real user.
        log_id = None if roleplay else await log_transcript_turn(
            user_text, apply_persona_pass(final_text) if final_text else "", temp_mode, speaker=companions.speaker_of(websocket)
        )
        # K1-00: the thread store records the exchange (user line, reply text, and
        # whether Stop cut it off, FR-C-2). Same "never fail the turn" rule as the
        # transcript log right above.
        if final_text:
            # K1-10: a model that just answered is not "failed to load" any more.
            with contextlib.suppress(Exception):
                await model_loader.LOADER.mark_ready(model_listing.effective_ref(model_ref, CONFIG))
        if on_finished is not None:
            stopped = isinstance(sys.exc_info()[1], asyncio.CancelledError)
            try:
                meta = {"log_id": log_id, "attachment": attachment, "sent_to": sent_to,
                        "tokens_in": usage.get("tokens_in"), "tokens_out": usage.get("tokens_out")}
                await on_finished(user_text, final_text, stopped, {k: v for k, v in meta.items() if v is not None})
            except Exception as exc:  # noqa: BLE001 -- a storage hiccup must not end the turn
                log.warning(f"could not save the exchange to the thread: {exc}")
        with contextlib.suppress(Exception):
            await websocket.send_json(
                protocol.frame(
                    "turn_done",
                    {
                        "text": final_text,
                        "stopped": isinstance(sys.exc_info()[1], asyncio.CancelledError),
                        "emotion": detected_emotion,   # the avatar's expression (K2)
                    },
                    thread=thread_id,
                )
            )
    return to_speak
