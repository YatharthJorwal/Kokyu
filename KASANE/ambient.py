"""The screen companions (FR-SC-1..5). Task Guide checks the screen against the
user's task and nudges when they drift; OCR watch remarks on what is on screen now
and then. Both run on the local vision model only (FR-SC-3), never while a reply is
running and never over someone typing (FR-SC-5). A remark is spoken and stored in
the thread, flagged ambient, so no model is ever handed it again (FR-R-7).
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import WebSocket

import companions
import llm
import router
import turns
from audio import arbiter
from audio.chunking import flush
from config import CONFIG
from persona import apply_persona_pass, extract_emotion_tag
from senses import ocr_watch, task_guide
from tools import vision

log = logging.getLogger(__name__)


def _stale(still_valid: "Callable[[], bool] | None", what: str) -> bool:
    """FR-MODE-9: the window's thread changed while the check ran (the user opened a
    roleplay or another thread). The remark belongs to the thread the check started
    in, so it is dropped, never spoken into the new one or stored there."""
    if still_valid is None or still_valid():
        return False
    log.info(f"{what}: dropped, the thread changed while the check ran")
    return True


# FR-SC-5: OCR watch keeps quiet while the user is typing. The chat window sends a
# `typing` frame at most every few seconds while keys go down.
TYPING_QUIET_SECONDS = 10.0


_last_typed_at = 0.0


def note_typing() -> None:
    """The window says the user is typing (FR-SC-5)."""
    global _last_typed_at
    _last_typed_at = time.monotonic()


def typing_recently(now: float | None = None) -> bool:
    return ((now if now is not None else time.monotonic()) - _last_typed_at) < TYPING_QUIET_SECONDS


async def vision_problem() -> str | None:
    """FR-SC-3: screen companions run on the local vision model only (the `vision`
    role is local_only). None when it reports that it can see images."""
    name = llm.vision_model_name()
    caps = await llm.model_capabilities(name)
    if caps is None:
        return f"Screen companions need a local vision model, and Ollama did not answer for '{name}'. Is Ollama running?"
    if "vision" not in caps:
        return f"Screen companions need a local model that can see images, and '{name}' cannot. Set llm.vision_model to one that can."
    return None


# Phase 4 Round 2 -- how often a session's task-guide background loop
# wakes up to check whether a screen check or an idle-clear is actually
# due (see _task_guide_loop). This is just a cheap dict read most of the
# time (task_guide.due_for_check/is_idle), not the interval between real
# screen checks themselves -- that's CONFIG.task_guide.capture_interval_
# seconds, checked against task_guide's own last_check_at timestamp each
# time this fires. Short enough that the real interval (90s by default)
# isn't meaningfully delayed by polling granularity, long enough not to
# spin the event loop for no reason while no task is even active.
TASK_GUIDE_POLL_SECONDS = 15


# Continuous OCR -- same reasoning as TASK_GUIDE_POLL_SECONDS above, just
# coarser: this feature's own real interval
# (CONFIG.ocr_watch.comment_interval_seconds, 240s by default) is far
# longer than task_guide's, so there's no need to poll as tightly to stay
# close to it.
OCR_WATCH_POLL_SECONDS = 30


# Phase 4 Round 2 -- how the drift observation from task_guide.check_task_
# progress() gets turned into an actual in-character line. Framed as an
# ephemeral one-off user-role message spliced onto the end of `history`
# for this call only (never written into `history` itself) -- same
# "ephemeral system context, not a real turn" treatment as recall.py's
# memory block and _scene_state above, just user-role here since it's
# instructing her to react to something specific rather than describing
# ambient world state.
def drift_prompt(task_description: str, observation: str) -> str:
    return (
        f"You are currently tracking this task for the user: "
        f"{task_description!r}. You just glanced at their screen on "
        f"your own, without them saying anything, and it looks like "
        f"they have drifted off it: {observation!r}. React to this "
        "right now, in character, in one short spoken line -- call it "
        "out and steer them back to the step. Do not mention that you "
        "were checking, do not mention a timer or a tool or that this "
        "was automatic, just react like you noticed it yourself. End "
        "with your usual [emotion] tag on its own line, same as always."
    )


async def run_task_guide_check(
    websocket: WebSocket,
    history: list[dict[str, str]],
    task_description: str,
    temp_mode: bool = False,
    temp_turn_flags: list[bool] | None = None,
    unprompted: list[dict[str, str]] | None = None,
    on_remark: "Callable[[str], Awaitable[None]] | None" = None,
    still_valid: "Callable[[], bool] | None" = None,
) -> None:
    """The scheduled half of Task Guide Mode actually doing its job: grab
    a screenshot, ask the VLM whether it still matches the tracked step
    (task_guide.check_task_progress), and if it clearly doesn't, have her
    react in character over the same speak pipeline turns.run_turn uses for a
    real reply -- just triggered by _task_guide_loop's timer instead of
    the user typing something.

    temp_mode/temp_turn_flags: read live off the connection at call time
    (see _task_guide_loop's own comment on late-binding closures) so a
    chide that happens to land while Temp Chat is toggled on still gets
    excluded from memory (the writer skips temp rows), same as everything else
    said during that window -- this does NOT suppress the chide itself,
    just how its history entry gets treated afterward. Task tracking
    itself already can't *start* during temp_mode (see turns.run_turn), so
    this only matters for a task that was already active before Temp
    Chat got toggled on mid-session.

    Always calls task_guide.mark_checked() up front (whether or not this
    ends up chiding) so due_for_check() measures from "last time we
    actually looked," not "last time we found drift" -- an on-task
    result still counts as a completed check.

    Deliberately narrow about what's worth logging vs. silently skipping:
    a failed capture, an unreachable LLM, or an unparseable VLM response
    all just mean "try again next interval" -- none of these should ever
    surface to the user as more than, at most, a missed check. Not
    wrapped in a broader try/except beyond that: an unexpected exception
    here should still show up in the kernel's own terminal rather
    than vanish, same as any other real bug would.
    """
    task_guide.mark_checked()
    try:
        image_b64 = await asyncio.to_thread(vision.capture_screen, CONFIG.vision.ambient_max_long_edge)
    except vision.ToolUnavailableError as exc:
        log.warning(f"task guide: capture failed, skipping this check: {exc}")
        return

    result = await task_guide.check_task_progress(task_description, image_b64)
    if result is None:
        log.warning("task guide: check result didn't parse, skipping this check")
        return
    # Logged unconditionally (not just on drift) so the loop's actual
    # cadence is visible in kasane.log without needing to wait for
    # a real chide -- useful for confirming it's alive at all during
    # testing, or for tuning capture_interval_seconds against how often
    # checks are really landing.
    log.info(
        f"task guide: checked '{task_description}' -> "
        f"on_task={result['on_task']} ({result['note'] or 'no note'})",
    )
    if result["on_task"]:
        return

    if _stale(still_valid, "task guide"):
        return   # `history` is another thread's now
    prompt = drift_prompt(task_description, result["note"] or "something unrelated is on screen")
    try:
        buffer = ""
        async for delta in router.stream_text("reflex", 
            turns.fit_for_llm(history + [{"role": "user", "content": prompt}])
        ):
            buffer += delta
    except llm.LLMUnreachableError as exc:
        log.warning(f"task guide: LLM unreachable for chide, skipping: {exc}")
        return

    buffer, _emotion = extract_emotion_tag(buffer)
    reply_parts = flush(buffer)
    if not reply_parts:
        return

    allowed, reason = arbiter.ARBITER.may_speak_ambient()
    if not allowed:
        log.info(f"task guide: chide suppressed ({reason})")
        return
    if _stale(still_valid, "task guide"):
        return
    for chunk in reply_parts:
        await turns.send_speak(websocket, apply_persona_pass(chunk))
    if _stale(still_valid, "task guide"):
        return   # spoken, but never recorded in the thread that is open now

    # Recorded as her own assistant turn, same as a normal reply, so a
    # later real turn sees she already commented on the drift and Phase
    # 9's transcript-log panel shows it happened. Deliberately no
    # matching "user" turn precedes it -- nobody said anything -- which
    # is a legitimate shape for an unprompted comment, not a bug.
    turns.record_unprompted(history, " ".join(reply_parts), temp_mode, temp_turn_flags, unprompted)
    await turns.log_transcript_turn("", " ".join(apply_persona_pass(p) for p in reply_parts), temp_mode, speaker=companions.speaker_of(websocket))
    if on_remark is not None:
        await on_remark(" ".join(reply_parts))


def ambient_comment_prompt(observation: str) -> str:
    return (
        f"You just glanced at the user's screen on your own, without "
        f"them saying anything, and noticed something worth remarking "
        f"on: {observation!r}. React to this right now, in character, "
        "in one short spoken line -- a genuine, in-the-moment remark, "
        "not a report. Do not mention that you were checking, do not "
        "mention a timer or a tool or that this was automatic, just "
        "react like you noticed it yourself. End with your usual "
        "[emotion] tag on its own line, same as always."
    )


async def run_ocr_watch_check(
    websocket: WebSocket,
    history: list[dict[str, str]],
    temp_mode: bool = False,
    temp_turn_flags: list[bool] | None = None,
    unprompted: list[dict[str, str]] | None = None,
    on_remark: "Callable[[str], Awaitable[None]] | None" = None,
    still_valid: "Callable[[], bool] | None" = None,
) -> None:
    """Continuous OCR's own scheduled check -- structurally the same
    shape as run_task_guide_check above (grab a screenshot, ask the VLM
    a judgment question, react in character if it says yes), but judging
    "is this worth an unprompted remark at all" (ocr_watch.
    check_for_comment) rather than "does this match a tracked task."
    Unlike Task Guide Mode, there is no task description to compare
    against -- ocr_watch.py's own WatchState.last_seen_summary is the only
    context carried between checks, so the judgment is "changed/notable
    since last glance," not "off the goal."

    temp_mode/temp_turn_flags: same treatment as run_task_guide_check's
    own -- read live at call time so a comment landing while Temp Chat is
    on still gets excluded from memory (the writer skips temp rows), without
    suppressing the comment itself.

    Always calls ocr_watch.mark_checked() (with the fresh summary, so the
    next check has something to compare against) whether or not this
    ends up commenting -- due_for_check() measures from "last time we
    actually looked," not "last time we said something."

    Same "narrow about what's worth logging vs. silently skipping" policy
    as run_task_guide_check: a failed capture, an unreachable LLM, or an
    unparseable VLM response all just mean "try again next interval,"
    never more than a missed check.
    """
    try:
        image_b64 = await asyncio.to_thread(vision.capture_screen, CONFIG.vision.ambient_max_long_edge)
    except vision.ToolUnavailableError as exc:
        log.warning(f"ocr watch: capture failed, skipping this check: {exc}")
        return

    previous_summary = ocr_watch.get_state().last_seen_summary
    last_comment_at = ocr_watch.get_state().last_comment_at
    result = await ocr_watch.check_for_comment(previous_summary, image_b64)
    if result is None:
        log.warning("ocr watch: check result didn't parse, skipping this check")
        return
    ocr_watch.mark_checked(result["summary"])
    # The model's comment_worthy is necessary, not sufficient: code applies
    # the quiet rules the prompt could not enforce (same screen as last
    # time, minimum gap since she last spoke, an actual note to react to).
    # The line below is logged unconditionally, same reasoning as
    # task_guide's own check line: it confirms the loop is alive without
    # waiting for a real comment, and says why a "yes" was overruled.
    speak, reason = ocr_watch.decide_comment(
        result,
        previous_summary,
        last_comment_at,
        CONFIG.ocr_watch.min_comment_gap_seconds,
        CONFIG.ocr_watch.same_screen_similarity,
    )
    suppressed = f" [no comment: {reason}]" if result["comment_worthy"] and not speak else ""
    log.info(
        f"ocr watch: checked -> comment_worthy={result['comment_worthy']} "
        f"({result['summary'] or 'no summary'}){suppressed}",
    )
    if not speak:
        return

    if _stale(still_valid, "ocr watch"):
        return   # `history` is another thread's now
    prompt = ambient_comment_prompt(result["note"])
    try:
        buffer = ""
        async for delta in router.stream_text("reflex", 
            turns.fit_for_llm(history + [{"role": "user", "content": prompt}])
        ):
            buffer += delta
    except llm.LLMUnreachableError as exc:
        log.warning(f"ocr watch: LLM unreachable for comment, skipping: {exc}")
        return

    buffer, _emotion = extract_emotion_tag(buffer)
    reply_parts = flush(buffer)
    if not reply_parts:
        return

    allowed, reason = arbiter.ARBITER.may_speak_ambient()
    if allowed and typing_recently():
        allowed, reason = False, "the user is typing"   # FR-SC-5: the check took seconds
    if not allowed:
        log.info(f"ocr watch: comment suppressed ({reason})")
        return
    if _stale(still_valid, "ocr watch"):
        return
    for chunk in reply_parts:
        await turns.send_speak(websocket, apply_persona_pass(chunk))
    if _stale(still_valid, "ocr watch"):
        return   # spoken, but never recorded in the thread that is open now

    # Same "unprompted comment, no preceding user turn" shape
    # run_task_guide_check's own chide uses -- see its comment for why
    # that's legitimate here too, not a bug.
    ocr_watch.mark_commented()
    turns.record_unprompted(history, " ".join(reply_parts), temp_mode, temp_turn_flags, unprompted)
    await turns.log_transcript_turn("", " ".join(apply_persona_pass(p) for p in reply_parts), temp_mode, speaker=companions.speaker_of(websocket))
    if on_remark is not None:
        await on_remark(" ".join(reply_parts))
