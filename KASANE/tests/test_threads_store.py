"""threads.db: create, list, rename, delete, search, messages (FR-C-1, FR-C-10, SPEC §3.5)."""
from __future__ import annotations

import itertools
import sqlite3

import pytest

from threads import ThreadNotFound, ThreadStore, title_from


@pytest.fixture
def store(tmp_path):
    ticks = itertools.count(1000)
    return ThreadStore(tmp_path / "threads.db", clock=lambda: float(next(ticks)))


def test_a_new_thread_has_the_spec_columns_and_no_title_yet(store):
    t = store.create_thread(active_waifu_id="luna", model_ref="local:ollama/qwen3.5:9b", effort="medium")
    assert t.title == "" and t.active_waifu_id == "luna" and t.model_ref == "local:ollama/qwen3.5:9b"
    assert t.effort == "medium" and t.temp is False and t.archived is False
    assert store.get_thread(t.id) == t


def test_the_first_user_message_titles_the_thread(store):
    t = store.create_thread()
    store.add_message(t.id, "user", "  What's the   weather\nlike today? ")
    store.add_message(t.id, "user", "second message does not retitle")
    assert store.get_thread(t.id).title == "What's the weather like today?"


def test_long_titles_are_cut_with_an_ellipsis():
    title = title_from("word " * 100)
    assert len(title) <= 80 and title.endswith("…")


def test_history_is_newest_first_and_a_message_moves_a_thread_up(store):
    a = store.create_thread()
    b = store.create_thread()
    assert [t.id for t in store.list_threads()] == [b.id, a.id]
    store.add_message(a.id, "user", "hello again")
    assert [t.id for t in store.list_threads()] == [a.id, b.id]


def test_a_divider_does_not_reorder_history(store):
    a = store.create_thread()
    b = store.create_thread()
    store.add_message(a.id, "divider", "Yuri joined the conversation")
    assert [t.id for t in store.list_threads()] == [b.id, a.id]


def test_rename_and_unknown_ids(store):
    t = store.create_thread()
    assert store.rename(t.id, "Trip plans").title == "Trip plans"
    with pytest.raises(ThreadNotFound):
        store.rename("missing", "x")
    with pytest.raises(ThreadNotFound):
        store.add_message("missing", "user", "x")
    assert store.find_thread("missing") is None


def test_delete_removes_messages_and_the_last_thread_marker(store, tmp_path):
    t = store.create_thread()
    m = store.add_message(t.id, "user", "bye")
    store.add_attachment(m.id, "image", "attachments/x.png", "image/png", 10)
    store.set_kv("last_thread", t.id)
    assert store.delete_thread(t.id) is True
    assert store.delete_thread(t.id) is False
    assert store.find_thread(t.id) is None and store.get_kv("last_thread") is None
    with sqlite3.connect(tmp_path / "threads.db") as db:
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM attachments").fetchone()[0] == 0


def test_search_finds_titles_and_message_text_case_insensitively(store):
    a = store.create_thread(title="Cooking ideas")
    b = store.create_thread()
    store.add_message(b.id, "user", "tell me about Saturn")
    store.add_message(b.id, "assistant", "It has RINGS.")
    store.create_thread(title="unrelated")
    assert [t.id for t in store.search("cooking")] == [a.id]
    assert [t.id for t in store.search("rings")] == [b.id]
    assert store.search("100%") == []          # LIKE wildcards are literal
    assert len(store.search("  ")) == 3        # empty search is the full list


def test_search_ignores_divider_text(store):
    t = store.create_thread(title="x")
    store.add_message(t.id, "divider", "Yuri joined the conversation")
    assert store.search("joined") == []


def test_messages_record_speaker_model_effort_and_meta(store):
    t = store.create_thread()
    store.add_message(t.id, "user", "hi")
    m = store.add_message(
        t.id, "assistant", "hello", speaker_waifu_id="yuri", speaker_name="Yuri",
        model_ref="api:airouter/x", effort="high", tokens_in=5, tokens_out=2, meta={"stopped": True},
    )
    assert (m.speaker_waifu_id, m.speaker_name, m.model_ref, m.effort) == ("yuri", "Yuri", "api:airouter/x", "high")
    assert (m.tokens_in, m.tokens_out, m.meta) == (5, 2, {"stopped": True})
    assert [x.role for x in store.messages(t.id)] == ["user", "assistant"]


def test_messages_limit_keeps_the_latest_in_order(store):
    t = store.create_thread()
    for i in range(5):
        store.add_message(t.id, "user", f"m{i}")
    assert [m.content for m in store.messages(t.id, limit=2)] == ["m3", "m4"]


def test_bad_role_and_bad_fields_are_rejected(store):
    t = store.create_thread()
    with pytest.raises(ValueError):
        store.add_message(t.id, "system", "nope")
    with pytest.raises(ValueError):
        store.update_thread(t.id, colour="red")


def test_temp_and_archived_flags_round_trip_and_archived_threads_are_hidden(store):
    t = store.create_thread()
    assert store.update_thread(t.id, temp=True).temp is True
    store.update_thread(t.id, archived=True)
    assert store.list_threads() == [] and len(store.list_threads(include_archived=True)) == 1


def test_reopening_the_database_keeps_everything(tmp_path):
    first = ThreadStore(tmp_path / "threads.db")
    t = first.create_thread(title="kept")
    first.add_message(t.id, "user", "still here")
    second = ThreadStore(tmp_path / "threads.db")
    assert second.get_thread(t.id).title == "kept"
    assert [m.content for m in second.messages(t.id)] == ["still here"]
