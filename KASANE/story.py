"""Story memory (K1c-04; FR-MODE-5, D-074).

Each roleplay thread keeps a running summary of its older scenes in `threads.db`
(`story_memory`, deleted with its thread), so a long story keeps its beginning
after the early messages fall out of the history window. It is written locally by
the `memory_writer` role (local-only, CLAUDE.md invariant 3) from the thread's own messages and fed to every
turn of that thread as part of the ephemeral note (`prompting.STORY_NOTE`), never
into history[0], so llama-server's cached prefix holds.

Batched: nothing happens until `story.summarize_every` messages that are not among
the newest `story.keep_recent` are waiting past `through_message_id`; then the old
summary and those messages are folded into a new one. The newest messages are never
folded, so Regenerate (which replaces only the last exchange) never has to take
back text that is already in the summary.

When it runs: in the background after a roleplay exchange is saved, and when a
roleplay thread is opened that is behind; never before boot's chat-model step is
over (D-060). Only while nothing else uses the model (the arbiter is idle, as for
the memory writer's timer pass, and no chat model is loading), one pass per thread at
a time, and a turn that starts cancels it (`preempt`, beside the memory writer's).
A failure is logged and leaves the old summary; the next exchange tries again.
Temp Chat keeps none, and chat threads have none. Nothing here reads or writes app
memory (`memory.db`): fiction never becomes facts about the user (FR-MODE-4).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import conversation
import model_loader
import router
from audio import arbiter
from config import CONFIG
from threads import Message

log = logging.getLogger(__name__)

ROLE = "memory_writer"   # local-only by policy (CLAUDE.md invariant 3); the router keeps it on this machine

INSTRUCTION = (
    "You keep the running summary of a roleplay story. Rewrite the summary to include the new "
    "scenes below. Keep names, places, relationships, promises, open threads and how things "
    "stand now; drop small talk. Write in past tense and third person, in at most {words} words. "
    "Output only the summary."
)
USER_SPEAKER = "the user"
HER_FALLBACK = "She"          # an assistant line stored without a speaker name
NO_SUMMARY_YET = "(none yet: this is the start of the story)"

# Sizes of one model call, like the memory writer's MAX_TURN_CHARS: a long backlog
# (a story opened far behind) is folded in several calls rather than one huge one.
MAX_MESSAGE_CHARS = 1500
MAX_BATCH_CHARS = 12000
# Regenerate replaces the last exchange (her reply and the user line before it), so
# however keep_recent is configured, those two are never folded.
MIN_KEEP_RECENT = 2
CHARS_PER_WORD = 6            # turns story.max_chars into the word limit in the instruction
# The fold call's reply cap. A local call otherwise gets llm.max_tokens (512), less
# than a summary near max_chars needs; a reply cut there would lose the newest scenes
# while through_message_id still moved past them. English runs about 4 characters a
# token; 3 leaves room, and the margin covers a short preamble.
CHARS_PER_TOKEN = 3
TOKEN_MARGIN = 128

_ENDS = ".!?"
_CLOSERS = "\"')]*”’"

Listener = Callable[[str, str], None]


def limits() -> tuple[int, int, int]:
    """(summarize_every, keep_recent, max_chars) from config; summarize_every <= 0 is off."""
    cfg = CONFIG.story
    return int(cfg.summarize_every), max(MIN_KEEP_RECENT, int(cfg.keep_recent)), int(cfg.max_chars)


def story_lines(messages: list[Message]) -> list[Message]:
    """What was said in the story: user and assistant lines with text. Dividers and
    screen companion remarks are not part of it."""
    return [
        m for m in messages
        if m.role in ("user", "assistant") and m.content.strip() and not m.meta.get("ambient")
    ]


def foldable(messages: list[Message], through_id: int, keep_recent: int) -> list[Message]:
    """The lines waiting to be folded: newer than `through_id`, never the newest `keep_recent`."""
    lines = story_lines(messages)
    older = lines[:-keep_recent] if keep_recent > 0 else lines
    return [m for m in older if m.id > through_id]


def format_line(message: Message) -> str:
    speaker = USER_SPEAKER if message.role == "user" else (message.speaker_name or HER_FALLBACK)
    return f"{speaker}: {message.content.strip()[:MAX_MESSAGE_CHARS]}"


def take_batch(pending: list[Message]) -> list[Message]:
    """The oldest pending lines that fit one call; always at least one."""
    batch: list[Message] = []
    used = 0
    for message in pending:
        cost = len(format_line(message)) + 1
        if batch and used + cost > MAX_BATCH_CHARS:
            break
        batch.append(message)
        used += cost
    return batch


def words_for(max_chars: int) -> int:
    return max(40, max_chars // CHARS_PER_WORD)


def tokens_for(max_chars: int) -> int:
    """The reply cap a fold asks for: room for a whole summary of `max_chars`."""
    return -(-max(max_chars, words_for(max_chars) * CHARS_PER_WORD) // CHARS_PER_TOKEN) + TOKEN_MARGIN


def cut(text: str, limit: int) -> str:
    """`text` trimmed to `limit` characters, ending at the last sentence end that fits
    (a closing quote or bracket stays with its sentence); at a word when none does."""
    text = text.strip()
    if len(text) <= limit:
        return text
    best = 0
    for i, ch in enumerate(text[:limit]):
        if ch not in _ENDS:
            continue
        j = i + 1
        while j < len(text) and text[j] in _CLOSERS:
            j += 1
        if j <= limit and (j == len(text) or text[j].isspace()):
            best = j
    if best:
        return text[:best].rstrip()
    head = text[:limit]
    if text[limit].isspace() or head[-1].isspace():
        return head.rstrip()   # the cut already falls between words
    parts = head.rsplit(None, 1)
    return (parts[0] if len(parts) > 1 else head).rstrip()


def fold_messages(summary: str, batch: list[Message], max_chars: int) -> list[dict[str, str]]:
    """The memory_writer call that folds `batch` into `summary`."""
    scenes = "\n".join(format_line(m) for m in batch)
    return [
        {"role": "system", "content": INSTRUCTION.format(words=words_for(max_chars))},
        {"role": "user", "content": f"The summary so far:\n{summary or NO_SUMMARY_YET}\n\nThe new scenes:\n{scenes}"},
    ]


def _model_busy() -> bool:
    """The memory writer's signal (app.py): anything but idle means a turn or a voice
    exchange holds the model. A chat-model load in progress (the model loader, K1-10)
    counts too: a fold beside it would load a second local model (D-065, D-072)."""
    return arbiter.ARBITER.state != arbiter.IDLE or model_loader.LOADER.busy()


async def _after_boot() -> None:
    """D-060: nothing folds before boot's chat-model step is over, the same point the
    memory writer's catch-up pass waits behind. Imported here: boot imports much."""
    import boot

    await boot.chat_model_settled_event().wait()


class StoryKeeper:
    """Runs the summaries in the background: one task per thread at most. `ready` is
    awaited before each pass (the running kernel's keeper waits for boot)."""

    def __init__(
        self,
        is_busy: Callable[[], bool] | None = None,
        ready: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._is_busy = is_busy or _model_busy
        self._ready = ready
        self._running: dict[str, asyncio.Task] = {}
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """`listener(thread_id, summary)` after each summary is saved; returns the unsubscribe."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def running(self, thread_id: str) -> asyncio.Task | None:
        task = self._running.get(thread_id)
        return task if task is not None and not task.done() else None

    def schedule(
        self, thread_id: str | None, manager: conversation.ConversationManager | None = None
    ) -> asyncio.Task | None:
        """Starts catching the thread's summary up in the background, unless a pass for
        it is already running or story memory is off. Never raises into the caller.
        The threads store is bound now, not when the task runs."""
        if not thread_id or limits()[0] <= 0:
            return None
        running = self.running(thread_id)
        if running is not None:
            return running
        manager = manager or conversation.get_manager()
        task = asyncio.create_task(self._guarded(thread_id, manager), name=f"story-memory-{thread_id}")
        self._running[thread_id] = task

        def finished(done: asyncio.Task, key: str = thread_id) -> None:
            if self._running.get(key) is done:
                del self._running[key]

        task.add_done_callback(finished)
        return task

    def preempt(self) -> None:
        """A turn is starting: the model is the reply's. A cancelled pass writes nothing
        it had not finished; the next exchange starts it again."""
        for task in list(self._running.values()):
            if not task.done():
                task.cancel()

    async def _guarded(self, thread_id: str, manager: conversation.ConversationManager) -> None:
        try:
            if self._ready is not None:
                await self._ready()
            await self.catch_up(thread_id, manager)
        except asyncio.CancelledError:
            log.debug(f"story memory: pass for thread {thread_id} preempted by a turn")
            raise
        except Exception as exc:  # noqa: BLE001 -- background work must never reach the session
            log.warning(f"story memory: could not update the summary of thread {thread_id}: {exc}")

    async def catch_up(self, thread_id: str, manager: conversation.ConversationManager | None = None) -> int:
        """Folds the thread's waiting lines into its summary while at least
        `summarize_every` are waiting. Returns how many lines were folded."""
        every, keep, max_chars = limits()
        if every <= 0:
            return 0
        manager = manager or conversation.get_manager()
        thread = await manager.get(thread_id)
        # From the thread only (FR-W-3): a roleplay that is not in Temp Chat.
        if thread is None or thread.mode != "roleplay" or thread.temp:
            return 0
        current = await manager.story(thread_id)
        summary = current.summary if current is not None else ""
        through = current.through_message_id if current is not None else 0
        pending = foldable(await manager.messages(thread_id), through, keep)
        folded = 0
        while len(pending) >= every:
            if self._is_busy():
                log.debug(f"story memory: the model is busy, thread {thread_id} waits for the next exchange")
                break
            batch = take_batch(pending)
            new_summary = await self._fold(summary, batch, max_chars)
            if not new_summary:
                break   # the old summary stays; the next exchange tries again
            if not await manager.save_story(thread_id, new_summary, batch[-1].id):
                break   # the thread was deleted meanwhile
            summary = new_summary
            pending = pending[len(batch):]
            folded += len(batch)
            log.info(f"story memory: folded {len(batch)} lines of thread {thread_id} ({len(summary)} chars)")
            self._notify(thread_id, summary)
        return folded

    @staticmethod
    async def _fold(summary: str, batch: list[Message], max_chars: int) -> str:
        """The new summary, or "" when the model failed or wrote nothing."""
        try:
            text = "".join([
                d async for d in router.stream_text(
                    ROLE, fold_messages(summary, batch, max_chars), max_tokens=tokens_for(max_chars)
                )
            ])
        except Exception as exc:  # noqa: BLE001 -- a failure keeps the old summary
            log.warning(f"story memory: the summary model failed, the old summary stays: {exc}")
            return ""
        return cut(text, max_chars)

    def _notify(self, thread_id: str, summary: str) -> None:
        for listener in list(self._listeners):
            try:
                listener(thread_id, summary)
            except Exception as exc:  # noqa: BLE001 -- one window's listener must not stop the rest
                log.warning(f"story memory: a listener failed: {exc}")


KEEPER = StoryKeeper(ready=_after_boot)
