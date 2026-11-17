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


def test_a_version_1_database_gains_the_efforts_column(tmp_path):
    # FR-M-11 added threads.efforts; a database from before opens and works
    db = tmp_path / "threads.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL, active_waifu_id TEXT, model_ref TEXT, effort TEXT,"
            " temp INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);"
            "INSERT INTO threads (id, created_at, updated_at) VALUES ('old', 1, 1);"
        )
    store = ThreadStore(db)
    assert store.get_thread("old").efforts == {}
    assert store.update_thread("old", efforts={"local:ollama/x": "off"}).efforts == {"local:ollama/x": "off"}


# -- conversation modes (FR-MODE-1, D-074) ------------------------------------

CARD = {"title": "Rain", "setting": "A station at night.", "opening": "*She waves.* Over here!"}


def test_a_new_thread_is_chat_with_no_scenario(store):
    t = store.create_thread()
    assert t.mode == "chat" and t.scenario == {}
    assert t.to_dict()["mode"] == "chat" and t.to_dict()["scenario"] == {}


def test_a_roleplay_thread_keeps_its_mode_and_card(store, tmp_path):
    t = store.create_thread(title="Rain", mode="roleplay", scenario=CARD)
    assert t.mode == "roleplay" and t.scenario == CARD and t.title == "Rain"
    assert t.to_dict()["mode"] == "roleplay" and t.to_dict()["scenario"] == CARD
    again = ThreadStore(tmp_path / "threads.db").get_thread(t.id)   # survives a reopen
    assert again.mode == "roleplay" and again.scenario == CARD
    # a blank roleplay: the mode, no card
    blank = store.create_thread(mode="roleplay", scenario={})
    assert blank.mode == "roleplay" and blank.scenario == {}


def test_an_unknown_mode_is_refused(store):
    with pytest.raises(ValueError):
        store.create_thread(mode="live")


def test_mode_and_scenario_are_fixed_for_the_threads_life(store):
    """FR-MODE-1: chosen when the thread is created; v1 does not edit the card either."""
    t = store.create_thread(mode="roleplay", scenario=CARD)
    with pytest.raises(ValueError):
        store.update_thread(t.id, mode="chat")
    with pytest.raises(ValueError):
        store.update_thread(t.id, scenario={"title": "Other"})
    renamed = store.rename(t.id, "Renamed")
    assert renamed.mode == "roleplay" and renamed.scenario == CARD


def test_a_version_2_database_gains_mode_and_scenario_and_old_threads_are_chat(tmp_path):
    """FR-MODE-1: threads that existed before modes read as chat; nothing else changes."""
    db = tmp_path / "threads.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL, active_waifu_id TEXT, model_ref TEXT, effort TEXT,"
            " temp INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0, efforts TEXT);"
            "INSERT INTO threads (id, title, created_at, updated_at, efforts)"
            " VALUES ('old', 'Before modes', 1, 1, '{\"local:ollama/x\": \"off\"}');"
            "PRAGMA user_version=2;"
        )
    store = ThreadStore(db)
    old = store.get_thread("old")
    assert old.mode == "chat" and old.scenario == {}
    assert old.title == "Before modes" and old.efforts == {"local:ollama/x": "off"}
    assert store.create_thread(mode="roleplay", scenario=CARD).scenario == CARD
    with sqlite3.connect(db) as conn:
        # Schema 4 (K1c-04, FR-MODE-5) added the story_memory table on top of schema 3's
        # columns, and schema 5 (K1c-06, FR-MODE-6) the scenarios table, so an old
        # database now lands on 5 and gains both tables too.
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        columns = {row[1] for row in conn.execute("PRAGMA table_info(threads)")}
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"efforts", "mode", "scenario"} <= columns
    assert {"story_memory", "scenarios"} <= tables
    ThreadStore(db)   # opening it again is a no-op, not a duplicate column


def test_a_version_1_database_gains_every_later_column(tmp_path):
    db = tmp_path / "threads.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,"
            " updated_at REAL NOT NULL, active_waifu_id TEXT, model_ref TEXT, effort TEXT,"
            " temp INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);"
            "INSERT INTO threads (id, created_at, updated_at) VALUES ('old', 1, 1);"
        )
    old = ThreadStore(db).get_thread("old")
    assert old.mode == "chat" and old.scenario == {} and old.efforts == {}


# -- saved scenario cards (FR-MODE-6, D-074) ---------------------------------


def test_a_scenario_card_is_saved_listed_replaced_and_deleted(store):
    """FR-MODE-6: cards are saved locally, newest first; saving with an id replaces that
    card in place; deleting one leaves the others."""
    first = store.save_scenario({"title": "Rain", "setting": "A station at night.", "rules": "  "})
    assert first.title == "Rain" and first.card == {"title": "Rain", "setting": "A station at night."}
    second = store.save_scenario({"title": "Snow"})
    assert [c.id for c in store.list_scenarios()] == [second.id, first.id]
    edited = store.save_scenario({"title": "Rain again", "opening": "*waves*"}, scenario_id=first.id)
    assert edited.id == first.id and edited.created_at == first.created_at and edited.updated_at > first.updated_at
    assert edited.card == {"title": "Rain again", "opening": "*waves*"}   # replaced, not merged
    assert [c.id for c in store.list_scenarios()] == [first.id, second.id]   # the edit moved it up
    assert store.delete_scenario(second.id) is True and store.delete_scenario(second.id) is False
    assert [c.to_dict() for c in store.list_scenarios()] == [
        {"id": first.id, "title": "Rain again", "card": edited.card, "updated_at": edited.updated_at}
    ]


def test_a_card_with_no_title_is_named_from_its_setting_or_untitled(store):
    """FR-MODE-6: the list's title comes from the setting when the title is empty; the
    card itself is kept as written."""
    from_setting = store.save_scenario({"title": "", "setting": "  A quiet  library\nat dusk.  "})
    assert from_setting.title == "A quiet library at dusk." and "title" not in from_setting.card
    long = store.save_scenario({"setting": "x" * 200})
    assert len(long.title) == 80 and long.title.endswith("…")
    assert store.save_scenario({}).title == "Untitled scenario"
    assert store.save_scenario({"opening": "Hi."}).title == "Untitled scenario"


def test_an_unknown_id_saves_a_new_card_with_it_and_cards_outlive_threads(store):
    """Saving with an id that is not there inserts it; a thread started from a card keeps
    its own copy, so deleting either leaves the other (FR-MODE-6)."""
    card = store.save_scenario({"title": "Rain"}, scenario_id="mine")
    assert card.id == "mine" and [c.id for c in store.list_scenarios()] == ["mine"]
    thread = store.create_thread(mode="roleplay", scenario=card.card)
    store.delete_thread(thread.id)
    assert [c.id for c in store.list_scenarios()] == ["mine"]
    other = store.create_thread(mode="roleplay", scenario=card.card)
    store.delete_scenario("mine")
    assert store.get_thread(other.id).scenario == {"title": "Rain"}
