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
import contextlib
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

import ambient
import boot
import companions
import conversation
import hub
import llm
import model_loader
import protocol
import router
import turns
import waifus
from audio import voice_mode
from config import CONFIG
from memory import writer
from router import listing as model_listing
from senses import camera, ocr_watch, task_guide

log = logging.getLogger(__name__)

# The turn's saver: (user line, reply, stopped, meta) -> stored in the thread.
Saver = Callable[[str, str, bool, dict[str, Any]], Awaitable[None]]

# Only the driving window may start a turn; another one is told why (D-062).
DRIVER_ONLY = frozenset({"send", "send_file", "regenerate"})

BUSY = "Wait for the reply to finish, or press Stop."
NO_THREADS = "Conversation history is unavailable right now."
GONE = "That conversation no longer exists."


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
        # The turn in flight runs as its own task, so the receive loop still reads Stop.
        self.turn: asyncio.Task | None = None
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
        await ws.send_json(protocol.frame("voice_status", voice_mode.VOICE.status()))

        # The active companion lives on the connection; it starts as the one the user
        # last used. With no packs installed it stays None and the fallback answers.
        ws.state.waifu = self.registry.get(companions.load_active_id()) or self.registry.get(
            self.registry.default_id() or ""
        )
        self.history = [{"role": "system", "content": companions.system_message(companions.waifu_of(ws))}]
        await companions.send_waifu_state(ws, self.registry)

        # Every window hears about model loads (K1-10, the waking-up card) and voice (D-061).
        async def push_model_status(status: dict[str, Any]) -> None:
            await ws.send_json(protocol.frame("model_status", status))

        async def push_voice_status(status: dict[str, Any]) -> None:
            await ws.send_json(protocol.frame("voice_status", status))

        self._unsubscribe = [
            model_loader.LOADER.subscribe(push_model_status),
            voice_mode.VOICE.subscribe(push_voice_status),
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
        active = companions.waifu_of(self.ws)
        wanted = thread.active_waifu_id
        if wanted and self.registry.get(wanted) is not None and (active is None or active.id != wanted):
            await companions.apply_switch(self.ws, self.history, self.registry, wanted)
        elif not wanted and active is not None:
            thread = await asyncio.to_thread(self.manager.store.update_thread, thread.id, active_waifu_id=active.id)
        self.thread = thread
        self.history[:] = await self.manager.history(thread, companions.system_message(companions.waifu_of(self.ws)))
        self.temp = thread.temp
        self.reset_history_flags()
        messages = await self.manager.messages(thread.id)
        await self.ws.send_json(
            protocol.frame(
                "thread_opened", {"thread": thread.to_dict(), "messages": [m.to_dict() for m in messages]}, thread=thread.id
            )
        )
        await self.send_thread_list()
        # K1-10: the thread's model loads after a short pause, so clicking through
        # threads does not start a load per click. Only the driver loads: an observer
        # opening a thread must not swap the model out from under the driver's reply.
        wanted_ref = model_listing.effective_ref(thread.model_ref, CONFIG)
        if load and hub.drives(self.ws) and boot.loads_without_asking(wanted_ref):
            model_loader.LOADER.request(wanted_ref, delay_s=CONFIG.chat.load_delay_s)
        await self.ws.send_json(protocol.frame("model_status", model_loader.LOADER.status()))

    async def switch_companion(self, target_id: str) -> None:
        """A companion switch plus the thread's divider line (FR-S-2)."""
        before = companions.waifu_of(self.ws)
        target = await companions.apply_switch(self.ws, self.history, self.registry, target_id)
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

    def saver(self) -> Saver | None:
        """Stores the exchange in the thread the turn started in."""
        thread = self.thread
        if thread is None:
            return None

        async def save(user_text: str, reply: str, stopped: bool, meta: dict[str, Any]) -> None:
            await self.manager.record_exchange(
                thread.id,
                user_text,
                reply,
                speaker=companions.speaker_record(self.ws),
                model_ref=thread.model_ref or CONFIG.chat.default_model_ref,
                effort=thread.effort or CONFIG.chat.default_effort,
                stopped=stopped,
                meta=meta,
            )
            await self.send_thread_list()

        return save

    def replacing(self, old_ids: list[int], old_log_id: int | None) -> Saver | None:
        """Regenerate's saver: the old exchange gives way only once a new reply exists,
        so a failure or a Stop before the first word loses nothing (K1-04)."""
        save = self.saver()
        thread = self.thread
        if save is None or thread is None:
            return None

        async def replace(user_text: str, reply: str, stopped: bool, meta: dict[str, Any]) -> None:
            if not reply:
                # The thread keeps the old exchange, so the model's context gets it back too.
                self.history[:] = await self.manager.history(thread, companions.system_message(companions.waifu_of(self.ws)))
                self.reset_history_flags()
                return
            await self.manager.delete_messages(old_ids)
            if old_log_id is not None:
                await turns.drop_transcript_turn(old_log_id)
            await save(user_text, reply, stopped, meta)

        return replace

    def start_turn(self, user_text: str, *, on_finished: Saver | None, attachment: Any = None) -> None:
        """Runs a turn as its own task. A companion switch asked for during it applies
        the moment it ends, so the chip and the divider do not wait for the next message."""
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
        )
        self.turn = asyncio.create_task(self._then_switch(turn))

    async def _then_switch(self, turn: Coroutine[Any, Any, None]) -> None:
        try:
            await turn
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
        self.start_turn(msg.data.text, on_finished=self.saver())

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
        self.start_turn(user_text, on_finished=self.saver(), attachment=data.kind)

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
        old_log_id = old_meta.get("log_id")
        # Rebuilt from the thread without the old exchange, so a remark or a divider
        # after it cannot leave it in the model's context.
        self.history[:] = await self.manager.history(
            self.thread, companions.system_message(companions.waifu_of(self.ws)), exclude=old_ids
        )
        self.reset_history_flags()
        self.start_turn(
            again,
            on_finished=self.replacing(old_ids, old_log_id if isinstance(old_log_id, int) else None),
            attachment=old_meta.get("attachment"),
        )

    async def on_stop(self, msg: Any) -> None:
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

    async def on_thread_new(self, msg: Any) -> None:
        async def new() -> None:
            active = companions.waifu_of(self.ws)
            await self.load_thread(
                await self.manager.new_thread(
                    waifu_id=active.id if active else None,
                    model_ref=self.thread.model_ref if self.thread else None,
                    effort=self.thread.effort if self.thread else None,
                )
            )

        await self._change_thread("thread_new", new)

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

    async def on_set_model(self, msg: Any) -> None:
        if self.thread is None:
            await self.refuse("threads_unavailable", NO_THREADS)
            return
        if self.busy:
            # Loading another model would pull the one answering out from under it.
            await self.refuse("turn_running", "Wait for the reply to finish, or press Stop, then switch models.")
            return
        await self._set_thread_field("model_ref", msg.data.model_ref)
        if hub.drives(self.ws):
            # A pick loads at once; the chip shows the progress (FR-M-6).
            model_loader.LOADER.request(model_listing.effective_ref(self.thread.model_ref, CONFIG))

    async def on_set_effort(self, msg: Any) -> None:
        if self.thread is None:
            await self.refuse("threads_unavailable", NO_THREADS)
            return
        await self._set_thread_field("effort", msg.data.effort)

    async def _set_thread_field(self, field_name: str, value: Any) -> None:
        """Per-thread model or effort, applied from the next turn on."""
        self.thread = await asyncio.to_thread(self.manager.store.update_thread, self.thread.id, **{field_name: value})
        await self.send_thread_updated()

    # Kernel-wide switches: only the driver changes them, every window sees them.

    async def on_voice_mode(self, msg: Any) -> None:
        # D-061: voice starts here, never at launch.
        if hub.drives(self.ws):
            await voice_mode.VOICE.set(msg.data.on)

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

    async def _task_guide_loop(self) -> None:
        while True:
            await asyncio.sleep(ambient.TASK_GUIDE_POLL_SECONDS)
            state = task_guide.get_state()
            if not state.active or not task_guide.enabled() or not hub.drives(self.ws):
                continue
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
                    on_remark=self.save_remark,
                )

    async def _ocr_watch_loop(self) -> None:
        pause_announced = False
        while True:
            await asyncio.sleep(ambient.OCR_WATCH_POLL_SECONDS)
            state = ocr_watch.get_state()
            if not state.active or not hub.drives(self.ws):
                pause_announced = False
                continue
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
                    self.ws, self.history, self.temp, self.temp_flags, self.unprompted, on_remark=self.save_remark
                )
