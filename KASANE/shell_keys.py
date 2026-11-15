"""API keys the desktop shell hands over (FR-R-6, D-059).

At spawn the shell puts the saved key in `KOKYU_API_KEYS` (JSON `{id: key}`); this
module takes it out of the environment at import, before anything can start a
child process. A key saved or removed later arrives as one JSON line on stdin
(`{"provider": id, "key": key | null}`) when `KOKYU_KEY_PIPE=1`.

Keys live only in this module's memory. Nothing here logs a key, or a line that
might hold one. Not named `secrets.py`: KASANE/ is on sys.path and would shadow
the standard library module.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from typing import Any, Awaitable, BinaryIO, Callable

from provider_presets import PROVIDER_ID

log = logging.getLogger(__name__)

_keys: dict[str, str] = {}
PIPE_ENABLED = False
MAX_LINE = 4096


def valid_key(key: Any) -> bool:
    """8 to 1024 printable ASCII characters, no spaces: what an API key looks like."""
    return isinstance(key, str) and 8 <= len(key) <= 1024 and all("\x21" <= ch <= "\x7e" for ch in key)


def take_from_environ() -> None:
    """Move the shell's keys out of the environment (children must not inherit them)."""
    global PIPE_ENABLED
    raw = os.environ.pop("KOKYU_API_KEYS", None)
    PIPE_ENABLED = os.environ.pop("KOKYU_KEY_PIPE", None) == "1"
    if not raw:
        return
    try:
        handed = json.loads(raw)
    except ValueError:
        handed = None
    if not isinstance(handed, dict):
        log.warning("keys: ignored the keys from the shell (not readable)")
        return
    for provider, key in handed.items():
        if isinstance(provider, str) and PROVIDER_ID.match(provider) and valid_key(key):
            _keys[provider] = key


def get(provider: str | None) -> str | None:
    return _keys.get(provider) if provider else None


def app_provider() -> str | None:
    """The provider of the key saved in the app (one at a time, D-059)."""
    return next(iter(_keys), None)


def set(provider: str, key: str | None) -> None:  # noqa: A001 -- module API: shell_keys.set
    """One key at a time: a new one replaces any other; None removes this one."""
    if key is None:
        _keys.pop(provider, None)
        return
    _keys.clear()
    _keys[provider] = key


def clear() -> None:
    _keys.clear()


def parse_line(raw: bytes) -> tuple[str, str | None] | None:
    """`(provider, key or None)` from one pipe line, or None when it is not one."""
    if len(raw) > MAX_LINE:
        return None
    try:
        message = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(message, dict):
        return None
    provider, key = message.get("provider"), message.get("key")
    if not isinstance(provider, str) or not PROVIDER_ID.match(provider):
        return None
    if key is not None and not valid_key(key):
        return None
    return provider, key


def start_reader(
    loop: asyncio.AbstractEventLoop,
    apply: Callable[[str, str | None], Awaitable[None]],
    stream: BinaryIO | None = None,
) -> threading.Thread:
    """Read key lines off the event loop and hand each to `apply` on the loop."""
    # Unbuffered and separate from sys.stdin: a daemon thread blocked in
    # sys.stdin.buffer holds its lock, and any normal exit (say, port 8780 taken)
    # then dies with "Fatal Python error: _enter_buffered_busy".
    source = stream if stream is not None else open(sys.stdin.fileno(), "rb", buffering=0, closefd=False)

    def run() -> None:
        while True:
            try:
                raw = source.readline(MAX_LINE + 1)
            except (OSError, ValueError):
                return
            if not raw:
                return   # EOF: the shell went away
            if not raw.strip():
                continue
            parsed = parse_line(raw.strip())
            if parsed is None:
                log.warning("keys: ignored a line from the shell that was not a key message")
                continue
            future = asyncio.run_coroutine_threadsafe(apply(*parsed), loop)
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001 -- one bad change must not stop the reader
                log.warning(f"keys: applying a key change failed: {type(exc).__name__}")

    thread = threading.Thread(target=run, name="kokyu-key-pipe", daemon=True)
    thread.start()
    return thread


take_from_environ()
