"""The open windows, and what every one of them hears (D-062).

Several windows can connect at once (the app window, a browser tab from
`npm run dev`). Only one may start turns, or two replies would play at once: the
first to connect drives, any other watches (surface_status, and an `observer`
error if it tries to send) until the driver leaves and the next one takes over.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import protocol
from senses import ocr_watch, task_guide

connections: set[Any] = set()
driver: Any = None
# Windows that have left but are still closing (their memory pass): /shutdown waits for them.
closing: set[Any] = set()

# Set by /shutdown. Every window's receive loop watches it and closes gracefully,
# so its memory pass runs before the process exits.
shutdown_event = asyncio.Event()


def join(websocket: Any) -> bool:
    """Registers a window. True when it drives (nobody else did)."""
    global driver
    connections.add(websocket)
    if driver is None:
        driver = websocket
    return driver is websocket


async def leave(websocket: Any) -> None:
    """A window is going. If it drove, another open one takes over and is told so;
    it keeps its own history (a promoted window does not inherit the conversation).
    The window counts as closing until `closed`."""
    global driver
    connections.discard(websocket)
    closing.add(websocket)
    if driver is websocket:
        driver = next(iter(connections), None)
        if driver is not None:
            with contextlib.suppress(Exception):
                await driver.send_json(protocol.frame("surface_status", {"role": "driver"}))


def closed(websocket: Any) -> None:
    """The window's close is done, memory pass included."""
    closing.discard(websocket)


def drives(websocket: Any) -> bool:
    return websocket is driver


async def broadcast(frame: dict[str, Any]) -> None:
    """Kernel-wide news (the model list, the screen companions) for every window."""
    for ws in list(connections):
        with contextlib.suppress(Exception):
            await ws.send_json(frame)


def screen_status() -> dict[str, Any]:
    """K1-05b (FR-SC-2): which screen companion is on, and Task Guide's task."""
    task = task_guide.get_state()
    return {
        "task_guide": {"on": task_guide.enabled(), "task": task.description if task.active else None},
        "ocr_watch": {"on": ocr_watch.get_state().active},
    }


async def broadcast_screen_status() -> None:
    """The state is kernel-wide, so every window's chip follows it."""
    await broadcast(protocol.frame("screen_companions", screen_status()))
