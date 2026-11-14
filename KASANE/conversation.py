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
from typing import Any

from threads import Message, Thread, ThreadStore

log = logging.getLogger("kokyu.conversation")

LAST_THREAD_KEY = "last_thread"


@dataclass(frozen=True)
class Speaker:
    """Who said an assistant line: recorded, never used to decide anything."""

    waifu_id: str | None
    name: str | None


def divider_text(name: str | None) -> str:
    return f"{name} joined the conversation" if name else "The companion changed"


def history_from(messages: list[Message], system_message: str, max_messages: int) -> list[dict[str, str]]:
    """The turn loop's `history` list: the system prompt, then the latest user and
    assistant lines. Dividers are UI markers, not something anyone said, so they stay out."""
    turns = [
        {"role": m.role, "content": m.content}
        for m in messages
        if m.role in ("user", "assistant") and m.content
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

    async def open_initial(self, *, waifu_id: str | None) -> Thread:
        """The thread a fresh connection lands in: the one last opened, else the most
        recent, else a new one. A page reload therefore returns to the same thread."""
        last = await self._run(self.store.get_kv, LAST_THREAD_KEY)
        thread = await self._run(self.store.find_thread, last) if last else None
        if thread is None or thread.archived:
            recent = await self._run(self.store.list_threads, limit=1)
            thread = recent[0] if recent else None
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
    ) -> Thread:
        thread = await self._run(
            self.store.create_thread,
            active_waifu_id=waifu_id,
            model_ref=model_ref,
            effort=effort,
            temp=temp,
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

    async def set_temp(self, thread_id: str, temp: bool) -> Thread | None:
        if await self.get(thread_id) is None:
            return None
        return await self._run(self.store.update_thread, thread_id, temp=temp)

    async def messages(self, thread_id: str) -> list[Message]:
        return await self._run(self.store.messages, thread_id)

    async def history(self, thread: Thread, system_message: str) -> list[dict[str, str]]:
        recent = await self._run(self.store.messages, thread.id, limit=self.history_messages * 2)
        return history_from(recent, system_message, self.history_messages)

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
    ) -> tuple[Message, Message | None]:
        """Stores one user line and the reply to it. A reply cut off by Stop is kept
        (FR-C-2) and flagged; a turn with no reply at all stores only the user line."""
        user = await self._run(self.store.add_message, thread_id, "user", user_text)
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
                meta={"stopped": True} if stopped else None,
            )
        return user, reply

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


def thread_summary(thread: Thread) -> dict[str, Any]:
    """What the sidebar needs for one history row."""
    return thread.to_dict()
