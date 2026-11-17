"""KASANE, the Kōkyū kernel: one FastAPI process on 127.0.0.1:8780 (D-027).

This module is the server only: the routes, the lifespan and the entry point (D-062).

- session.py     one Session per window, a handler per protocol v1 message type
- turns.py       one model turn, streamed; with Read aloud on, spoken once finished
- ambient.py     the screen companions (Task Guide, OCR watch)
- companions.py  a window's active companion: persona and voice, nothing more
- boot.py        model warm-up once a window is up (D-060), stale-kernel takeover
- hub.py         the open windows, which one drives, kernel-wide news

`/shutdown` lets the shell quit gracefully, so each window's memory pass runs
before the process ends. Loopback only: nothing here is reachable from another
machine (CLAUDE.md §3).
"""

import asyncio
import contextlib
import logging
import os
import sys
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import boot
import hub
import model_loader
import paths
import protocol
import router
import session
import settings_file
import shell_keys
import waifus
from audio import arbiter, read_aloud, tts
from config import CONFIG
from memory import writer
from router import listing as model_listing
from waifus import portrait

log = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORT = 8780

# Kōkyū's own pages: Vite on :1420 in development, the Tauri webview when packaged.
ALLOWED_ORIGINS = (
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
)


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Boot runs in the background (D-060), so the port opens at once. On the way out
    everything the kernel started stops with it."""
    # settings.json over config.yaml (FR-SET-2, D-070), before anything builds on it.
    await settings_file.apply_saved()
    boot_task = asyncio.create_task(boot.boot_sequence())
    if shell_keys.PIPE_ENABLED:
        # FR-R-6, D-059: a key saved or removed in the app arrives on stdin, live.
        shell_keys.start_reader(asyncio.get_running_loop(), apply_shell_key)
    # The memory writer never competes with a reply (it waits for the arbiter to be
    # idle); its catch-up pass after boot picks up anything a crash left unprocessed.
    writer.WRITER.configure(is_busy=lambda: arbiter.ARBITER.state != arbiter.IDLE)
    writer.WRITER.start()
    yield
    boot_task.cancel()
    await writer.WRITER.stop(final_pass=True)
    await read_aloud.READ_ALOUD.shutdown()
    tts.stop_server()
    # K1-01: a llama-server the router started must not outlive the kernel. A load
    # in progress is cancelled first, or it could start one after this.
    with contextlib.suppress(Exception):
        await model_loader.LOADER.stop()
    with contextlib.suppress(Exception):
        await router.get_router().shutdown()


app = FastAPI(lifespan=_lifespan)

# The page fetches each companion's .vrm from this kernel, which is a different
# origin. Loopback only, GET only, no credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_methods=["GET"],
    allow_headers=[],
)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    # A browser always sends Origin, so any other web page the user has open is
    # refused here (CORS does not cover websockets). Local programs that send none
    # (the tests) still connect.
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return
    await session.Session(websocket).run()


@app.get("/waifus/{waifu_id}/vrm")
async def waifu_vrm(waifu_id: str) -> FileResponse:
    """The avatar file of a known companion. The id is looked up in the registry; the
    path comes from the validated pack, never from the request."""
    waifu = waifus.get_registry().get(waifu_id)
    if waifu is None:
        raise HTTPException(status_code=404, detail="unknown companion")
    return FileResponse(waifu.vrm_path, media_type="model/gltf-binary")


@app.get("/waifus/{waifu_id}/portrait")
async def waifu_portrait(waifu_id: str) -> FileResponse:
    """Her face (D-091, FR-W-8): the picture the user chose, else the VRM's thumbnail
    scaled down. 404 when she has neither; the window then shows her initial. The URL
    carries a version (`?v=`), so the browser may keep it."""
    waifu = waifus.get_registry().get(waifu_id)
    if waifu is None:
        raise HTTPException(status_code=404, detail="unknown companion")
    path = await asyncio.to_thread(portrait.portrait_file, waifu)
    if path is None:
        raise HTTPException(status_code=404, detail="no portrait")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "max-age=31536000, immutable"})


async def apply_shell_key(provider_id: str, key: str | None) -> None:
    """The shell saved or removed an API key: point the router at it and show every
    window the new list (D-059). Logs the provider id only, never the key."""
    rt = router.get_router()
    usable = await rt.use_app_key(provider_id, key)
    log.info(
        f"keys: {provider_id} key {'saved' if key else 'removed'} in the app; "
        f"API models {'usable' if usable else 'not usable yet'} ({rt.api_status()['label']})",
    )
    await hub.broadcast(protocol.frame("model_list", await model_listing.model_list(rt, cfg=CONFIG)))


@app.post("/shutdown")
async def shutdown_endpoint() -> dict:
    """The shell's tray Quit asks here first, and kills the process only if this
    does not finish in time (src-tauri/src/lib.rs).

    Sets hub.shutdown_event: every window's receive loop notices, and its session
    closes the normal way, memory pass included. This waits a bounded time for them,
    then exits the process itself. `os._exit` rather than uvicorn's graceful drain:
    a single-user desktop app needs a bounded, explicit teardown, not a drain.
    """
    hub.shutdown_event.set()

    # 50 x 100 ms = 5 s, the grace period the shell waits before its hard kill.
    # Too short for a slow memory pass is a mismatch to fix on both sides together.
    for _ in range(50):
        if not hub.connections and not hub.closing:
            break
        await asyncio.sleep(0.1)

    # K1-01: os._exit below skips the lifespan teardown, so stop the llama-server
    # child here or it outlives the kernel (and holds ~20 GB of RAM and its port).
    # Bounded: Tauri's Job Object is the backstop.
    with contextlib.suppress(Exception):
        await model_loader.LOADER.stop()
    with contextlib.suppress(Exception):
        await asyncio.wait_for(router.get_router().shutdown(), timeout=8)
    with contextlib.suppress(Exception):
        await read_aloud.READ_ALOUD.shutdown()
        tts.stop_server()

    sys.stdout.flush()
    sys.stderr.flush()
    # Slightly after this returns, so uvicorn still sends the response.
    asyncio.get_event_loop().call_later(0.1, lambda: os._exit(0))
    return {"status": "shutting down"}


if __name__ == "__main__":
    import uvicorn

    # One line per event on stderr; the shell writes it to logs/kasane.log (R-13).
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)

    from memory import db as memory_db

    boot.take_over_stale_kernel(paths.logs_dir() / "kernel.pid")
    # Cheap, once per start: a changed embedding model is caught here, not mid-turn.
    memory_db.check_embedding_dimension_matches()

    uvicorn.run(app, host=HOST, port=PORT)
