"""One model turn: the user's line in, the reply streamed token by token (FR-C-2)
and, with voice mode on (D-061), spoken clause by clause. Tools run here, the
exchange is logged for the memory writer, and a failure becomes an error frame
with Retry and Switch model (FR-R-5). Also the pieces every spoken path shares
(send_speak) and the limits on what the model is sent (fit_for_llm, trim_history).
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
import hub
import llm
import model_loader
import prompting
import protocol
import router
import story as story_memory
import tools
from audio import arbiter, latency, speech, speech_stream, tts, voice_mode
from audio.chunking import extract_ready_chunks, flush
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


async def synthesize_for(websocket: Any, spoken: str) -> bytes:
    """Speak in the active waifu's voice. With voice mode off (D-061) or a dead TTS
    backend this yields empty audio: the caption still shows and the reply stays
    text-only (FR-V-7)."""
    if not voice_mode.VOICE.speaking():
        return b""
    voice_params = companions.voice_of(websocket)
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
) -> list[dict[str, Any]]:
    """The messages actually sent to the model: `messages` with the oldest
    history dropped (from this copy only) until prompt + reserved reply fit
    llm.num_ctx. See context_budget.py for why -- replies were being cut off
    with done_reason 'length' because nothing bounded the prompt by size."""
    fitted, dropped, est_tokens, budget = context_budget.fit_messages(
        messages,
        num_ctx=CONFIG.llm.num_ctx,
        reply_reserve=CONFIG.llm.max_tokens,
        tools=tools_list,
        extra=extra,
    )
    if dropped:
        log.info(
            f"context: left out the {dropped} oldest history message(s) this call "
            f"to fit num_ctx={CONFIG.llm.num_ctx} (estimated prompt {est_tokens} tokens, "
            f"budget {budget}).",
        )
    if budget and est_tokens > budget:
        log.warning(
            f"the persona prompt + memory block alone (~{est_tokens} tokens) "
            f"exceed the prompt budget ({budget}) for num_ctx={CONFIG.llm.num_ctx}; raise "
            "llm.num_ctx.",
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
) -> None:
    """The actual agent turn: append user_text to history, stream the LLM
    reply, speak each sentence chunk as it's ready, commit (or roll back)
    history. Shared by both `user_text` (typed) and `user_audio`
    (transcribed) messages -- by the time this runs, there's no difference
    between the two.

    Also writes one row to Phase 9's persistent transcript_log table
    (memory/store.py) per call, regardless of how the turn ends (normal
    completion, LLM-unreachable fallback, or stopped mid-sentence) -- see
    spoken_parts below for what that does and doesn't include, and why
    it's tracked separately from reply_parts/history.

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
    story reaches app memory (FR-MODE-4). Its voice and captions get only her
    dialogue (speech.DialogueFilter, FR-MODE-8); history keeps the whole reply.
    The router role is "chat" in both modes.

    story: the thread's story summary (FR-MODE-5), passed by the session for a
    roleplay thread; it joins the turn's ephemeral note, never history[0]. Dropped
    in Temp Chat, like the profile card (D-074)."""
    if mode not in prompting.MODE_LAYERS:
        raise ValueError(f"unknown conversation mode: {mode!r}")
    roleplay = mode == "roleplay"
    history.append({"role": "user", "content": user_text})
    if temp_turn_flags is not None:
        temp_turn_flags.append(temp_mode)
    # K1-00b: the chat view streams the reply token by token (FR-C-2); the
    # spoken clauses below are unchanged.
    local_model = is_local_ref(model_ref)
    # FR-R-7: an attached file or image may go to the chosen API model, with a badge saying so.
    # shortcut: badged before the router decides, so a blocked call is badged too (over-warns); fine until routing reports back.
    sent_to = model_listing.effective_ref(model_ref, CONFIG) if attachment and not local_model else None
    with contextlib.suppress(Exception):
        await websocket.send_json(protocol.frame("turn_start", {"user_text": user_text, "sent_to": sent_to}, thread=thread_id))
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
    # FR-MODE-8: while voice is on, how to shape a reply that is heard. Per turn and
    # not in history[0]: voice is kernel-wide and toggles, the cached prefix must not.
    delivery = prompting.delivery_layer(mode) if voice_mode.VOICE.speaking() else None
    # FR-MODE-5: the story so far, for a roleplay only and never in Temp Chat (D-074).
    story_note = prompting.STORY_NOTE.format(summary=story) if story and roleplay and not temp_mode else None
    memory_parts = [part for part in (forget_hint, task_hint, look_hint, memory_block, story_note, delivery) if part]

    if memory_parts:
        combined = " ".join(memory_parts)
        messages_for_llm = history[:-1] + [{"role": "system", "content": combined}] + history[-1:]
    else:
        messages_for_llm = history

    buffer = ""
    reply_parts: list[str] = []
    # FR-MODE-8: in a roleplay only her dialogue is spoken. The raw stream goes
    # through this cut first, and `buffer` (the speech side) holds what is left;
    # raw_text below keeps everything she wrote. None in chat: buffer is the stream.
    dialogue = speech.DialogueFilter() if roleplay else None
    # Everything the model wrote, untouched (D-074): history, the saved message and
    # turn_done use it, so Markdown and paragraph breaks survive the stream.
    # reply_parts and spoken_parts are the speech side, clause by clause.
    raw_text = ""
    # Pipelined voice: clauses go in as the model writes them, audio comes out
    # in order, synthesizing one clause ahead of playback. The old path awaited
    # TTS inside this loop, so the model's next sentence waited on the voice.
    def _first_audio() -> None:
        timings.mark("first_audio")
        arbiter.ARBITER.on_first_audio()

    stream = speech_stream.SpeechStream(
        send=lambda display, audio: send_audio(websocket, display, audio),
        synth=lambda spoken: synthesize_for(websocket, spoken),
        on_first_audio=_first_audio,
    )
    # Everything actually sent to send_speak this turn, in order --
    # tracked separately from reply_parts because the two lists serve
    # different purposes and can legitimately diverge: reply_parts is what
    # goes back into `history` for the LLM's own context (and deliberately
    # excludes the LLM-unreachable fallback line, see below), while
    # spoken_parts is Phase 9's transcript-log panel's record of what the
    # user actually heard/saw this turn, unconditionally -- including that
    # same fallback line, since it genuinely was spoken to them even though
    # it shouldn't be fed back into the LLM as if she'd said it.
    spoken_parts: list[str] = []
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
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            saw_tool_call = False
            # K1-00c (D-025): the conversation runs as the `chat` role on the
            # thread's chosen model and effort. A camera/screen capture this
            # turn is ambient content and may only go to a local model.
            async for event in router.stream_with_tools(
                "chat",
                fit_for_llm(messages_for_llm, offered_tools, tool_messages) + tool_messages,
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
                buffer += dialogue.feed(event["text"]) if dialogue is not None else event["text"]
                raw_text += event["text"]
                if event["text"]:
                    await websocket.send_json(protocol.frame("token", {"text": event["text"]}, thread=thread_id))
                timings.mark("first_token")
                chunks, buffer = extract_ready_chunks(buffer)
                for chunk in chunks:
                    reply_parts.append(chunk)
                    styled = apply_persona_pass(chunk)
                    spoken_parts.append(styled)
                    timings.mark("first_clause")
                    await stream.push(styled)
            if not saw_tool_call:
                # A normal reply, not another tool call -- stream's fully
                # done now, not mid-flight, so this is the only safe point
                # to check for a trailing [emotion] tag (see
                # extract_emotion_tag()'s own docstring on why mid-stream
                # would risk a false match). The emotion is read from the raw
                # text: in a roleplay the dialogue cut has already dropped the tag.
                if dialogue is not None:
                    buffer += dialogue.finish()
                buffer = extract_emotion_tag(buffer)[0]
                detected_emotion = extract_emotion_tag(raw_text)[1]
                for chunk in flush(buffer):
                    reply_parts.append(chunk)
                    styled = apply_persona_pass(chunk)
                    spoken_parts.append(styled)
                    timings.mark("first_clause")
                    await stream.push(styled)
                await stream.close()
                if not reply_text(raw_text):
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
            await stream.close()
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
        # Flush whatever was already generated before the failure: half a reply
        # is still what she said.
        await stream.close()
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
        # Something in the voice path may have died; make sure a worker task
        # is not left behind holding clauses nobody will hear.
        stream.abort()
    finally:
        # In `finally`, not just after the try block, so a stop-button
        # cancellation (asyncio.CancelledError, raised into whichever
        # await this task happens to be sitting on when the session's
        # on_stop cancels it) still records whatever was actually
        # said up to that point -- matching reality (she got cut off
        # mid-sentence) instead of silently dropping the whole turn.
        # CancelledError propagates on through after this, same as any
        # other exception would through a finally block. The
        # LLM-unreachable fallback line above is deliberately NOT added to
        # reply_parts -- it was never really said by her, so it shouldn't
        # end up looking like a real reply in history either.
        final_text = reply_text(raw_text, stopped=isinstance(sys.exc_info()[1], asyncio.CancelledError))
        if final_text:
            history.append({"role": "assistant", "content": final_text})
            if temp_turn_flags is not None:
                temp_turn_flags.append(temp_mode)
        else:
            # Nothing usable came back (LLM unreachable and no fallback
            # line ended up in reply_parts either, or stopped before a
            # single chunk arrived) -- drop the dangling user turn rather
            # than leave a one-sided exchange in context for next time.
            history.pop()
            if temp_turn_flags is not None:
                temp_turn_flags.pop()
        trim_history(history, temp_turn_flags)
        # Stop-button cancellation and unexpected failures land here too; abort
        # is idempotent and a no-op after a normal close().
        stream.abort()
        arbiter.ARBITER.on_turn_finished()
        LATENCY.finish(timings, clauses=len(reply_parts), spoken=len(spoken_parts))
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
            user_text, " ".join(spoken_parts), temp_mode, speaker=companions.speaker_of(websocket)
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
