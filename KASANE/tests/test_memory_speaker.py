"""Shared memory knows who spoke (FR-MEM-1, FR-MEM-2, D-005)."""
from __future__ import annotations

import sqlite3

import pytest

from memory import consolidation, migrate, store, writer


def test_speaker_is_stored_and_read_back(memory_db):
    store.add_transcript_turn("hi", "hello there", speaker="Luna")
    store.add_transcript_turn("again", "welcome back", speaker="Yuri")
    rows = store.get_transcript_after(0)
    assert [r["speaker"] for r in rows] == ["Luna", "Yuri"]


def test_a_turn_without_a_speaker_stores_null(memory_db):
    store.add_transcript_turn("hi", "hello there")
    store.add_transcript_turn("yo", "sup", speaker="   ")
    assert [r["speaker"] for r in store.get_transcript_after(0)] == [None, None]


def test_the_review_log_is_unchanged_by_speakers(memory_db):
    store.add_transcript_turn("hi", "hello", speaker="Luna")
    assert set(store.get_transcript_log()[0]) == {"user", "assistant", "ts"}


def test_writer_attributes_each_line_to_the_companion_who_said_it():
    luna = writer._format_turn({"user": "hello", "assistant": "hi, it's me", "speaker": "Luna"})
    yuri = writer._format_turn({"user": "hello", "assistant": "hi, it's me", "speaker": "Yuri"})
    assert luna == "User: hello\nLuna: hi, it's me"
    assert yuri == "User: hello\nYuri: hi, it's me"


def test_rows_from_before_waifus_keep_the_legacy_speaker_name():
    row = {"user": "a", "assistant": "b", "speaker": None}
    assert writer._format_turn(row).endswith(f"{writer.SPEAKER}: b")


def test_memory_writes_do_not_depend_on_which_waifu_spoke(memory_db):
    """Facts and episodes are never namespaced by waifu: the schema has no waifu column
    outside the transcript speaker name (D-005)."""
    for table in ("facts", "episodes"):
        cols = {r[1] for r in memory_db.execute(f"PRAGMA table_info({table})")}
        assert not any("waifu" in c or "speaker" in c or "persona" in c for c in cols), (table, cols)


def test_consolidation_prompt_tells_the_model_to_name_the_companion():
    prompt = consolidation._SYSTEM_PROMPT
    assert "name her in the episode_summary" in prompt
    assert 'does not start with "User:"' in prompt


def test_v2_database_gains_the_speaker_column_without_losing_rows(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE transcript_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_text TEXT NOT NULL, "
        "assistant_text TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')), temp INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO transcript_log (user_text, assistant_text) VALUES ('hello', 'hi')")
    conn.commit()
    migrate._add_columns(conn, "transcript_log", migrate._V3_TRANSCRIPT_COLUMNS)
    migrate._add_columns(conn, "transcript_log", migrate._V3_TRANSCRIPT_COLUMNS)  # idempotent
    row = conn.execute("SELECT user_text, assistant_text, speaker FROM transcript_log").fetchone()
    assert row == ("hello", "hi", None)
    conn.close()
