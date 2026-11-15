"""Settings -> Memory (K1-13, FR-MEM-4): the remembered facts, for the user to
read, correct and forget.

Memory is app-level and shared by every companion (FR-MEM-1), so nothing here
looks at a waifu. Nothing is hard-deleted (FR-MEM-3): a correction is a new fact
that supersedes the old one, and a forgotten fact keeps its row so it can be
restored. Facts that decayed or were replaced by the writer are not listed.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from memory import embeddings, migrate, store

log = logging.getLogger(__name__)

# shortcut: the newest 500 live facts, no paging; add paging when someone has more.
LIMIT = 500


def _view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "content": row["content"],
        "source": row["source"],
        "pinned": row["pinned"],
        "created_ts": row["created_ts"],
        "forgotten": row["superseded_by"] == migrate.FORGOTTEN,
    }


async def facts() -> list[dict[str, Any]]:
    """Live facts, newest first, then every fact the user forgot (restorable)."""
    rows = await asyncio.to_thread(store.get_fact_rows, include_superseded=True)
    live = [r for r in rows if r["superseded_by"] is None][:LIMIT]
    gone = [r for r in rows if r["superseded_by"] == migrate.FORGOTTEN]
    return [_view(r) for r in live + gone]


async def correct(fact_id: int, text: str) -> bool:
    """The user's wording replaces a live fact. False if there is nothing to correct."""
    old = await asyncio.to_thread(store.get_fact, fact_id)
    if old is None or old["superseded_by"] is not None or not text.strip() or text.strip() == old["content"]:
        return False
    new_id = await asyncio.to_thread(
        store.add_fact, text, source="correction", subject=old["subject"], pinned=old["pinned"]
    )
    if new_id is None:
        return False
    await asyncio.to_thread(store.supersede_fact, fact_id, new_id)
    await asyncio.to_thread(store.log_event, "user_correct", "user", {"old": fact_id, "new": new_id})
    try:
        vector = await embeddings.embed(text)
        await asyncio.to_thread(store.set_fact_vector, new_id, vector)
    except Exception as exc:  # noqa: BLE001 -- the writer pass backfills a missing vector
        log.warning(f"memory: the corrected fact waits for its vector: {type(exc).__name__}: {exc}")
    return True


async def forget(fact_id: int) -> None:
    await asyncio.to_thread(store.forget_facts, [fact_id])
    await asyncio.to_thread(store.log_event, "user_forget", "user", {"id": fact_id})


async def restore(fact_id: int) -> bool:
    """Brings back a fact the user forgot (not one a correction replaced)."""
    row = await asyncio.to_thread(store.get_fact, fact_id)
    if row is None or row["superseded_by"] != migrate.FORGOTTEN:
        return False
    restored = await asyncio.to_thread(store.restore_fact, fact_id)
    if restored:
        await asyncio.to_thread(store.log_event, "user_restore", "user", {"id": fact_id})
    return restored
