"""Ollama started when a model needs it (D-105).

Picking an Ollama model, or the boot warm-up of one, used to fail with "Ollama is
not running" when its service was down. `ensure` asks Ollama first (one GET);
only when nothing answers on a local address does it start `ollama serve` and wait
for it. Started from the kernel, it is the kernel's child, so the shell's Job
Object ends it with the app (llama.cpp's server is started by its provider the
same way). Never raises: a failure is the ordinary "not running" the load shows.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx

log = logging.getLogger("kokyu.ollama")

WAIT_S = 20.0
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_lock = asyncio.Lock()


async def is_up(base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> bool:
    try:
        async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(3.0, connect=1.0)) as client:
            return (await client.get(f"{base_url.rstrip('/')}/api/version")).status_code < 400
    except httpx.HTTPError:
        return False


def find_exe() -> Path | None:
    """Ollama's CLI: on PATH, else where its Windows installer puts it."""
    found = shutil.which("ollama")
    if found:
        return Path(found)
    local = os.environ.get("LOCALAPPDATA")
    candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe" if local else None
    return candidate if candidate is not None and candidate.is_file() else None


def spawn(exe: Path) -> None:
    """`ollama serve` in the background, no console window. Blocking: a thread."""
    subprocess.Popen(  # noqa: S603 -- a local, found executable with a fixed argument
        [str(exe), "serve"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


async def ensure(base_url: str, *, wait_s: float = WAIT_S, poll_s: float = 0.5) -> bool:
    """True when Ollama answers, starting it first if it is local and down."""
    if await is_up(base_url):
        return True
    if (urlparse(base_url).hostname or "") not in _LOCAL_HOSTS:
        return False   # someone else's server: never ours to start
    async with _lock:   # two loads at once start it once
        if await is_up(base_url):
            return True
        exe = find_exe()
        if exe is None:
            log.warning("Ollama is not running and is not installed where Kokyu looks")
            return False
        log.info(f"Ollama is not running: starting {exe} serve")
        try:
            await asyncio.to_thread(spawn, exe)
        except OSError as exc:
            log.warning(f"could not start Ollama: {exc}")
            return False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_s
        while loop.time() < deadline:
            await asyncio.sleep(poll_s)
            if await is_up(base_url):
                log.info("Ollama is up")
                return True
        log.warning(f"Ollama did not answer within {wait_s:.0f} s of starting")
        return False
