import pytest

import llm
from memory import db


@pytest.fixture(autouse=True)
def _no_picked_model(monkeypatch):
    """D-072: no chat model picked unless a test picks one (boot sets it on a load)."""
    monkeypatch.setattr(llm, "ACTIVE_MODEL", None)


@pytest.fixture(autouse=True)
def _no_real_unload(monkeypatch):
    """A model pick unloads the rest of Ollama (D-072); never the real one from a test."""
    import boot

    async def unload(base_url, keep=frozenset(), transport=None):
        return []

    monkeypatch.setattr(boot, "unload_ollama", unload)


@pytest.fixture(autouse=True)
def _quiet_story_memory(monkeypatch):
    """FR-MODE-5: a fresh story keeper per test that always finds the model busy, so a
    roleplay thread in a test never reaches a real model through story memory. Tests
    of story memory put in their own keeper."""
    import story

    monkeypatch.setattr(story, "KEEPER", story.StoryKeeper(is_busy=lambda: True))


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    """Real sqlite-vec connection on a throwaway file (dim=4), swapped in for
    db.get_connection so every memory module uses it."""
    conn = db._open_connection(path=tmp_path / "test_memory.db", dimension=4)
    monkeypatch.setattr(db, "_conn", conn)
    monkeypatch.setattr(db, "get_connection", lambda: conn)
    yield conn
    conn.close()
