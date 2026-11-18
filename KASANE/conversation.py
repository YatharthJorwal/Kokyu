"""Conversation manager (K1-00; FR-C-1, FR-C-10, FR-S-2, FR-MEM-5).

Sits between the WebSocket endpoint and the threads store. It decides which
thread a connection is in, turns stored messages into the LLM history the
turn loop already understands, and records each finished exchange with who
spoke and which model and effort produced it.

Waifu invariance (FR-W-3): nothing here branches on a waifu. A waifu id and
name are only *recorded* (speaker columns, the thread's active companion) and
a divider is written when the companion changes. Which model answers, recall,
tools and memory are decided elsewhere and never read these fields.

All store calls go through `asyncio.to_thread` so SQLite never blocks the
kernel's event loop.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from collections.abc import Collection
from typing import Any

import paths
from config import CONFIG
from threads import Message, ScenarioCard, StoryMemory, Thread, ThreadStore

log = logging.getLogger("kokyu.conversation")

LAST_THREAD_KEY = "last_thread"


@dataclass(frozen=True)
class Speaker:
    """Who said an assistant line: recorded, never used to decide anything."""

    waifu_id: str | None
    name: str | None


def divider_text(name: str | None) -> str:
    return f"Switched to {name}" if name else "Switched companion"  # FR-S-2 wording


def prompt_layers(thread: Thread | None) -> dict[str, Any]:
    """The thread's part of the system message (FR-MODE-2): its mode and scenario card,
    as keywords for `companions.system_message`. Read from the THREAD only, never from
    a companion (FR-W-3, D-074). No thread (the store is unavailable) means chat."""
    if thread is None:
        return {"mode": "chat", "scenario": None}
    return {"mode": thread.mode, "scenario": dict(thread.scenario) or None}


def _aside(message: Message) -> bool:
    """A stored assistant line that no user line asked for: a screen companion's remark
    (meta.ambient) or a roleplay's opening (meta.opening, FR-MODE-6). Neither is part
    of an exchange, so neither goes to a model as history nor is regenerated."""
    return bool(message.meta.get("ambient") or message.meta.get("opening"))


def history_from(messages: list[Message], system_message: str, max_messages: int) -> list[dict[str, str]]:
    """The turn loop's `history` list: the system prompt, then the latest user and
    assistant lines. Dividers are UI markers, not something anyone said, so they stay out.
    So do screen companion remarks: they came from a screen capture, and a reloaded
    thread may run on an API model (FR-SC-3, FR-R-7). A roleplay's opening line stays
    out too: it is already in the system message's scenario block (FR-MODE-6, D-074),
    and it would be a leading assistant line anyway."""
    turns = [
        {"role": m.role, "content": m.content}
        for m in messages
        if m.role in ("user", "assistant") and m.content and not _aside(m)
    ]
    if max_messages >= 0 and len(turns) > max_messages:
        turns = turns[-max_messages:] if max_messages else []
    # The model expects a user line first after the system prompt; a leading
    # assistant line (an unprompted remark, or a cut by the window) is dropped.
    while turns and turns[0]["role"] == "assistant":
        turns.pop(0)
    return [{"role": "system", "content": system_message}, *turns]


class ConversationManager:
    def __init__(self, store: ThreadStore, *, history_messages: int = 40) -> None:
        self.store = store
        self.history_messages = history_messages

    async def _run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(fn, *args, **kwargs)

    # -- choosing a thread -----------------------------------------------------

    async def last_thread(self) -> Thread | None:
        """The thread a fresh connection would land in, without creating one: the
        one last opened, else the most recent. Boot uses it to load that thread's
        model before any window connects (K1-10, D-054)."""
        last = await self._run(self.store.get_kv, LAST_THREAD_KEY)
        thread = await self._run(self.store.find_thread, last) if last else None
        if thread is None or thread.archived:
            recent = await self._run(self.store.list_threads, limit=1)
            thread = recent[0] if recent else None
        return thread

    async def open_initial(self, *, waifu_id: str | None) -> Thread:
        """The thread a fresh connection lands in: the one last opened, else the most
        recent, else a new one. A page reload therefore returns to the same thread."""
        thread = await self.last_thread()
        if thread is None:
            thread = await self.new_thread(waifu_id=waifu_id)
        await self._run(self.store.set_kv, LAST_THREAD_KEY, thread.id)
        return thread

    async def new_thread(
        self,
        *,
        waifu_id: str | None,
        model_ref: str | None = None,
        effort: str | None = None,
        temp: bool = False,
        mode: str = "chat",
        scenario: dict[str, Any] | None = None,
        title: str = "",
    ) -> Thread:
        """`mode` and `scenario` are fixed for the thread's life (FR-MODE-1). A roleplay
        started from a card with a title is named after it; otherwise the first user
        message names the thread, as before."""
        thread = await self._run(
            self.store.create_thread,
            title=title,
            active_waifu_id=waifu_id,
            model_ref=model_ref,
            effort=effort,
            temp=temp,
            mode=mode,
            scenario=scenario,
        )
        await self._run(self.store.set_kv, LAST_THREAD_KEY, thread.id)
        return thread

    async def open(self, thread_id: str) -> Thread | None:
        thread = await self._run(self.store.find_thread, thread_id)
        if thread is not None:
            await self._run(self.store.set_kv, LAST_THREAD_KEY, thread.id)
        return thread

    async def get(self, thread_id: str) -> Thread | None:
        return await self._run(self.store.find_thread, thread_id)

    # -- history list, rename, delete, search ----------------------------------

    async def list(self) -> list[Thread]:
        return await self._run(self.store.list_threads)

    async def search(self, query: str) -> list[Thread]:
        return await self._run(self.store.search, query)

    async def rename(self, thread_id: str, title: str) -> Thread | None:
        if await self.get(thread_id) is None:
            return None
        return await self._run(self.store.rename, thread_id, title)

    async def delete(self, thread_id: str) -> bool:
        return await self._run(self.store.delete_thread, thread_id)

    async def pin(self, thread_id: str, on: bool) -> Thread | None:
        """UI1-09 (D-094): pinned threads stay at the top of the history list."""
        if await self.get(thread_id) is None:
            return None
        return await self._run(self.store.update_thread, thread_id, pinned=on)

    async def set_temp(self, thread_id: str, temp: bool) -> Thread | None:
        if await self.get(thread_id) is None:
            return None
        return await self._run(self.store.update_thread, thread_id, temp=temp)

    async def messages(self, thread_id: str) -> list[Message]:
        return await self._run(self.store.messages, thread_id)

    async def history(self, thread: Thread, system_message: str, *, exclude: Collection[int] = ()) -> list[dict[str, str]]:
        """`exclude`: message ids left out (Regenerate's old exchange)."""
        recent = await self._run(self.store.messages, thread.id, limit=self.history_messages * 2 + len(exclude))
        return history_from([m for m in recent if m.id not in exclude], system_message, self.history_messages)

    # -- recording -------------------------------------------------------------

    async def record_exchange(
        self,
        thread_id: str,
        user_text: str,
        assistant_text: str,
        *,
        speaker: Speaker,
        model_ref: str | None = None,
        effort: str | None = None,
        stopped: bool = False,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        meta: dict[str, Any] | None = None,
        reply_meta: dict[str, Any] | None = None,
    ) -> tuple[Message, Message | None]:
        """Stores one user line and the reply to it. A reply cut off by Stop is kept
        (FR-C-2) and flagged; a turn with no reply at all stores only the user line.
        The reply carries its token counts where the backend reported them (FR-C-10).
        `meta` rides on the user line: the turn's transcript_log row (log_id, so
        Regenerate can take it back out), an attachment's kind and the API model it
        went to (sent_to, FR-R-7). `reply_meta` rides on the reply: a swipe's
        candidates (D-100)."""
        user = await self._run(self.store.add_message, thread_id, "user", user_text, meta=meta or None)
        reply = None
        if assistant_text:
            reply = await self._run(
                self.store.add_message,
                thread_id,
                "assistant",
                assistant_text,
                speaker_waifu_id=speaker.waifu_id,
                speaker_name=speaker.name,
                model_ref=model_ref,
                effort=effort,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                meta={**(reply_meta or {}), **({"stopped": True} if stopped else {})} or None,
            )
        return user, reply

    async def last_exchange(self, thread_id: str) -> tuple[str, list[int], dict[str, Any]] | None:
        """The thread's last exchange, for Regenerate and Retry (K1-04): its user line,
        the message ids a new reply replaces (the line, and the reply if one came) and
        the user line's meta (see record_exchange).
        A failed turn left only the line. Dividers after it are skipped: a companion
        switch does not end the exchange. None when the thread does not end in one.
        A roleplay's opening line is never part of an exchange (FR-MODE-6): a thread
        holding only the opening has nothing to regenerate."""
        # A few dozen messages cover any run of dividers a user could click together.
        recent = await self._run(self.store.messages, thread_id, limit=50)
        tail = [m for m in recent if m.role != "divider" and not _aside(m)][-2:]
        if tail and tail[-1].role == "user":
            drop = tail[-1:]
        elif len(tail) == 2 and tail[0].role == "user" and tail[1].role == "assistant":
            drop = tail
        else:
            return None
        return drop[0].content, [m.id for m in drop], dict(drop[0].meta)

    async def record_remark(self, thread_id: str, text: str, *, speaker: Speaker) -> Message:
        """A screen companion's unprompted remark (FR-SC-2), flagged `ambient`."""
        return await self._run(
            self.store.add_message,
            thread_id,
            "assistant",
            text,
            speaker_waifu_id=speaker.waifu_id,
            speaker_name=speaker.name,
            meta={"ambient": True},
        )

    async def record_opening(self, thread_id: str, text: str, *, speaker: Speaker) -> Message:
        """A roleplay's opening line from its card (FR-MODE-6, D-074): her first message,
        flagged `opening`. Written by the user, not a model, so it has no model or effort.
        history_from and last_exchange leave it out; the system message carries it."""
        return await self._run(
            self.store.add_message,
            thread_id,
            "assistant",
            text,
            speaker_waifu_id=speaker.waifu_id,
            speaker_name=speaker.name,
            meta={"opening": True},
        )

    async def delete_messages(self, ids: list[int]) -> None:
        await self._run(self.store.delete_messages, ids)

    # -- message actions (D-100) -----------------------------------------------

    async def message(self, thread_id: str, message_id: int) -> Message | None:
        """A message of this thread, or None (gone, or in another thread)."""
        found = await self._run(self.store.get_message, message_id)
        return found if found is not None and found.thread_id == thread_id else None

    async def rewind(self, thread_id: str, message_id: int) -> list[Message]:
        return await self._run(self.store.rewind, thread_id, message_id)

    async def branch(self, thread_id: str, message_id: int) -> Thread:
        thread = await self._run(self.store.branch, thread_id, message_id)
        await self._run(self.store.set_kv, LAST_THREAD_KEY, thread.id)
        return thread

    async def set_pin(self, message: Message, on: bool) -> Message:
        meta = {k: v for k, v in message.meta.items() if k != "pinned"}
        if on:
            meta["pinned"] = True
        return await self._run(self.store.update_message, message.id, meta=meta)

    async def pins(self, thread_id: str) -> list[Message]:
        """A roleplay thread's pinned messages, oldest first (D-100)."""
        return [m for m in await self._run(self.store.messages, thread_id) if m.meta.get("pinned")]

    async def swipe_to(self, message: Message, index: int) -> Message:
        """Shows another of the reply's candidates (D-100): the shown one goes back
        into the list, the chosen one into the message's columns."""
        candidates = list(message.meta.get("swipes") or [])
        current = int(message.meta.get("swipe", 0))
        if not 0 <= index < len(candidates) or index == current or not isinstance(candidates[index], dict):
            raise ValueError("no such reply")
        chosen = candidates[index]
        candidates[current] = candidate_of(message)
        candidates[index] = None
        meta = {k: v for k, v in message.meta.items() if k not in ("stopped",)}
        meta.update(swipes=candidates, swipe=index)
        if chosen.get("stopped"):
            meta["stopped"] = True
        fields = {k: chosen.get(k) for k in CANDIDATE_FIELDS}
        return await self._run(self.store.update_message, message.id, **fields, meta=meta)

    # -- saved scenario cards (FR-MODE-6, D-074) -------------------------------

    async def scenarios(self) -> list[ScenarioCard]:
        return await self._run(self.store.list_scenarios)

    async def save_scenario(self, card: dict[str, Any], *, scenario_id: str | None = None) -> ScenarioCard:
        return await self._run(self.store.save_scenario, card, scenario_id=scenario_id)

    async def delete_scenario(self, scenario_id: str) -> bool:
        return await self._run(self.store.delete_scenario, scenario_id)

    # -- story memory (FR-MODE-5, D-074) ---------------------------------------

    async def story(self, thread_id: str) -> StoryMemory | None:
        return await self._run(self.store.get_story, thread_id)

    async def save_story(self, thread_id: str, summary: str, through_message_id: int) -> bool:
        """False when the thread was deleted meanwhile (nothing is written)."""
        return await self._run(self.store.set_story, thread_id, summary, through_message_id)

    async def record_companion_change(self, thread_id: str, speaker: Speaker) -> Message:
        """FR-S-2: a divider marks where another companion took over; the thread
        remembers her so reopening it brings her back."""
        await self._run(self.store.update_thread, thread_id, active_waifu_id=speaker.waifu_id)
        return await self._run(
            self.store.add_message,
            thread_id,
            "divider",
            divider_text(speaker.name),
            speaker_waifu_id=speaker.waifu_id,
            speaker_name=speaker.name,
        )


# A reply candidate (D-100): what a swipe puts back into the message's columns.
CANDIDATE_FIELDS = ("content", "speaker_waifu_id", "speaker_name", "model_ref", "effort", "tokens_in", "tokens_out")


def candidate_of(message: Message) -> dict[str, Any]:
    out: dict[str, Any] = {k: getattr(message, k) for k in CANDIDATE_FIELDS}
    if message.meta.get("stopped"):
        out["stopped"] = True
    return out


def next_swipe(old_reply: Message) -> dict[str, Any]:
    """The reply meta of a new candidate for `old_reply` (D-100): every earlier one
    is kept, the new one goes last and is shown. `None` marks the shown candidate,
    whose text lives in the message's own columns."""
    candidates = list(old_reply.meta.get("swipes") or [None])
    candidates[int(old_reply.meta.get("swipe", 0))] = candidate_of(old_reply)
    return {"swipes": [*candidates, None], "swipe": len(candidates)}


def pin_lines(pins: list[Message]) -> list[str]:
    """Pinned messages as lines for her prompt (D-100): who said it, then what."""
    return [f"{'The user' if m.role == 'user' else (m.speaker_name or 'You')}: {m.content}" for m in pins if m.content]


def thread_summary(thread: Thread) -> dict[str, Any]:
    """What the sidebar needs for one history row."""
    return thread.to_dict()


_manager: ConversationManager | None = None


def get_manager() -> ConversationManager:
    """The threads store for the current data dir (rebuilt if tests redirect it)."""
    global _manager
    db_path = paths.app_data_dir() / "threads.db"
    if _manager is None or _manager.store.db_path != db_path:
        _manager = ConversationManager(ThreadStore(db_path), history_messages=CONFIG.session.max_history_turns * 2)
    return _manager
