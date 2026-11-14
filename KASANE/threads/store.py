"""SQLite threads store (`threads.db`, SPEC §3.5; FR-C-1, FR-C-10, FR-MEM-5).

The chat history the user sees: threads, their messages, attachments. Memory
(`memory.db`) is a separate database and is never touched from here.

Plain synchronous sqlite3 on purpose: every call is short, and the async side
(`conversation.py`) runs them through `asyncio.to_thread` so the kernel's event
loop is never blocked (RULES: never block the loop). One connection per call
keeps it safe across threads; WAL mode lets the UI read while a turn writes.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1
TITLE_MAX = 80
SEARCH_LIMIT = 50

ROLES = ("user", "assistant", "divider")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    active_waifu_id TEXT,
    model_ref       TEXT,
    effort          TEXT,
    temp            INTEGER NOT NULL DEFAULT 0,
    archived        INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id        TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    ts               REAL NOT NULL,
    role             TEXT NOT NULL,
    speaker_waifu_id TEXT,
    speaker_name     TEXT,
    content          TEXT NOT NULL DEFAULT '',
    model_ref        TEXT,
    effort           TEXT,
    tokens_in        INTEGER,
    tokens_out       INTEGER,
    meta             TEXT
);
CREATE INDEX IF NOT EXISTS messages_thread ON messages(thread_id, id);
CREATE TABLE IF NOT EXISTS attachments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,
    path       TEXT NOT NULL,
    mime       TEXT,
    size       INTEGER
);
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@dataclass(frozen=True)
class Thread:
    id: str
    title: str
    created_at: float
    updated_at: float
    active_waifu_id: str | None = None
    model_ref: str | None = None
    effort: str | None = None
    temp: bool = False
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "active_waifu_id": self.active_waifu_id,
            "model_ref": self.model_ref,
            "effort": self.effort,
            "temp": self.temp,
            "archived": self.archived,
        }


@dataclass(frozen=True)
class Message:
    id: int
    thread_id: str
    ts: float
    role: str
    content: str
    speaker_waifu_id: str | None = None
    speaker_name: str | None = None
    model_ref: str | None = None
    effort: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "ts": self.ts,
            "role": self.role,
            "content": self.content,
            "speaker_waifu_id": self.speaker_waifu_id,
            "speaker_name": self.speaker_name,
            "model_ref": self.model_ref,
            "effort": self.effort,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "meta": dict(self.meta),
        }


class ThreadNotFound(KeyError):
    pass


def title_from(text: str) -> str:
    """A thread's automatic title: the first line of the first user message, trimmed."""
    line = " ".join(text.strip().split())
    if len(line) <= TITLE_MAX:
        return line
    return line[: TITLE_MAX - 1].rstrip() + "…"


def _thread(row: sqlite3.Row) -> Thread:
    return Thread(
        id=row["id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        active_waifu_id=row["active_waifu_id"],
        model_ref=row["model_ref"],
        effort=row["effort"],
        temp=bool(row["temp"]),
        archived=bool(row["archived"]),
    )


def _message(row: sqlite3.Row) -> Message:
    try:
        meta = json.loads(row["meta"]) if row["meta"] else {}
    except json.JSONDecodeError:
        meta = {}
    return Message(
        id=row["id"],
        thread_id=row["thread_id"],
        ts=row["ts"],
        role=row["role"],
        content=row["content"],
        speaker_waifu_id=row["speaker_waifu_id"],
        speaker_name=row["speaker_name"],
        model_ref=row["model_ref"],
        effort=row["effort"],
        tokens_in=row["tokens_in"],
        tokens_out=row["tokens_out"],
        meta=meta if isinstance(meta, dict) else {},
    )


class ThreadStore:
    def __init__(self, db_path: Path, clock: Any = time.time) -> None:
        self.db_path = Path(db_path)
        self._clock = clock
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(_SCHEMA)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _now(self) -> float:
        return float(self._clock())

    # -- threads ---------------------------------------------------------------

    def create_thread(
        self,
        *,
        title: str = "",
        active_waifu_id: str | None = None,
        model_ref: str | None = None,
        effort: str | None = None,
        temp: bool = False,
    ) -> Thread:
        now = self._now()
        thread_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute(
                "INSERT INTO threads (id, title, created_at, updated_at, active_waifu_id, model_ref, effort, temp)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (thread_id, title_from(title), now, now, active_waifu_id, model_ref, effort, int(temp)),
            )
        return self.get_thread(thread_id)

    def get_thread(self, thread_id: str) -> Thread:
        with self._connect() as db:
            row = db.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
        if row is None:
            raise ThreadNotFound(thread_id)
        return _thread(row)

    def find_thread(self, thread_id: str) -> Thread | None:
        try:
            return self.get_thread(thread_id)
        except ThreadNotFound:
            return None

    def list_threads(self, *, limit: int = 200, include_archived: bool = False) -> list[Thread]:
        sql = "SELECT * FROM threads"
        if not include_archived:
            sql += " WHERE archived = 0"
        sql += " ORDER BY updated_at DESC, created_at DESC LIMIT ?"
        with self._connect() as db:
            return [_thread(r) for r in db.execute(sql, (limit,)).fetchall()]

    def update_thread(self, thread_id: str, **fields: Any) -> Thread:
        """Sets any of: title, active_waifu_id, model_ref, effort, temp, archived.
        Settings changes do not reorder the history list (updated_at is for messages)."""
        allowed = {"title", "active_waifu_id", "model_ref", "effort", "temp", "archived"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown thread fields: {sorted(unknown)}")
        if not fields:
            return self.get_thread(thread_id)
        values: dict[str, Any] = dict(fields)
        if "title" in values:
            values["title"] = title_from(str(values["title"] or ""))
        for flag in ("temp", "archived"):
            if flag in values:
                values[flag] = int(bool(values[flag]))
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self._connect() as db:
            cur = db.execute(f"UPDATE threads SET {assignments} WHERE id = ?", (*values.values(), thread_id))
            if cur.rowcount == 0:
                raise ThreadNotFound(thread_id)
        return self.get_thread(thread_id)

    def rename(self, thread_id: str, title: str) -> Thread:
        return self.update_thread(thread_id, title=title)

    def delete_thread(self, thread_id: str) -> bool:
        with self._connect() as db:
            cur = db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            if self.get_kv("last_thread", db=db) == thread_id:
                db.execute("DELETE FROM kv WHERE key = 'last_thread'")
        return cur.rowcount > 0

    def search(self, query: str, *, limit: int = SEARCH_LIMIT) -> list[Thread]:
        """Threads whose title or any message contains `query` (case-insensitive), newest first."""
        needle = query.strip()
        if not needle:
            return self.list_threads(limit=limit)
        pattern = "%" + needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql = (
            "SELECT * FROM threads WHERE archived = 0 AND ("
            " title LIKE ? ESCAPE '\\' OR id IN ("
            "  SELECT thread_id FROM messages WHERE role != 'divider' AND content LIKE ? ESCAPE '\\'))"
            " ORDER BY updated_at DESC LIMIT ?"
        )
        with self._connect() as db:
            return [_thread(r) for r in db.execute(sql, (pattern, pattern, limit)).fetchall()]

    # -- messages --------------------------------------------------------------

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        *,
        speaker_waifu_id: str | None = None,
        speaker_name: str | None = None,
        model_ref: str | None = None,
        effort: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Message:
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, not {role!r}")
        now = self._now()
        with self._connect() as db:
            row = db.execute("SELECT title FROM threads WHERE id = ?", (thread_id,)).fetchone()
            if row is None:
                raise ThreadNotFound(thread_id)
            cur = db.execute(
                "INSERT INTO messages (thread_id, ts, role, speaker_waifu_id, speaker_name, content,"
                " model_ref, effort, tokens_in, tokens_out, meta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    thread_id, now, role, speaker_waifu_id, speaker_name, content,
                    model_ref, effort, tokens_in, tokens_out,
                    json.dumps(meta) if meta else None,
                ),
            )
            message_id = cur.lastrowid
            if role != "divider":
                db.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, thread_id))
            if role == "user" and not row["title"]:
                db.execute("UPDATE threads SET title = ? WHERE id = ?", (title_from(content), thread_id))
            out = db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return _message(out)

    def messages(self, thread_id: str, *, limit: int | None = None) -> list[Message]:
        """Messages in order. With `limit`, the most recent `limit` messages, still in order."""
        with self._connect() as db:
            if limit is None:
                rows = db.execute(
                    "SELECT * FROM messages WHERE thread_id = ? ORDER BY id", (thread_id,)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM (SELECT * FROM messages WHERE thread_id = ? ORDER BY id DESC LIMIT ?)"
                    " ORDER BY id",
                    (thread_id, limit),
                ).fetchall()
        return [_message(r) for r in rows]

    def add_attachment(self, message_id: int, kind: str, path: str, mime: str | None = None, size: int | None = None) -> int:
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO attachments (message_id, kind, path, mime, size) VALUES (?, ?, ?, ?, ?)",
                (message_id, kind, path, mime, size),
            )
            return int(cur.lastrowid)

    # -- small key/value (last opened thread) ----------------------------------

    def get_kv(self, key: str, *, db: sqlite3.Connection | None = None) -> str | None:
        if db is not None:
            row = db.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None
        with self._connect() as conn:
            return self.get_kv(key, db=conn)

    def set_kv(self, key: str, value: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
