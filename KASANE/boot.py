"""Kernel start-up (D-060). The port opens at once; the chat model, its helpers
and the memory catch-up pass wait for the first window, one at a time, so the
window paints on an idle PC. The voice starts after the chat model, and only
if Read aloud was left on (D-097). Also the stale-kernel takeover that runs
before the server binds its port.
"""

import asyncio
import contextlib
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import ambient
import companions
import conversation
import hub
import llm
import model_loader
import protocol
import router
import tools
import vram
import waifus
from audio import read_aloud
from config import CONFIG
from memory import embeddings, writer
from router import listing as model_listing
from router import model_ref as model_refs
from router.providers.llamacpp import helper_models, unload_ollama
from senses import ocr_watch, task_guide

log = logging.getLogger(__name__)


async def check_chat_model() -> None:
    # Capability report first (cheap, answers fast), then the warm-up load.
    await llm.report_model_capabilities()
    await warm_default_chat_model()


async def _last_thread() -> "conversation.Thread | None":
    """The thread the first window will land in, or None without the store."""
    try:
        return await conversation.get_manager().last_thread()
    except Exception as exc:  # noqa: BLE001 -- no store: the defaults
        log.warning(f"warm-up: threads store unavailable ({exc}); using the defaults")
        return None


async def boot_model_ref() -> str:
    """The model the first window will use: the last thread's choice, else the
    configured default (FR-M-5: new threads inherit the last selection)."""
    thread = await _last_thread()
    return model_listing.effective_ref(thread.model_ref if thread else None, CONFIG)


async def warm_up_prompt() -> tuple[list[dict[str, str]], list[dict]]:
    """The first message and tool list llama-server reads once at load (D-052): built
    by the same builder a turn uses, for the thread the first turn will run in (its
    mode and scenario, FR-MODE-2), so the cached prefix matches. A roleplay thread
    offers no tools (FR-MODE-4)."""
    thread = await _last_thread()
    registry = waifus.get_registry()
    waifu = registry.get(companions.load_active_id()) or registry.get(registry.default_id() or "")
    layers = conversation.prompt_layers(thread)
    system = companions.system_message(waifu, **layers)
    offered = [] if layers["mode"] == "roleplay" else tools.offered_schemas(already_looked=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": "(warm-up)"}], offered


def loads_without_asking(ref_text: str) -> bool:
    """D-060: llama.cpp models (a 21 GB file, two minutes, every CPU core) start
    only when the user picks one or sends a message to one, never at boot or on
    opening a thread. Ollama and API models load on their own."""
    try:
        return model_refs.parse(ref_text).provider != "llamacpp"
    except model_refs.ModelRefError:
        return False


async def warm_default_chat_model() -> None:
    """K1-01b (D-052), K1-10 (D-054): load the model the first message will use,
    through the model loader so every window sees "waking up" while it loads and
    a pick in the chip can cancel it. A llama.cpp model waits to be picked (D-060).
    Never raises."""
    if not CONFIG.llm.warm_up_on_start:
        return
    ref_text = await boot_model_ref()
    try:
        model_refs.parse(ref_text)
    except model_refs.ModelRefError as exc:
        log.warning(f"warm-up skipped: {ref_text!r} is not a usable model ({exc})")
        return
    if not loads_without_asking(ref_text):
        log.info(f"{ref_text} starts when it is picked or messaged (D-060)")
        return
    task = model_loader.LOADER.request(ref_text)
    if task is not None:
        # asyncio.wait, not await: a user's pick cancels this load, which is not an error here.
        await asyncio.wait({task})


async def load_chat_model(ref_text: str) -> None:
    """Loads a chat model so the next message starts at once (the loader's `warm`
    function). Raises when the load fails; the loader shows why.

    - llama.cpp: start `llama-server` for the preset (which unloads Ollama's chat
      model, keeping the helpers) and have it read the active persona with the
      last thread's mode layer, and that mode's tool list, once, so the first
      message reuses that prefix (D-052, FR-MODE-2).
    - Ollama: stop `llama-server` first: one large local model at a time (FR-M-6).
    - API: nothing to load.
    Then the small helper models that run before every reply.

    A local model that would not fit in VRAM beside the helpers is refused first,
    naming what holds the memory; the current model stays loaded (K1-09)."""
    ref = model_refs.parse(ref_text)
    rt = router.get_router()
    if ref.is_local:
        check = await model_listing.load_check(str(ref), rt)
        if check.fits is False:
            raise vram.VramFullError(check.message or "not enough graphics memory", can_unload(check.blockers))
    # D-072: only the picked model (and the embedding model) stays in memory.
    keep = helper_models()
    if ref.provider == "local_ollama":
        if await rt.stop_llamacpp():
            log.info("stopped llama-server: an Ollama chat model was picked")
        llm.ACTIVE_MODEL = ref.model
        await free_ollama(keep | {ref.model})
        await llm.load_model(ref.model)
        await warm_helpers()
        await vram.snapshot(lambda: llm.loaded_models())   # remembers what each model took
        return
    llm.ACTIVE_MODEL = ""
    if ref.provider != "llamacpp":
        # an API model: nothing to load, and the local models make room
        if await rt.stop_llamacpp():
            log.info("stopped llama-server: an API model was picked")
        await free_ollama(keep)
        return
    messages, offered = await warm_up_prompt()
    await rt.warm(str(ref), messages, offered)
    await warm_helpers()


def can_unload(blockers: tuple[vram.Resident, ...]) -> tuple[vram.Resident, ...]:
    """K1-09b (SPEC §5, D-071): the blockers *Unload X* may offer. Ollama models
    only, and not the embedding model: `warm_helpers` loads it again right after the
    chat model, so unloading it would make room for a moment. (The classifier was
    excluded too until D-072 stopped keeping it loaded.)"""
    again_refs = {vram.ollama_ref(CONFIG.memory.embedding.model)} if CONFIG.memory.embedding.model else set()
    return tuple(b for b in blockers if b.ref and b.ref.startswith("local:ollama/") and b.ref not in again_refs)


model_loader.LOADER.configure(
    # Looked up at call time, so tests can replace either function.
    warm=lambda ref: load_chat_model(ref),
    label=lambda ref: model_listing.label_for(ref, CONFIG),
    instant=lambda ref: ref.startswith("api:"),
)


async def free_ollama(keep: frozenset[str]) -> None:
    """D-072: every Ollama model but `keep` leaves memory. Best effort."""
    dropped = await unload_ollama(CONFIG.llm.base_url, keep=frozenset(n.removesuffix(":latest") for n in keep))
    if dropped:
        log.info(f"unloaded {', '.join(dropped)}: only the picked model stays loaded")


async def warm_helpers() -> None:
    """Recall embeds every message, so a cold embedding model would land on the
    first one (K1-01b). The classifier and memory writer run on the picked model
    now (D-072), so nothing else is warmed."""
    try:
        await embeddings.embed("warm-up")
    except Exception as exc:  # noqa: BLE001 -- recall reports its own failures per turn
        log.warning(f"warm-up of the embedding model failed: {exc}")


async def check_router() -> None:
    try:
        rt = router.get_router()
        cloud = await rt.startup()
        log.info(
            f"router: mode={rt.config.routing.mode} "
            f"cloud={'available' if cloud else 'local-only'} "
            f"catalog={len(rt.catalog.model_ids())} models",
        )
    except Exception as exc:  # noqa: BLE001 -- diagnostics must never stop startup
        log.warning(f"router startup skipped: {type(exc).__name__}: {exc}")


# Set by the first window that connects (D-060).
_first_window: asyncio.Event | None = None


def first_window_event() -> asyncio.Event:
    global _first_window
    if _first_window is None:
        _first_window = asyncio.Event()
    return _first_window


# Set once boot's chat-model step is over, loaded or failed (D-060): background model
# work that a window can start (story memory, FR-MODE-5) waits for it, like the
# memory writer's catch-up pass.
_chat_model_settled: asyncio.Event | None = None


def chat_model_settled_event() -> asyncio.Event:
    global _chat_model_settled
    if _chat_model_settled is None:
        _chat_model_settled = asyncio.Event()
    return _chat_model_settled


async def boot_sequence() -> None:
    """D-060: the kernel opens its port at once and loads nothing heavy until a
    window is up, so the window paints on an idle PC. Then the chat model, then the
    memory catch-up pass: loading everything together pegged every core and filled
    RAM. The voice starts only if Read aloud was left on (D-097), after the chat
    model. The router reads its cached catalog straight away (cheap). Never raises."""
    await asyncio.gather(check_router(), after_first_window(), return_exceptions=True)


async def after_first_window() -> None:
    await first_window_event().wait()
    for step in (check_chat_model, start_read_aloud, start_screen_companions, startup_memory_pass):
        try:
            await step()
        except Exception as exc:  # noqa: BLE001 -- one failed step must not stop the rest
            log.warning(f"boot step {step.__name__} failed: {type(exc).__name__}: {exc}")
        finally:
            if step is check_chat_model:
                chat_model_settled_event().set()


async def start_read_aloud() -> None:
    """D-097: Read aloud left on last time wakes the voice now (about 47 s), after the
    chat model, so the first reply can be spoken. Not awaited: the boot steps go on."""
    read_aloud.READ_ALOUD.start()


async def start_screen_companions() -> None:
    """FR-SC-1 (D-070): a screen companion set in Settings to start with Kōkyū turns
    on once a window is up, after the same vision check as the + tray (FR-SC-3).
    Without a local vision model it stays off and the window says why."""
    wanted = [mode for mode, on in (
        ("task_guide", CONFIG.task_guide.on_at_start),
        ("ocr_watch", CONFIG.ocr_watch.on_at_start),
    ) if on]
    if not wanted:
        return
    problem = await ambient.vision_problem()
    if problem:
        log.warning(f"screen companions not started: {problem}")
        await hub.broadcast(protocol.error_frame("vision_unavailable", problem))
        return
    if "task_guide" in wanted:
        task_guide.set_enabled(True)
    if "ocr_watch" in wanted:
        ocr_watch.set_active(True)
    log.info(f"screen companions on at start: {', '.join(wanted)}")
    await hub.broadcast_screen_status()


async def startup_memory_pass() -> None:
    try:
        await writer.WRITER.run_pass("startup")
    except Exception as exc:  # noqa: BLE001 -- memory work must never affect startup
        log.warning(f"memory catch-up pass failed: {exc}")


def pid_is_alive(pid: int) -> bool:
    """Cross-platform "is this PID still running" check -- the only thing
    _take_over_stale_kernel() below actually needs from the OS."""
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def take_over_stale_kernel(pid_file: Path) -> None:
    """Makes sure this process ends up as the *only* kernel running,
    no matter what launched it or how the previous one died.

    Found from the user's own terminal log, not anticipated up front:
    Ctrl+C on `npm run tauri dev` kills the Tauri parent via Windows'
    STATUS_CONTROL_C_EXIT before any of Tauri's own event handlers run --
    graceful_shutdown_then_kill() in src-tauri/src/lib.rs only ever fires from a tray-Quit click or
    a window-close event, neither of which happens on a raw terminal
    Ctrl+C. The kernel child process spawned underneath it is left
    running, still bound to PORT, with whatever history/state it had --
    so the next launch (however it happens: Tauri spawning a fresh child,
    a manually-run `python app.py`, or `npm run dev`) would otherwise either fail to bind the port
    at all, or -- more confusingly -- silently succeed while the frontend
    keeps talking to the same stale orphan the whole time, which is
    exactly what looked like "kernel.log showed old data" from the
    outside.

    Deliberately fixed here rather than on the Rust/Windows side:
    reliably intercepting a raw console Ctrl+C (as opposed to a
    window/tray event) is real, fiddly, hard-to-verify-without-a-Windows-
    machine territory -- see docs/DECISIONS.md. A plain PID-file takeover
    here is portable, was actually tested (simulating a stale orphaned
    process and confirming this detects and kills it -- see
    docs/DECISIONS.md), and is correct regardless of which of the three
    launch paths above is used, rather than needing each one to
    separately get shutdown-signal-handling right.
    """
    our_pid = os.getpid()
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            old_pid = None
        if old_pid is not None and old_pid != our_pid and pid_is_alive(old_pid):
            log.warning(f"found a stale kernel still running (pid {old_pid}) -- taking over")
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(old_pid), "/F"], capture_output=True)
            else:
                with contextlib.suppress(OSError):
                    os.kill(old_pid, signal.SIGTERM)
            # Give the OS a moment to actually free the port before we try
            # to bind it ourselves below.
            time.sleep(0.5)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(our_pid))
