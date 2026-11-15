"""Kernel start-up (D-060). The port opens at once; the chat model, its helpers
and the memory catch-up pass wait for the first window, one at a time, so the
window paints on an idle PC. Voice is not part of boot (D-061). Also the
stale-kernel takeover that runs before the server binds its port.
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

import companions
import conversation
import llm
import model_loader
import router
import tools
import waifus
from config import CONFIG
from memory import embeddings, writer
from router import listing as model_listing
from router import model_ref as model_refs

log = logging.getLogger(__name__)


async def check_chat_model() -> None:
    # Capability report first (cheap, answers fast), then the warm-up load.
    await llm.report_model_capabilities()
    await warm_default_chat_model()


async def boot_model_ref() -> str:
    """The model the first window will use: the last thread's choice, else the
    configured default (FR-M-5: new threads inherit the last selection)."""
    thread = None
    try:
        thread = await conversation.get_manager().last_thread()
    except Exception as exc:  # noqa: BLE001 -- no store: the default model
        log.warning(f"warm-up: threads store unavailable ({exc}); using the default model")
    return model_listing.effective_ref(thread.model_ref if thread else None, CONFIG)


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
      model, keeping the helpers) and have it read the active persona and the
      tool list once, so the first message reuses that prefix (D-052).
    - Ollama: stop `llama-server` first: one large local model at a time (FR-M-6).
    - API: nothing to load.
    Then the small helper models that run before every reply."""
    ref = model_refs.parse(ref_text)
    rt = router.get_router()
    if ref.provider == "local_ollama":
        if await rt.stop_llamacpp():
            log.info("stopped llama-server: an Ollama chat model was picked")
        await llm.load_model(ref.model)
        await warm_helpers()
        return
    if ref.provider != "llamacpp":
        return
    registry = waifus.get_registry()
    waifu = registry.get(companions.load_active_id()) or registry.get(registry.default_id() or "")
    messages = [{"role": "system", "content": companions.system_message(waifu)}, {"role": "user", "content": "(warm-up)"}]
    await rt.warm(str(ref), messages, tools.offered_schemas(already_looked=False))
    await warm_helpers()


model_loader.LOADER.configure(
    # Looked up at call time, so tests can replace either function.
    warm=lambda ref: load_chat_model(ref),
    label=lambda ref: model_listing.label_for(ref, CONFIG),
    instant=lambda ref: ref.startswith("api:"),
)


async def warm_helpers() -> None:
    """The classifier runs before every reply and recall embeds every message, so
    a cold load of either lands on the first message (about 48 s measured,
    K1-01b). Loaded after the chat model, which unloads the rest of Ollama."""
    from router.decision import LOCAL_PROVIDER, model_for

    classifier = model_for(LOCAL_PROVIDER, "classifier", CONFIG.models)
    await llm.warm_up_model(classifier)
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


async def boot_sequence() -> None:
    """D-060: the kernel opens its port at once and loads nothing heavy until a
    window is up, so the window paints on an idle PC. Then the chat model, then the
    memory catch-up pass: loading everything together pegged every core and filled
    RAM. Voice is not part of boot at all; it starts when the user turns voice mode
    on (D-061). The router reads its cached catalog straight away (cheap). Never raises."""
    await asyncio.gather(check_router(), after_first_window(), return_exceptions=True)


async def after_first_window() -> None:
    await first_window_event().wait()
    for step in (check_chat_model, startup_memory_pass):
        try:
            await step()
        except Exception as exc:  # noqa: BLE001 -- one failed step must not stop the rest
            log.warning(f"boot step {step.__name__} failed: {type(exc).__name__}: {exc}")


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
