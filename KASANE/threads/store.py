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

SCHEMA_VERSION = 7   # 2: threads.efforts (FR-M-11); 3: threads.mode and threads.scenario (FR-MODE-1, D-074);
                     # 4: the story_memory table (FR-MODE-5, D-074); 5: the scenarios table (FR-MODE-6, D-074);
                     # 6: threads.pinned (UI1-09, D-094); 7: threads.note, a roleplay's Memory (D-101)
TITLE_MAX = 80
SEARCH_LIMIT = 50
# FR-MODE-6: what a saved card is called when its title was left empty and it has no setting.
UNTITLED_SCENARIO = "Untitled scenario"

ROLES = ("user", "assistant", "divider")
# FR-MODE-1 (D-074): what kind of conversation a thread is, fixed when it is created.
MODES = ("chat", "roleplay")

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
    archived        INTEGER NOT NULL DEFAULT 0,
    efforts         TEXT,
    mode            TEXT NOT NULL DEFAULT 'chat',
    scenario        TEXT,
    pinned          INTEGER NOT NULL DEFAULT 0,
    note            TEXT NOT NULL DEFAULT ''
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
CREATE TABLE IF NOT EXISTS story_memory (
    thread_id          TEXT PRIMARY KEY REFERENCES threads(id) ON DELETE CASCADE,
    summary            TEXT NOT NULL DEFAULT '',
    through_message_id INTEGER NOT NULL DEFAULT 0,
    updated_at         REAL
);
CREATE TABLE IF NOT EXISTS scenarios (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    card       TEXT NOT NULL,
    created_at REAL,
    updated_at REAL
);
"""

# Columns added after schema 1, checked on every start (PRAGMA user_version is
# written but never read: the checks are the migration, and they are idempotent).
_ADDED_COLUMNS = (
    ("efforts", "efforts TEXT"),
    ("mode", "mode TEXT NOT NULL DEFAULT 'chat'"),
    ("scenario", "scenario TEXT"),
    ("pinned", "pinned INTEGER NOT NULL DEFAULT 0"),
    ("note", "note TEXT NOT NULL DEFAULT ''"),
)


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
    # FR-M-11: the effort last used with each model in this thread, by model ref
    efforts: dict[str, str] = field(default_factory=dict)
    # FR-MODE-1 (D-074): fixed for the thread's life; threads made before modes are chat
    mode: str = "chat"
    # FR-MODE-4, 6: the roleplay's scenario card (title, setting, user_role, her_role,
    # rules, opening); empty for chat threads and blank roleplays
    scenario: dict[str, Any] = field(default_factory=dict)
    # UI1-09 (D-094): kept at the top of the history list
    pinned: bool = False
    # D-101: a roleplay's Memory, written by the user; in her note every turn
    note: str = ""

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
            "mode": self.mode,
            "scenario": dict(self.scenario),
            "pinned": self.pinned,
            "note": self.note,
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


@dataclass(frozen=True)
class StoryMemory:
    """A roleplay thread's running summary (FR-MODE-5, D-074): everything up to and
    including message `through_message_id` is folded into `summary`."""

    thread_id: str
    summary: str = ""
    through_message_id: int = 0
    updated_at: float | None = None


@dataclass(frozen=True)
class ScenarioCard:
    """A saved scenario card (FR-MODE-6, D-074): the user's, app-level, never tied to a
    companion. `card` holds the filled-in fields (title, setting, user_role, her_role,
    rules, opening); `title` is what the list shows."""

    id: str
    title: str
    card: dict[str, Any] = field(default_factory=dict)
    created_at: float | None = None
    updated_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "card": dict(self.card), "updated_at": self.updated_at}


class ThreadNotFound(KeyError):
    pass


def title_from(text: str) -> str:
    """A thread's automatic title: the first line of the first user message, trimmed."""
    line = " ".join(text.strip().split())
    if len(line) <= TITLE_MAX:
        return line
    return line[: TITLE_MAX - 1].rstrip() + "…"


def scenario_title(card: dict[str, Any]) -> str:
    """A saved card's name in the list (FR-MODE-6): its own title, else the start of its
    setting, else UNTITLED_SCENARIO."""
    for key in ("title", "setting"):
        value = card.get(key)
        text = title_from(value) if isinstance(value, str) else ""
        if text:
            return text
    return UNTITLED_SCENARIO


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
        efforts=_json_dict(row["efforts"]),
        mode=row["mode"] if row["mode"] in MODES else "chat",
        scenario=_json_dict(row["scenario"]),
        pinned=bool(row["pinned"]),
        note=row["note"] or "",
    )


def _json_dict(text: str | None) -> dict[str, Any]:
    try:
        value = json.loads(text) if text else {}
    except json.JSONDecodeError:
        value = {}
    return value if isinstance(value, dict) else {}


def _scenario(row: sqlite3.Row) -> ScenarioCard:
    return ScenarioCard(
        id=row["id"], title=row["title"], card=_json_dict(row["card"]),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _message(row: sqlite3.Row) -> Message:
    meta = _json_dict(row["meta"])
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
        meta=meta,
    )


class ThreadStore:
    def __init__(self, db_path: Path, clock: Any = time.time) -> None:
        self.db_path = Path(db_path)
        self._clock = clock
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(_SCHEMA)
            # Older databases gain the columns in place (v1 -> v2: efforts, FR-M-11;
            # v2 -> v3: mode and scenario, FR-MODE-1). SQLite adds a NOT NULL column only
            # with a constant default, so every existing thread reads as a chat thread.
            have = {r["name"] for r in db.execute("PRAGMA table_info(threads)")}
            for name, ddl in _ADDED_COLUMNS:
                if name not in have:
                    db.execute(f"ALTER TABLE threads ADD COLUMN {ddl}")
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
        mode: str = "chat",
        scenario: dict[str, Any] | None = None,
    ) -> Thread:
        """`mode` is fixed for the thread's life (FR-MODE-1): update_thread cannot change
        it, nor the scenario card (not editable in v1, D-074)."""
        if mode not in MODES:
            raise ValueError(f"unknown thread mode: {mode!r}")
        now = self._now()
        thread_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute(
                "INSERT INTO threads"
                " (id, title, created_at, updated_at, active_waifu_id, model_ref, effort, temp, mode, scenario)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    thread_id, title_from(title), now, now, active_waifu_id, model_ref, effort, int(temp),
                    mode, json.dumps(scenario) if scenario else None,
                ),
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
        # Pinned threads first, so the list's limit never drops one (UI1-09, D-094).
        sql += " ORDER BY pinned DESC, updated_at DESC, created_at DESC LIMIT ?"
        with self._connect() as db:
            return [_thread(r) for r in db.execute(sql, (limit,)).fetchall()]

    def update_thread(self, thread_id: str, **fields: Any) -> Thread:
        """Sets any of: title, active_waifu_id, model_ref, effort, temp, archived, efforts, pinned, note.
        Settings changes do not reorder the history list (updated_at is for messages).
        Mode and scenario are not here on purpose: fixed when the thread is made (FR-MODE-1)."""
        allowed = {"title", "active_waifu_id", "model_ref", "effort", "temp", "archived", "efforts", "pinned", "note"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown thread fields: {sorted(unknown)}")
        if not fields:
            return self.get_thread(thread_id)
        values: dict[str, Any] = dict(fields)
        if "title" in values:
            values["title"] = title_from(str(values["title"] or ""))
        for flag in ("temp", "archived", "pinned"):
            if flag in values:
                values[flag] = int(bool(values[flag]))
        if "efforts" in values:
            values["efforts"] = json.dumps(values["efforts"]) if values["efforts"] else None
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

    def delete_messages(self, ids: list[int]) -> None:
        with self._connect() as db:
            db.executemany("DELETE FROM messages WHERE id = ?", [(i,) for i in ids])

    def get_message(self, message_id: int) -> Message | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return _message(row) if row is not None else None

    def update_message(self, message_id: int, **fields: Any) -> Message:
        """Sets any of: content, speaker_waifu_id, speaker_name, model_ref, effort,
        tokens_in, tokens_out, meta (a pin, a swipe: D-100). The thread's order is kept."""
        allowed = {"content", "speaker_waifu_id", "speaker_name", "model_ref", "effort", "tokens_in", "tokens_out", "meta"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown message fields: {sorted(unknown)}")
        values: dict[str, Any] = dict(fields)
        if "meta" in values:
            values["meta"] = json.dumps(values["meta"]) if values["meta"] else None
        with self._connect() as db:
            if values:
                assignments = ", ".join(f"{name} = ?" for name in values)
                db.execute(f"UPDATE messages SET {assignments} WHERE id = ?", (*values.values(), message_id))
            row = db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            raise KeyError(message_id)
        return _message(row)

    def rewind(self, thread_id: str, message_id: int) -> list[Message]:
        """Rewind to here (D-100): every message after `message_id` in the thread goes,
        in one transaction, and a story summary that reached past it goes too (it is
        rebuilt from what is left). Returns what was deleted."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM messages WHERE thread_id = ? AND id > ? ORDER BY id", (thread_id, message_id)
            ).fetchall()
            db.execute("DELETE FROM messages WHERE thread_id = ? AND id > ?", (thread_id, message_id))
            db.execute("DELETE FROM story_memory WHERE thread_id = ? AND through_message_id > ?", (thread_id, message_id))
        return [_message(r) for r in rows]

    def branch(self, thread_id: str, through_id: int) -> Thread:
        """Start a new chat from here (D-100): a new thread of the same mode, scenario,
        companion, model and effort with copies of the messages up to `through_id`. A
        story summary that ends at or before that point comes along. The copies keep
        their pins and swipes but not the transcript row (log_id) of the original, so
        a Regenerate in the copy never takes a turn out of the original's log."""
        src = self.get_thread(thread_id)
        now = self._now()
        new_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute(
                "INSERT INTO threads (id, title, created_at, updated_at, active_waifu_id, model_ref, effort, temp,"
                " efforts, mode, scenario, note) SELECT ?, title, ?, ?, active_waifu_id, model_ref, effort, temp,"
                " efforts, mode, scenario, note FROM threads WHERE id = ?",
                (new_id, now, now, src.id),
            )
            new_ids: dict[int, int] = {}
            rows = db.execute(
                "SELECT * FROM messages WHERE thread_id = ? AND id <= ? ORDER BY id", (src.id, through_id)
            ).fetchall()
            for r in rows:
                meta = _json_dict(r["meta"])
                meta.pop("log_id", None)
                cur = db.execute(
                    "INSERT INTO messages (thread_id, ts, role, speaker_waifu_id, speaker_name, content,"
                    " model_ref, effort, tokens_in, tokens_out, meta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        new_id, r["ts"], r["role"], r["speaker_waifu_id"], r["speaker_name"], r["content"],
                        r["model_ref"], r["effort"], r["tokens_in"], r["tokens_out"], json.dumps(meta) if meta else None,
                    ),
                )
                new_ids[r["id"]] = int(cur.lastrowid)
            story = db.execute("SELECT * FROM story_memory WHERE thread_id = ?", (src.id,)).fetchone()
            if story is not None and int(story["through_message_id"]) in new_ids:
                db.execute(
                    "INSERT INTO story_memory (thread_id, summary, through_message_id, updated_at) VALUES (?, ?, ?, ?)",
                    (new_id, story["summary"], new_ids[int(story["through_message_id"])], now),
                )
        return self.get_thread(new_id)

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

    # -- story memory (FR-MODE-5, D-074) ---------------------------------------

    def get_story(self, thread_id: str) -> StoryMemory | None:
        """The thread's story summary, or None before the first one is written."""
        with self._connect() as db:
            row = db.execute("SELECT * FROM story_memory WHERE thread_id = ?", (thread_id,)).fetchone()
        if row is None:
            return None
        return StoryMemory(
            thread_id=row["thread_id"],
            summary=row["summary"],
            through_message_id=int(row["through_message_id"]),
            updated_at=row["updated_at"],
        )

    def set_story(self, thread_id: str, summary: str, through_message_id: int) -> bool:
        """Writes the thread's summary and how far it reaches, in one statement. False
        (nothing written) when the thread is gone: a summary finished after its thread
        was deleted is dropped, never left behind."""
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO story_memory (thread_id, summary, through_message_id, updated_at)"
                " SELECT ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM threads WHERE id = ?)"
                " ON CONFLICT(thread_id) DO UPDATE SET summary = excluded.summary,"
                " through_message_id = excluded.through_message_id, updated_at = excluded.updated_at",
                (thread_id, summary, int(through_message_id), self._now(), thread_id),
            )
        return cur.rowcount > 0

    # -- saved scenario cards (FR-MODE-6, D-074) -------------------------------

    def list_scenarios(self) -> list[ScenarioCard]:
        """Every saved card, the most recently saved first."""
        with self._connect() as db:
            rows = db.execute("SELECT * FROM scenarios ORDER BY updated_at DESC, created_at DESC, id").fetchall()
        return [_scenario(r) for r in rows]

    def save_scenario(self, card: dict[str, Any], *, scenario_id: str | None = None) -> ScenarioCard:
        """Inserts a card, or replaces the one with `scenario_id` (a new one is made with
        that id when it is not there). Only filled-in fields are kept; the list's title
        comes from scenario_title. Returns the saved card."""
        kept = {key: value for key, value in card.items() if isinstance(value, str) and value.strip()}
        card_id = scenario_id or uuid.uuid4().hex
        now = self._now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO scenarios (id, title, card, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET title = excluded.title, card = excluded.card,"
                " updated_at = excluded.updated_at",
                (card_id, scenario_title(kept), json.dumps(kept), now, now),
            )
            row = db.execute("SELECT * FROM scenarios WHERE id = ?", (card_id,)).fetchone()
        return _scenario(row)

    def delete_scenario(self, scenario_id: str) -> bool:
        """False when there was no such card. Threads started from it keep their own copy."""
        with self._connect() as db:
            cur = db.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
        return cur.rowcount > 0

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
