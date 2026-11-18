"""One window's conversation with the kernel (D-062).

A Session lives from a window's connect to its close. It owns that window's
thread, history, Temp Chat flag and the turn in flight, and answers each protocol
v1 message with the method named after it: `on_send` for `send`, and so on. A new
message type is a CLIENT_TYPES entry plus one `on_<type>` method (a test checks
that every type has one). The turn itself is turns.run_turn; the screen
companions' checks are ambient.py; who drives is hub.py.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

import ambient
import boot
import companions
import context_fit
import conversation
import doctor
import hub
import llm
import model_loader
import protocol
import router
import settings_file
import story
import turns
import vram
import waifus
from audio import read_aloud, stt
from config import CONFIG
from memory import viewer as memory_viewer
from memory import writer
from router import listing as model_listing
from senses import camera, ocr_watch, task_guide
from waifus import portrait

log = logging.getLogger(__name__)

# The turn's saver: (user line, reply, stopped, meta) -> stored in the thread.
Saver = Callable[[str, str, bool, dict[str, Any]], Awaitable[None]]

# Only the driving window may start a turn; another one is told why (D-062).
DRIVER_ONLY = frozenset({"send", "send_file", "regenerate", "message_rewind", "message_swipe", "message_pin"})

BUSY = "Wait for the reply to finish, or press Stop."
NO_THREADS = "Conversation history is unavailable right now."
NO_SCENARIOS = "Saved scenarios are unavailable right now."
GONE = "That conversation no longer exists."
NO_MESSAGE = "That message is no longer in this conversation."


class Session:
    """One window, from connect to close."""

    def __init__(self, websocket: WebSocket) -> None:
        self.ws = websocket
        self.registry = waifus.get_registry()
        self.manager = conversation.get_manager()
        self.history: list[dict[str, str]] = []
        # Temp Chat (FR-MEM-5) is per thread. temp_flags runs in lockstep with
        # history[1:], one bool per message, so the session-end memory pass can
        # leave out what was said while it was on.
        self.temp = False
        self.temp_flags: list[bool] = []
        # The unprompted remarks currently in `history`, by identity, so
        # context_budget.cap_unprompted keeps only the newest few.
        self.unprompted: list[dict[str, str]] = []
        self.thread: Any = None
        # The open roleplay thread's story summary (FR-MODE-5), kept here so a turn
        # starts without a database read; story.KEEPER tells us when it changes.
        self.story_summary = ""
        # The open roleplay thread's pinned messages as prompt lines (D-100).
        self.pins: list[str] = []
        # The turn in flight runs as its own task, so the receive loop still reads Stop.
        self.turn: asyncio.Task | None = None
        # Read aloud (D-097): the finished reply being spoken, its own task so the user
        # can type and send meanwhile; a new turn, Stop or another thread cancels it.
        self.speech: asyncio.Task | None = None
        # Dictation (D-097): one recording written down at a time, off the receive loop.
        self.dictating: asyncio.Task | None = None
        # A companion switch asked for mid-reply; it applies when the reply ends (FR-S-2).
        self.pending_waifu: str | None = None
        # Task Guide and OCR watch never speak at once: they share the history and the socket.
        self.ambient_lock = asyncio.Lock()
        self._loops: list[asyncio.Task] = []
        self._unsubscribe: list[Callable[[], None]] = []

    # ── life cycle ──────────────────────────────────────────────────────────

    async def run(self) -> None:
        await self.ws.accept()
        await self._open()
        try:
            while (raw := await self._receive()) is not None:
                await self._dispatch(raw)
        except WebSocketDisconnect:
            pass
        finally:
            await self._close()

    async def _open(self) -> None:
        ws = self.ws
        role = "driver" if hub.join(ws) else "observer"
        await ws.send_json(protocol.frame("surface_status", {"role": role}))
        boot.first_window_event().set()   # D-060: the boot sequence may start loading now
        await ws.send_json(protocol.frame("screen_companions", hub.screen_status()))
        await ws.send_json(protocol.frame("read_aloud_status", read_aloud.READ_ALOUD.status()))

        # The active companion lives on the connection; it starts as the one the user
        # last used. With no packs installed it stays None and the fallback answers.
        ws.state.waifu = self.registry.get(companions.load_active_id()) or self.registry.get(
            self.registry.default_id() or ""
        )
        self.history = [{"role": "system", "content": self.system_prompt()}]   # no thread yet: chat
        await companions.send_waifu_state(ws, self.registry)

        # Every window hears about model loads (K1-10, the waking-up card) and the voice
        # waking up for Read aloud (D-097).
        async def push_model_status(status: dict[str, Any]) -> None:
            await ws.send_json(protocol.frame("model_status", status))

        async def push_read_aloud(status: dict[str, Any]) -> None:
            await ws.send_json(protocol.frame("read_aloud_status", status))

        self._unsubscribe = [
            model_loader.LOADER.subscribe(push_model_status),
            read_aloud.READ_ALOUD.subscribe(push_read_aloud),
            story.KEEPER.subscribe(self.story_updated),
        ]

        # K1-00: every window works in a thread from threads.db. Without the store it
        # still chats, with an unsaved history.
        try:
            active = companions.waifu_of(ws)
            # warm_up_on_start off: opening the window must not load the model either
            await self.load_thread(
                await self.manager.open_initial(waifu_id=active.id if active else None),
                load=CONFIG.llm.warm_up_on_start,
            )
        except Exception as exc:  # noqa: BLE001 -- chat must still work without the store
            log.warning(f"threads store unavailable, this session is not saved: {exc}")
            self.thread = None

        # Every window has the loops and only the driver's act, so a window promoted
        # to driver keeps the screen companions running.
        self._loops = [asyncio.create_task(self._task_guide_loop()), asyncio.create_task(self._ocr_watch_loop())]

    async def _receive(self) -> Any:
        """The next message, or None once /shutdown asked every window to close.
        Raced against the shutdown event: an idle window would otherwise never notice."""
        receive = asyncio.create_task(self.ws.receive_json())
        shutdown = asyncio.create_task(hub.shutdown_event.wait())
        done, _ = await asyncio.wait({receive, shutdown}, return_when=asyncio.FIRST_COMPLETED)
        loser = receive if shutdown in done else shutdown
        loser.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loser
        return None if shutdown in done else receive.result()

    async def _close(self) -> None:
        self.pending_waifu = None   # nobody is left to switch for: no divider, no saved choice
        for unsubscribe in self._unsubscribe:
            unsubscribe()
        await hub.leave(self.ws)
        try:
            await self._wind_down()
        finally:
            hub.closed(self.ws)   # /shutdown waits for this, so the memory pass is not cut off

    async def _wind_down(self) -> None:
        # A turn still running when the window goes: cancel it, so the memory pass
        # below sees a settled transcript.
        if self.busy:
            self.turn.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self.turn
        await self.hush()
        if self.dictating is not None and not self.dictating.done():
            self.dictating.cancel()
        # The screen loops never end on their own. Their state (task_guide, ocr_watch)
        # is kernel-wide and outlives the window, so a reconnect finds the task.
        for loop in self._loops:
            loop.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await loop
        # Distill what this window added to the transcript into memory. Temp Chat turns
        # were logged with temp=True and are skipped. A kill mid-pass loses nothing:
        # the checkpoint moves only on commit and the startup pass redoes it.
        try:
            await writer.WRITER.run_pass("session_end")
        except Exception as exc:  # noqa: BLE001 -- a window closing must never wait on memory work
            log.warning(f"memory writer failed unexpectedly: {exc}")
        with contextlib.suppress(Exception):
            await self.ws.close()   # a no-op after a real disconnect

    async def _dispatch(self, raw: Any) -> None:
        try:
            msg = protocol.parse_client(raw)
        except protocol.ProtocolError as exc:
            reply_to = raw.get("id") if isinstance(raw, dict) else None
            await self.ws.send_json(protocol.error_frame(exc.code, exc.message, reply_to=reply_to))
            return
        # A switch asked for during a reply applies between turns (FR-S-2). start_turn
        # normally did it already; this catches one asked for while that ran.
        if self.pending_waifu and not self.busy:
            await self.apply_pending_switch()
        if msg.type in DRIVER_ONLY and not hub.drives(self.ws):
            await self.refuse("observer", "Another Kōkyū window is in charge of this conversation right now.")
            return
        await getattr(self, f"on_{msg.type}")(msg)

    # ── small helpers ───────────────────────────────────────────────────────

    @property
    def busy(self) -> bool:
        """A reply is in flight."""
        return self.turn is not None and not self.turn.done()

    async def hush(self) -> None:
        """Stop reading the last reply aloud (D-097), if she still is."""
        speech, self.speech = self.speech, None
        if speech is not None and not speech.done():
            speech.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await speech

    @property
    def thread_id(self) -> str | None:
        return self.thread.id if self.thread is not None else None

    async def refuse(self, code: str, message: str) -> None:
        await self.ws.send_json(protocol.error_frame(code, message))

    def thread_model(self) -> dict[str, str | None]:
        """The thread's model and effort, else the configured defaults (D-051)."""
        model_ref = self.thread.model_ref if self.thread is not None else None
        effort = self.thread.effort if self.thread is not None else None
        return {"model_ref": model_ref or CONFIG.chat.default_model_ref, "effort": effort or CONFIG.chat.default_effort}

    def thread_mode(self) -> str:
        """The open thread's conversation mode (FR-MODE-1); chat with no thread. From
        the thread only, never from the companion (FR-W-3, D-074)."""
        return str(conversation.prompt_layers(self.thread)["mode"])

    def in_roleplay(self) -> bool:
        return self.thread_mode() == "roleplay"

    def system_prompt(self, thread: Any = None) -> str:
        """history[0]: the window's companion's persona with the layers of `thread` (the
        open thread by default): its mode and scenario card (FR-MODE-2, D-074). The one
        builder wherever history[0] is set, so a regenerate, a reload or a companion
        switch never drops a roleplay back to chat. The mode comes from the thread only."""
        return companions.system_message(
            companions.waifu_of(self.ws), **conversation.prompt_layers(thread if thread is not None else self.thread)
        )

    def story_updated(self, thread_id: str, summary: str) -> None:
        """story.KEEPER saved a new summary; this window keeps it if the thread is open here."""
        if thread_id == self.thread_id:
            self.story_summary = summary

    def turn_story(self) -> str | None:
        """What run_turn gets as `story`: the summary of a roleplay thread outside Temp
        Chat, else None (FR-MODE-5, D-074). The mode comes from the thread only."""
        if not self.in_roleplay() or self.temp:
            return None
        return self.story_summary or None

    def keep_story(self, thread: Any) -> None:
        """A roleplay thread outside Temp Chat: ask story.KEEPER to catch its summary up
        in the background (FR-MODE-5). It runs only while the model is free."""
        if thread is not None and conversation.prompt_layers(thread)["mode"] == "roleplay" and not self.temp:
            story.KEEPER.schedule(thread.id, self.manager)

    def reset_history_flags(self) -> None:
        """temp_flags follows a rebuilt history; no remark is in it any more."""
        self.temp_flags[:] = [self.temp] * (len(self.history) - 1)
        self.unprompted.clear()

    async def send_thread_list(self, query: str = "") -> None:
        found = await (self.manager.search(query) if query.strip() else self.manager.list())
        await self.ws.send_json(protocol.frame("thread_list", {"query": query, "threads": [t.to_dict() for t in found]}))

    async def send_thread_updated(self) -> None:
        await self.ws.send_json(protocol.frame("thread_updated", {"thread": self.thread.to_dict()}, thread=self.thread.id))

    # ── threads and companions ──────────────────────────────────────────────

    async def load_thread(self, thread: Any, *, load: bool = True) -> None:
        """Makes `thread` this window's thread: its companion comes back, its messages
        become the history, its Temp Chat flag applies (FR-MEM-5). `load` False leaves
        its model unloaded until the first message."""
        await self.hush()   # the last thread's reply is not read over this one
        active = companions.waifu_of(self.ws)
        wanted = thread.active_waifu_id
        if wanted and self.registry.get(wanted) is not None and (active is None or active.id != wanted):
            await companions.apply_switch(
                self.ws, self.history, self.registry, wanted, **conversation.prompt_layers(thread)
            )
        elif not wanted and active is not None:
            thread = await asyncio.to_thread(self.manager.store.update_thread, thread.id, active_waifu_id=active.id)
        self.thread = thread
        self.history[:] = await self.manager.history(thread, self.system_prompt())
        self.temp = thread.temp
        self.reset_history_flags()
        # FR-MODE-5: the story so far, and a catch-up if the thread is behind.
        self.story_summary = ""
        if conversation.prompt_layers(thread)["mode"] == "roleplay":
            try:
                kept = await self.manager.story(thread.id)
                self.story_summary = kept.summary if kept is not None else ""
            except Exception as exc:  # noqa: BLE001 -- the story still plays without its summary
                log.warning(f"could not read the story summary: {exc}")
            self.keep_story(thread)
        await self.load_pins()
        await self.send_thread_messages()
        await self.send_thread_list()
        # K1-10: the thread's model loads after a short pause, so clicking through
        # threads does not start a load per click. Only the driver loads: an observer
        # opening a thread must not swap the model out from under the driver's reply.
        wanted_ref = model_listing.effective_ref(thread.model_ref, CONFIG)
        if load and hub.drives(self.ws) and boot.loads_without_asking(wanted_ref):
            model_loader.LOADER.request(wanted_ref, delay_s=CONFIG.chat.load_delay_s)
        await self.ws.send_json(protocol.frame("model_status", model_loader.LOADER.status()))

    async def send_thread_messages(self) -> None:
        """The open thread with all its messages, as the window shows it."""
        messages = await self.manager.messages(self.thread.id)
        await self.ws.send_json(
            protocol.frame(
                "thread_opened",
                {"thread": self.thread.to_dict(), "messages": [m.to_dict() for m in messages]},
                thread=self.thread.id,
            )
        )

    async def load_pins(self) -> None:
        """D-100: pins exist only in a roleplay; a chat thread has none."""
        self.pins = []
        if self.in_roleplay():
            try:
                self.pins = conversation.pin_lines(await self.manager.pins(self.thread.id))
            except Exception as exc:  # noqa: BLE001 -- the story still plays without its pins
                log.warning(f"could not read the pinned messages: {exc}")

    async def switch_companion(self, target_id: str) -> None:
        """A companion switch plus the thread's divider line (FR-S-2)."""
        before = companions.waifu_of(self.ws)
        target = await companions.apply_switch(
            self.ws, self.history, self.registry, target_id, **conversation.prompt_layers(self.thread)
        )
        if target is None or self.thread is None or (before is not None and before.id == target.id):
            return
        try:
            divider = await self.manager.record_companion_change(self.thread.id, companions.speaker_record(self.ws))
            await self.ws.send_json(protocol.frame("thread_message", {"message": divider.to_dict()}, thread=self.thread.id))
        except Exception as exc:  # noqa: BLE001 -- the switch itself already happened
            log.warning(f"could not record the companion change: {exc}")

    async def apply_pending_switch(self) -> None:
        target, self.pending_waifu = self.pending_waifu, None
        if target:
            await self.switch_companion(target)

    async def save_remark(self, text: str) -> None:
        """A screen companion's remark shows in the chat like a reply (FR-SC-2). It is
        stored flagged `ambient`, so a reloaded thread never hands it to a model: it
        came from a screen capture (FR-SC-3, FR-R-7)."""
        if self.thread is None:
            return
        try:
            remark = await self.manager.record_remark(self.thread.id, text, speaker=companions.speaker_record(self.ws))
            await self.ws.send_json(protocol.frame("thread_message", {"message": remark.to_dict()}, thread=self.thread.id))
        except Exception as exc:  # noqa: BLE001 -- the remark was already spoken
            log.warning(f"could not save a screen companion remark: {exc}")

    # ── turns ───────────────────────────────────────────────────────────────

    def saver(self, reply_meta: dict[str, Any] | None = None, line_meta: dict[str, Any] | None = None) -> Saver | None:
        """Stores the exchange in the thread the turn started in, and tells the window
        the stored messages before turn_done, so every message it shows has its id
        (D-100). `reply_meta` and `line_meta` carry a swipe's candidates and pins."""
        thread = self.thread
        if thread is None:
            return None

        async def save(user_text: str, reply: str, stopped: bool, meta: dict[str, Any]) -> None:
            meta = {**dict(meta), **(line_meta or {})}
            user, saved = await self.manager.record_exchange(
                thread.id,
                user_text,
                reply,
                speaker=companions.speaker_record(self.ws),
                model_ref=thread.model_ref or CONFIG.chat.default_model_ref,
                effort=thread.effort or CONFIG.chat.default_effort,
                stopped=stopped,
                tokens_in=meta.pop("tokens_in", None),
                tokens_out=meta.pop("tokens_out", None),
                meta=meta,
                reply_meta=reply_meta,
            )
            with contextlib.suppress(Exception):
                await self.ws.send_json(
                    protocol.frame(
                        "exchange_saved",
                        {"user": user.to_dict(), "reply": saved.to_dict() if saved is not None else None},
                        thread=thread.id,
                    )
                )
            await self.send_thread_list()
            # FR-MODE-5: fold older scenes once the model is free. The store's row
            # decides (story.KEEPER re-reads mode and Temp Chat), not this snapshot.
            if self.thread_id == thread.id:
                self.keep_story(self.thread)

        return save

    def replacing(
        self,
        old_ids: list[int],
        old_log_id: int | None,
        reply_meta: dict[str, Any] | None = None,
        line_meta: dict[str, Any] | None = None,
    ) -> Saver | None:
        """Regenerate's saver: the old exchange gives way only once a new reply exists,
        so a failure or a Stop before the first word loses nothing (K1-04)."""
        save = self.saver(reply_meta, line_meta)
        thread = self.thread
        if save is None or thread is None:
            return None

        async def replace(user_text: str, reply: str, stopped: bool, meta: dict[str, Any]) -> None:
            if not reply:
                # The thread keeps the old exchange, so the model's context gets it back too.
                self.history[:] = await self.manager.history(thread, self.system_prompt(thread))
                self.reset_history_flags()
                return
            await self.manager.delete_messages(old_ids)
            if old_log_id is not None:
                await turns.drop_transcript_turn(old_log_id)
            await save(user_text, reply, stopped, meta)

        return replace

    async def start_turn(self, user_text: str, *, on_finished: Saver | None, attachment: Any = None) -> None:
        """Runs a turn as its own task. A companion switch asked for during it applies
        the moment it ends, so the chip and the divider do not wait for the next message.
        The last reply stops being read aloud first (D-097)."""
        await self.hush()
        mode = self.thread_mode()
        turn = turns.run_turn(
            self.ws,
            self.history,
            user_text,
            self.temp,
            self.temp_flags,
            on_finished=on_finished,
            thread_id=self.thread_id,
            unprompted=self.unprompted,
            **({"attachment": attachment} if attachment is not None else {}),
            **self.thread_model(),
            mode=mode,
            story=self.turn_story(),
            pins=self.pins if mode == "roleplay" else None,
        )
        self.turn = asyncio.create_task(self._then_switch(turn, mode))

    async def _then_switch(self, turn: Coroutine[Any, Any, str], mode: str) -> None:
        try:
            reply = await turn
            if reply and read_aloud.READ_ALOUD.on:
                # D-097: read aloud once it has finished, in the voice of who wrote it
                # (taken now, before a switch asked for mid-reply applies below).
                voice = companions.voice_of(self.ws)
                await self.hush()   # a message read on request meanwhile gives way
                self.speech = asyncio.create_task(turns.speak_reply(self.ws, reply, mode, voice), name="read-aloud")
        finally:
            try:
                await self.apply_pending_switch()
            except Exception as exc:  # noqa: BLE001 -- a failed switch must not fail the turn or the teardown
                log.warning(f"companion switch after the reply failed: {exc}")

    # ── message handlers: one per protocol v1 client type ───────────────────

    async def on_hello(self, msg: Any) -> None:
        await self.ws.send_json(
            protocol.frame(
                "hello",
                {
                    "protocol": protocol.PROTOCOL_VERSION,
                    "kernel": "KASANE",
                    # what a thread with no model or effort of its own runs with (the chip shows it)
                    "default_model_ref": model_listing.default_ref(CONFIG),
                    "default_effort": CONFIG.chat.default_effort,
                },
                id=msg.id,
            )
        )

    async def on_send(self, msg: Any) -> None:
        if self.busy:
            return   # the window disables input during a reply; two turns would share one history
        await self.start_turn(msg.data.text, on_finished=self.saver())

    async def on_send_file(self, msg: Any) -> None:
        """The tray's Upload file (src/app/file-upload.ts reads and resizes it), turned
        into a user line. The caption goes on its own line, so the user's own words read
        as theirs next to the file's description."""
        if self.busy:
            return
        data = msg.data
        filename = data.filename or "uploaded file"
        if data.kind == "text":
            # Capped in the window too (file-upload.ts); capped again rather than trusted.
            shared = f'(shared a file, "{filename}") {data.content[:6000]}'
        else:
            prompt = "Describe what's in this image in a few sentences -- focus on what's actually visible, not a generic guess."
            try:
                description = await router.describe_image("vision", prompt, data.content)
            except llm.LLMUnreachableError as exc:
                log.warning(f"describe_image failed for upload: {exc}")
                await self.refuse("vision_unavailable", "Couldn't look at that image: the vision model isn't reachable.")
                # The window shows a turn since it sent the file; this ends it with no line.
                await self.ws.send_json(protocol.frame("turn_done", {"text": "", "stopped": False}, thread=self.thread_id))
                return
            shared = f'(shared an image, "{filename}") {description}'
        user_text = f"{shared}\n\n{data.caption}" if data.caption else shared
        await self.start_turn(user_text, on_finished=self.saver(), attachment=data.kind)

    async def on_regenerate(self, msg: Any) -> None:
        """K1-04 (FR-C-9): Regenerate the last reply, or Retry a failed turn. The new
        reply replaces the last exchange, so the user line is stored once."""
        if self.busy:
            await self.refuse("turn_running", BUSY)
            return
        if self.thread is None:
            await self.refuse("threads_unavailable", NO_THREADS)
            return
        found = await self.manager.last_exchange(self.thread.id)
        if found is None:
            await self.refuse("bad_message", "There is no reply to regenerate.")
            return
        again, old_ids, old_meta = found
        if msg.data.text is not None:
            # A file's line is the engine's words about the file: there is nothing to edit.
            if old_meta.get("attachment"):
                await self.refuse("bad_message", "A message with a file can't be edited. Send the file again instead.")
                return
            again = msg.data.text
        old_log_id = old_meta.get("log_id")
        # D-100: Regenerate is a swipe: the old reply stays as a candidate to swipe back
        # to. An edited line starts over. A pin stays on its line and on the reply.
        reply_meta: dict[str, Any] = {}
        old_reply = await self.manager.message(self.thread.id, old_ids[1]) if len(old_ids) == 2 else None
        if old_reply is not None and msg.data.text is None:
            reply_meta = conversation.next_swipe(old_reply)
        if old_reply is not None and old_reply.meta.get("pinned"):
            reply_meta["pinned"] = True
        line_meta = {"pinned": True} if old_meta.get("pinned") else None
        # Rebuilt from the thread without the old exchange, so a remark or a divider
        # after it cannot leave it in the model's context.
        self.history[:] = await self.manager.history(self.thread, self.system_prompt(), exclude=old_ids)
        self.reset_history_flags()
        await self.start_turn(
            again,
            on_finished=self.replacing(
                old_ids, old_log_id if isinstance(old_log_id, int) else None, reply_meta or None, line_meta
            ),
            attachment=old_meta.get("attachment"),
        )

    # ── message actions (D-100): rewind, swipe, pin, a new chat from here ──

    async def message_here(self, message_id: int) -> Any:
        """The open thread's message, or None after telling the window why."""
        found = await self.manager.message(self.thread.id, message_id) if self.thread is not None else None
        if found is None:
            await self.refuse("unknown_message", NO_MESSAGE)
        return found

    async def send_message_updated(self, message: Any) -> None:
        await self.ws.send_json(protocol.frame("message_updated", {"message": message.to_dict()}, thread=message.thread_id))

    async def on_message_rewind(self, msg: Any) -> None:
        """Rewind to here: every later message of the open thread is deleted. A chat
        exchange's transcript row goes too, so the memory writer never learns from it."""
        if self.busy:
            await self.refuse("turn_running", BUSY)
            return
        if await self.message_here(msg.data.id) is None:
            return
        await self.hush()
        story.KEEPER.preempt()   # a summary being written could reach past this point
        try:
            gone = await self.manager.rewind(self.thread.id, msg.data.id)
            for m in gone:
                log_id = m.meta.get("log_id")
                if isinstance(log_id, int):
                    await turns.drop_transcript_turn(log_id)
            await self.load_thread(self.thread, load=False)
        except Exception as exc:  # noqa: BLE001 -- report, keep the connection
            log.warning(f"rewind failed: {exc}")
            await self.refuse("threads_unavailable", NO_THREADS)

    async def on_message_swipe(self, msg: Any) -> None:
        """Shows another candidate of her latest reply; the model's history follows."""
        if self.busy:
            await self.refuse("turn_running", BUSY)
            return
        message = await self.message_here(msg.data.id)
        if message is None:
            return
        found = await self.manager.last_exchange(self.thread.id)
        if found is None or len(found[1]) != 2 or found[1][1] != message.id:
            await self.refuse("bad_message", "Only her latest reply can be swiped.")
            return
        try:
            shown = await self.manager.swipe_to(message, msg.data.to)
        except ValueError:
            await self.refuse("bad_message", "That reply is no longer there.")
            return
        await self.hush()
        self.history[:] = await self.manager.history(self.thread, self.system_prompt())
        self.reset_history_flags()
        await self.load_pins()
        await self.send_message_updated(shown)

    async def on_message_pin(self, msg: Any) -> None:
        """Pins exist only in a roleplay (D-100): a story's own memory, never the app's."""
        if not self.in_roleplay():
            await self.refuse("bad_message", "Pins are for roleplay stories.")
            return
        message = await self.message_here(msg.data.id)
        if message is None:
            return
        if message.role not in ("user", "assistant") or not message.content:
            await self.refuse("bad_message", "That line can't be pinned.")
            return
        if msg.data.on and not message.meta.get("pinned"):
            limit = CONFIG.story.max_pins
            if len(await self.manager.pins(self.thread.id)) >= limit:
                await self.refuse("pin_limit", f"A story can have {limit} pinned messages. Unpin one first.")
                return
        updated = await self.manager.set_pin(message, msg.data.on)
        await self.load_pins()
        await self.send_message_updated(updated)

    async def on_message_branch(self, msg: Any) -> None:
        """Start a new chat from here: a copy of the thread up to this message, in the
        same mode (a roleplay keeps its scenario card), opened in this window."""
        if await self.message_here(msg.data.id) is None:
            return

        async def branch() -> None:
            await self.load_thread(await self.manager.branch(self.thread.id, msg.data.id))

        await self._change_thread("message_branch", branch)

    async def on_stop(self, msg: Any) -> None:
        # Stop silences her too (FR-C-2): the reply being read aloud ends here.
        await self.hush()
        # Nothing running (a late click): nothing to do and nothing to say.
        if self.busy:
            self.turn.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.turn   # its turn_done says stopped

    async def on_switch_waifu(self, msg: Any) -> None:
        target_id = msg.data.id
        if self.registry.get(target_id) is None:
            await self.refuse("unknown_waifu", f"There is no companion called {target_id!r}.")
        elif self.busy:
            self.pending_waifu = target_id
            await companions.send_waifu_state(self.ws, self.registry, pending=target_id)
        else:
            self.pending_waifu = None
            await self.switch_companion(target_id)

    async def on_set_portrait(self, msg: Any) -> None:
        """Her picture (D-091, FR-W-9). App-level, not the conversation: any window may,
        mid-reply too. Every window hears the new roster."""
        data = msg.data
        if self.registry.get(data.waifu_id) is None:
            await self.refuse("unknown_waifu", f"There is no companion called {data.waifu_id!r}.")
            return
        try:
            raw = base64.b64decode(data.image_b64, validate=True) if data.image_b64 is not None else None
            await asyncio.to_thread(portrait.choose, data.waifu_id, raw)
        except (ValueError, binascii.Error):
            await self.refuse("picture_unreadable", "That file is not a picture Kōkyū can read. Try a PNG or JPEG.")
            return
        await hub.broadcast(protocol.frame("waifu_roster", {"waifus": self.registry.describe()}))

    async def on_set_temp(self, msg: Any) -> None:
        """Temp Chat (FR-MEM-5): saved with the thread, so it comes back when the thread
        is reopened. Only this window's conversation changes."""
        self.temp = msg.data.on
        if self.thread is not None:
            with contextlib.suppress(Exception):
                self.thread = await self.manager.set_temp(self.thread.id, self.temp) or self.thread
                await self.send_thread_updated()

    async def on_camera_frame(self, msg: Any) -> None:
        # The window's answer to camera.request_frame (K2-07 turns the camera on).
        camera.resolve_pending_frame(msg.data.image_b64)

    # Listing, searching and renaming are always allowed; changing which thread is
    # open waits for the reply (K1-00, FR-C-1).

    async def on_thread_list(self, msg: Any) -> None:
        await self.send_thread_list()

    async def on_thread_search(self, msg: Any) -> None:
        await self.send_thread_list(msg.data.query)

    async def on_thread_rename(self, msg: Any) -> None:
        renamed = await self.manager.rename(msg.data.id, msg.data.title)
        if renamed is None:
            await self.refuse("unknown_thread", GONE)
            return
        if self.thread is not None and renamed.id == self.thread.id:
            self.thread = renamed
        await self.send_thread_list()

    async def on_thread_pin(self, msg: Any) -> None:
        pinned = await self.manager.pin(msg.data.id, msg.data.on)
        if pinned is None:
            await self.refuse("unknown_thread", GONE)
            return
        if self.thread is not None and pinned.id == self.thread.id:
            self.thread = pinned
        await self.send_thread_list()

    async def on_thread_new(self, msg: Any) -> None:
        """A new thread in the mode asked for, fixed for its life (FR-MODE-1). It keeps
        the open thread's model and effort, but not its Temp Chat flag."""
        data = msg.data
        # Only the filled-in fields are kept; a chat thread has no scenario card, and a
        # blank roleplay has an empty one (FR-MODE-6).
        card = data.scenario.model_dump() if data.mode == "roleplay" and data.scenario is not None else {}
        scenario = {key: value for key, value in card.items() if value} or None

        if data.waifu_id is not None and self.registry.get(data.waifu_id) is None:
            await self.refuse("unknown_waifu", f"There is no companion called {data.waifu_id!r}.")
            return

        async def new() -> None:
            current = companions.waifu_of(self.ws)
            if data.waifu_id is not None and (current is None or current.id != data.waifu_id):
                # Persona and voice only (FR-W-3); load_thread rebuilds the history for the new thread.
                await companions.apply_switch(
                    self.ws, self.history, self.registry, data.waifu_id, **conversation.prompt_layers(self.thread)
                )
            active = companions.waifu_of(self.ws)
            thread = await self.manager.new_thread(
                waifu_id=active.id if active else None,
                model_ref=self.thread.model_ref if self.thread else None,
                effort=self.thread.effort if self.thread else None,
                mode=data.mode,
                scenario=scenario,
                title=(scenario or {}).get("title", ""),
            )
            # FR-MODE-6 (D-074): the card's opening line is her first message, shown by
            # thread_opened below. It stays out of the model's history; the scenario block
            # of the system message carries it.
            opening = (scenario or {}).get("opening")
            if opening:
                await self.manager.record_opening(thread.id, opening, speaker=companions.speaker_record(self.ws))
            await self.load_thread(thread)

        await self._change_thread("thread_new", new)

    # ── saved scenario cards (FR-MODE-6, D-074): app-level, any window ──────

    async def send_scenarios(self, saved_id: str | None = None) -> None:
        """The fresh list; the answer to a save also names the card it saved, so the
        dialog ties its pending save to this answer and not to any later list."""
        cards = await self.manager.scenarios()
        data: dict[str, Any] = {"cards": [c.to_dict() for c in cards]}
        if saved_id is not None:
            data["saved_id"] = saved_id
        await self.ws.send_json(protocol.frame("scenarios", data))

    async def _change_scenarios(self, what: str, change: Callable[[], Awaitable[Any]] | None = None) -> None:
        """Runs `change` (if any), then answers with the fresh list."""
        try:
            changed = await change() if change is not None else None
            await self.send_scenarios(changed.id if what == "scenario_save" else None)
        except Exception as exc:  # noqa: BLE001 -- report, keep the connection
            log.warning(f"scenario request {what} failed: {exc}")
            await self.refuse("threads_unavailable", NO_SCENARIOS)

    async def on_scenario_list(self, msg: Any) -> None:
        await self._change_scenarios("scenario_list")

    async def on_scenario_save(self, msg: Any) -> None:
        """Saves the card's filled-in fields; an empty title is named from its setting,
        else "Untitled scenario". Answered with the fresh list."""
        data = msg.data
        await self._change_scenarios(
            "scenario_save", lambda: self.manager.save_scenario(data.card.model_dump(), scenario_id=data.id)
        )

    async def on_scenario_delete(self, msg: Any) -> None:
        """Deleting a card leaves the threads started from it as they are. A card that is
        already gone is not an error: the fresh list answers either way."""
        await self._change_scenarios("scenario_delete", lambda: self.manager.delete_scenario(msg.data.id))

    async def on_thread_open(self, msg: Any) -> None:
        async def open_it() -> None:
            opened = await self.manager.open(msg.data.id)
            if opened is None:
                await self.refuse("unknown_thread", GONE)
            else:
                await self.load_thread(opened)

        await self._change_thread("thread_open", open_it)

    async def on_thread_delete(self, msg: Any) -> None:
        async def delete() -> None:
            await self.manager.delete(msg.data.id)
            if self.thread is not None and self.thread.id == msg.data.id:
                active = companions.waifu_of(self.ws)
                await self.load_thread(await self.manager.open_initial(waifu_id=active.id if active else None))
            else:
                await self.send_thread_list()

        await self._change_thread("thread_delete", delete)

    async def _change_thread(self, what: str, change: Callable[[], Awaitable[None]]) -> None:
        if self.busy:
            await self.refuse("turn_running", BUSY)
            return
        try:
            await change()
        except Exception as exc:  # noqa: BLE001 -- report, keep the connection
            log.warning(f"thread request {what} failed: {exc}")
            await self.refuse("threads_unavailable", NO_THREADS)

    # The model (K1-00c, K1-10; FR-M-1, 3, 4, 6, 7, 8)

    async def on_model_list(self, msg: Any) -> None:
        # The chip's popover. Read-only, any window.
        listed = await model_listing.model_list(router.get_router(), refresh=msg.data.refresh, cfg=CONFIG)
        await self.ws.send_json(protocol.frame("model_list", listed))

    # ── Settings (K1-13): the Doctor and the memory viewer ──────────────────
    # App-level, not about the conversation: any window may ask, observers too.

    async def on_doctor(self, msg: Any) -> None:
        """FR-SET-3: one row per component, each with a fix hint."""
        checks = await doctor.report(router.get_router())
        await self.ws.send_json(protocol.frame("doctor_report", {"checks": checks}))

    async def send_memory_facts(self) -> None:
        await self.ws.send_json(protocol.frame("memory_facts", {"facts": await memory_viewer.facts()}))

    async def on_memory_list(self, msg: Any) -> None:
        await self.send_memory_facts()

    async def on_memory_edit(self, msg: Any) -> None:
        """FR-MEM-4: the user's wording supersedes the fact (never a hard delete, FR-MEM-3)."""
        await memory_viewer.correct(msg.data.id, msg.data.text)
        await self.send_memory_facts()

    async def on_memory_forget(self, msg: Any) -> None:
        await memory_viewer.forget(msg.data.id)
        await self.send_memory_facts()

    async def on_memory_restore(self, msg: Any) -> None:
        await memory_viewer.restore(msg.data.id)
        await self.send_memory_facts()

    # ── Settings (K1-13b): what the user edits, in settings.json (D-070) ────

    async def on_settings_get(self, msg: Any) -> None:
        saved = await asyncio.to_thread(settings_file.read)
        await self.ws.send_json(protocol.frame("settings", settings_file.view(CONFIG, saved)))

    async def on_settings_set(self, msg: Any) -> None:
        """FR-SET-2 (D-070): only the keys sent change; saved to settings.json and
        applied with no restart. A refused value changes nothing and says why."""
        async with settings_file.LOCK:
            saved = await asyncio.to_thread(settings_file.read)
            try:
                updated = settings_file.change(saved, msg.data.model_dump(exclude_unset=True))
                cfg = await settings_file.save(updated)
            except Exception as exc:  # noqa: BLE001 - shown to the user, nothing applied
                problem = str(exc) if isinstance(exc, settings_file.SettingsError) else f"Not saved: {exc}"
                await self.ws.send_json(protocol.frame("settings", settings_file.view(CONFIG, saved, problem)))
                return
            rt = router.get_router()
            await rt.reconfigure(cfg)
        log.info(f"settings: saved {sorted(msg.data.model_dump(exclude_unset=True))} to {settings_file.path()}")
        await hub.broadcast(protocol.frame("settings", settings_file.view(cfg, updated)))
        await hub.broadcast(protocol.frame("model_list", await model_listing.model_list(rt, cfg=cfg)))

    async def on_model_load(self, msg: Any) -> None:
        # Try again after a failed load. Observers only watch; the driver never reloads mid-reply.
        if not hub.drives(self.ws):
            return
        if self.busy:
            await self.refuse("turn_running", BUSY)
            return
        model_loader.LOADER.request(
            model_listing.effective_ref(self.thread.model_ref if self.thread else None, CONFIG), force=True
        )

    async def on_model_unload(self, msg: Any) -> None:
        """K1-09b (SPEC §5, D-071): *Unload X* on the card of a load refused for
        graphics memory. Unloads that model, then tries the load again. Only a model
        the card offers; the driver only, never mid-reply."""
        if not hub.drives(self.ws):
            return
        if self.busy:
            await self.refuse("turn_running", BUSY)
            return
        status = model_loader.LOADER.status()
        if status["state"] != model_loader.FAILED or msg.data.ref not in {u["ref"] for u in status["unload"]}:
            await self.refuse("bad_message", "That model is not one the card offers to unload.")
            return
        try:
            await llm.unload_model(msg.data.ref.split("/", 1)[1])
        except Exception as exc:  # noqa: BLE001 -- the load below says what is still in the way
            log.warning(f"unloading {msg.data.ref} failed: {exc}")
        model_loader.LOADER.request(
            model_listing.effective_ref(self.thread.model_ref if self.thread else None, CONFIG), force=True
        )

    async def on_set_model(self, msg: Any) -> None:
        if self.thread is None:
            await self.refuse("threads_unavailable", NO_THREADS)
            return
        if self.busy:
            # Loading another model would pull the one answering out from under it.
            await self.refuse("turn_running", "Wait for the reply to finish, or press Stop, then switch models.")
            return
        # FR-M-11: effort is remembered per model in this thread. The old model's is
        # kept; the new one gets its own back, or its default the first time.
        old_ref = model_listing.effective_ref(self.thread.model_ref, CONFIG)
        new_ref = model_listing.effective_ref(msg.data.model_ref, CONFIG)
        efforts = {ref: e for ref, e in {**self.thread.efforts, old_ref: self.thread.effort}.items() if e is not None}
        self.thread = await asyncio.to_thread(
            self.manager.store.update_thread,
            self.thread.id,
            model_ref=msg.data.model_ref,
            effort=efforts.get(new_ref),
            efforts=efforts,
        )
        await self.send_thread_updated()
        if hub.drives(self.ws):
            # A pick loads at once; the chip shows the progress (FR-M-6).
            model_loader.LOADER.request(model_listing.effective_ref(self.thread.model_ref, CONFIG))

    async def on_set_context(self, msg: Any) -> None:
        """D-098: a model's Chat memory, for every thread, kept in settings.json. If it
        is the chat model in memory, it loads again with the new context now (the
        loading strip shows); otherwise it takes effect at its next load."""
        if not hub.drives(self.ws):
            return
        if self.busy:
            await self.refuse("turn_running", BUSY)
            return
        ref = msg.data.ref
        async with settings_file.LOCK:
            saved = await asyncio.to_thread(settings_file.read)
            try:
                cfg = await settings_file.save(settings_file.change(saved, {"context": {"ref": ref, "tokens": msg.data.tokens}}))
            except Exception as exc:  # noqa: BLE001 -- shown to the user, nothing applied
                await self.refuse("bad_message", f"Chat memory was not saved: {exc}")
                return
        log.info(f"chat memory: {ref} -> {context_fit.context_for(ref, cfg)} tokens")
        await asyncio.to_thread(vram.MEASURED.forget, ref)   # measured at the old context
        loader = model_loader.LOADER
        if ref.startswith("local:") and loader.model_ref == ref and loader.state != model_loader.IDLE:
            loader.request(ref, force=True)
        await hub.broadcast(protocol.frame("model_list", await model_listing.model_list(router.get_router(), cfg=cfg)))

    async def on_set_effort(self, msg: Any) -> None:
        if self.thread is None:
            await self.refuse("threads_unavailable", NO_THREADS)
            return
        await self._set_thread_field("effort", msg.data.effort)

    async def _set_thread_field(self, field_name: str, value: Any) -> None:
        """A per-thread setting (the effort), applied from the next turn on."""
        self.thread = await asyncio.to_thread(self.manager.store.update_thread, self.thread.id, **{field_name: value})
        await self.send_thread_updated()

    # Kernel-wide switches: only the driver changes them, every window sees them.

    async def on_read_aloud(self, msg: Any) -> None:
        """D-097: the composer's Read aloud, kept in settings.json. Turning it on
        starts the voice; every window sees it wake up."""
        if not hub.drives(self.ws):
            return
        if not msg.data.on:
            await self.hush()
        try:
            await read_aloud.READ_ALOUD.set(msg.data.on)
        except Exception as exc:  # noqa: BLE001 -- the switch stays as it was, and says why
            log.warning(f"read aloud: not saved: {exc}")
            await self.refuse("bad_message", f"Read aloud could not be saved: {exc}")

    # ── A message read on request (D-099): her speaker button ─────────────────

    async def on_speak_message(self, msg: Any) -> None:
        """Read one of her messages aloud now, Read aloud on or off, in the voice of the
        companion who said it (or the active one when she is not installed any more),
        cut by the thread's mode. Replaces whatever was being read."""
        await self.hush()
        data = msg.data
        speaker = self.registry.get(data.speaker_id) if data.speaker_id else None
        voice = companions.voice_for(speaker) if speaker is not None else companions.voice_of(self.ws)
        self.speech = asyncio.create_task(
            turns.speak_reply(self.ws, data.text, self.thread_mode(), voice, ref=data.ref), name="read-message"
        )

    async def on_speak_stop(self, msg: Any) -> None:
        """Stop reading aloud. A reply being written goes on (that is Stop's job)."""
        await self.hush()

    # ── Dictation (D-097): the mic button and its key fill the input box ────────

    async def on_dictate_start(self, msg: Any) -> None:
        """Recording began: load the speech model while the user talks (once per run,
        on the CPU). Best-effort and in the background: stt.preload never raises."""
        asyncio.create_task(stt.preload(), name="stt-preload")

    async def on_dictate(self, msg: Any) -> None:
        """Write a recording down for this window's input box. Any window may: it sends
        nothing. The audio stays on this PC and is not kept (invariant 3)."""
        if self.dictating is not None and not self.dictating.done():
            await self.send_dictation("", "Still writing down the last recording.")
            return
        try:
            audio = base64.b64decode(msg.data.audio_b64, validate=True)
        except (binascii.Error, ValueError):
            audio = b""
        if not audio:
            await self.send_dictation("", "That recording could not be read.")
            return
        self.dictating = asyncio.create_task(self._write_down(audio), name="dictation")

    async def _write_down(self, audio: bytes) -> None:
        try:
            text = await stt.transcribe(audio)
        except stt.STTError as exc:
            log.warning(f"dictation: speech to text failed: {exc}")
            await self.send_dictation("", "Speech to text failed. Settings → Doctor shows why.")
            return
        await self.send_dictation(text, None)

    async def send_dictation(self, text: str, error: str | None) -> None:
        with contextlib.suppress(Exception):   # the window may have closed meanwhile
            await self.ws.send_json(protocol.frame("dictation", {"text": text, "error": error}))

    async def on_screen_companion(self, msg: Any) -> None:
        """K1-05b (FR-SC-1..4, D-048): the + tray's Task Guide and OCR watch."""
        if not hub.drives(self.ws):
            return
        data = msg.data
        problem = await ambient.vision_problem() if data.on else None
        if problem:
            await self.refuse("vision_unavailable", problem)
            await self.ws.send_json(protocol.frame("screen_companions", hub.screen_status()))
            return
        if data.mode == "task_guide":
            task_guide.set_enabled(data.on)
            if data.on and data.task:
                task_guide.set_active_task(True, data.task)   # a new task replaces the old one
        else:
            ocr_watch.set_active(data.on)
        await hub.broadcast_screen_status()

    async def on_typing(self, msg: Any) -> None:
        ambient.note_typing()   # FR-SC-5: OCR watch keeps quiet

    # ── the screen companions' clocks (FR-SC-1..5) ──────────────────────────

    def _ambient_may_speak(self) -> bool:
        """Never during a reply (both would speak and share the history), never while
        the other screen companion speaks. Skipped, not deferred: the next poll decides."""
        return not self.busy and not self.ambient_lock.locked()

    def _ambient_still_in(self, thread_id: str | None) -> bool:
        """FR-MODE-9: the thread a screen check started in is still open and is not a
        story. A check takes seconds and the user may open a roleplay meanwhile
        (_change_thread does not wait for it); its remark is then dropped."""
        return self.thread_id == thread_id and not self.in_roleplay()

    def _ambient_hooks(self) -> dict[str, Any]:
        """still_valid and on_remark for one screen check, bound to the open thread."""
        started = self.thread_id

        async def on_remark(text: str) -> None:
            if self._ambient_still_in(started):
                await self.save_remark(text)

        return {"still_valid": lambda: self._ambient_still_in(started), "on_remark": on_remark}

    async def _task_guide_loop(self) -> None:
        while True:
            await asyncio.sleep(ambient.TASK_GUIDE_POLL_SECONDS)
            state = task_guide.get_state()
            if not state.active or not task_guide.enabled() or not hub.drives(self.ws):
                continue
            if self.in_roleplay():
                continue   # FR-MODE-9: no remark ever lands in a story
            if task_guide.is_idle(state, CONFIG.task_guide.idle_timeout_seconds):
                # Stepped away: the task ends quietly, nobody is there to hear a nudge.
                task_guide.clear_active_task()
                await hub.broadcast_screen_status()
                continue
            if not task_guide.due_for_check(state, CONFIG.task_guide.capture_interval_seconds):
                continue
            if not self._ambient_may_speak():
                continue
            async with self.ambient_lock:
                await ambient.run_task_guide_check(
                    self.ws, self.history, state.description, self.temp, self.temp_flags, self.unprompted,
                    **self._ambient_hooks(),
                )

    async def _ocr_watch_loop(self) -> None:
        pause_announced = False
        while True:
            await asyncio.sleep(ambient.OCR_WATCH_POLL_SECONDS)
            state = ocr_watch.get_state()
            if not state.active or not hub.drives(self.ws):
                pause_announced = False
                continue
            if self.in_roleplay():
                continue   # FR-MODE-9: no remark ever lands in a story
            paused = CONFIG.ocr_watch.pause_during_task and task_guide.get_state().active
            if paused and not pause_announced:
                # Said once: "OCR watch does nothing" was reported when a task paused it.
                log.info(
                    f"ocr watch: paused while Task Guide tracks '{task_guide.get_state().description}' "
                    "(ocr_watch.pause_during_task); it resumes when that task ends.",
                )
                pause_announced = True
            elif not paused and pause_announced:
                log.info("ocr watch: resumed (no task being tracked)")
                pause_announced = False
            if paused:
                # Task Guide already watches the screen; remarks on top of its nudges
                # doubled the vision calls. The first check after the task is a full
                # interval away.
                ocr_watch.defer_check()
                continue
            if not ocr_watch.due_for_check(state, CONFIG.ocr_watch.comment_interval_seconds):
                continue
            if ambient.typing_recently() or not self._ambient_may_speak():
                continue   # FR-SC-5: never talk over someone typing
            async with self.ambient_lock:
                await ambient.run_ocr_watch_check(
                    self.ws, self.history, self.temp, self.temp_flags, self.unprompted, **self._ambient_hooks()
                )
