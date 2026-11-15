"""K1-13: the Doctor (FR-SET-3) and the memory viewer (FR-MEM-4)."""
from __future__ import annotations

import dataclasses

import pytest

import doctor
import vram
from audio import tts
from config import CONFIG, LlamaCppConfig, LlamaCppPreset
from memory import embeddings, migrate, store
from memory import viewer as memory_viewer

# -- the memory viewer -------------------------------------------------------------


@pytest.mark.asyncio
async def test_facts_can_be_read_corrected_forgotten_and_restored(memory_db, monkeypatch):
    async def embed(text):
        return [0.5, 0.5, 0.5, 0.5]   # the fixture's database is 4-wide

    monkeypatch.setattr(embeddings, "embed", embed)
    old = store.add_fact("The user lives in Pune")
    other = store.add_fact("The user likes green tea")
    replaced = store.add_fact("The user is 20")
    store.supersede_fact(replaced, other)                     # the writer's own correction: not listed
    assert [f["content"] for f in await memory_viewer.facts()] == ["The user likes green tea", "The user lives in Pune"]

    # correct: a new fact in the user's words supersedes the old one; nothing is deleted
    assert await memory_viewer.correct(old, "The user lives in Mumbai")
    live = await memory_viewer.facts()
    assert [f["content"] for f in live][0] == "The user lives in Mumbai" and live[0]["source"] == "correction"
    assert store.get_fact(old)["superseded_by"] == live[0]["id"]          # the row stays (FR-MEM-3)
    assert live[0]["id"] not in dict(store.facts_missing_vectors())          # recall can find it at once
    assert not await memory_viewer.correct(old, "again")                   # only a live fact can be corrected

    # forget and restore
    await memory_viewer.forget(other)
    shown = {f["content"]: f["forgotten"] for f in await memory_viewer.facts()}
    assert shown == {"The user lives in Mumbai": False, "The user likes green tea": True}
    assert store.get_fact(other)["superseded_by"] == migrate.FORGOTTEN
    assert not await memory_viewer.restore(old)                            # replaced, not forgotten
    assert await memory_viewer.restore(other)
    assert not any(f["forgotten"] for f in await memory_viewer.facts())
    assert [e["kind"] for e in store.get_events()][:3] == ["user_restore", "user_forget", "user_correct"]


@pytest.mark.asyncio
async def test_a_correction_without_the_embedder_waits_for_the_writer(memory_db, monkeypatch):
    async def down(text):
        raise embeddings.EmbeddingUnreachableError("Ollama is not running")

    monkeypatch.setattr(embeddings, "embed", down)
    fact = store.add_fact("The user has a cat")
    assert await memory_viewer.correct(fact, "The user has two cats")
    assert [content for _id, content in store.facts_missing_vectors()] == ["The user has two cats"]


# -- the Doctor ---------------------------------------------------------------------


class Catalog:
    available, last_error = True, None

    def model_ids(self):
        return ["vendor/a", "vendor/b"]

    def is_stale(self):
        return False


class Rt:
    api_key_present = True
    catalog = Catalog()

    def api_status(self):
        return {"id": "airouter", "label": "AI Router", "key": "app"}

    def llamacpp_preset(self):
        return None


@pytest.mark.asyncio
async def test_the_doctor_reports_every_component_with_a_fix_hint(tmp_path, monkeypatch):
    replies = {
        "/api/version": {"version": "0.40.16"},
        "/api/tags": {"models": [{"name": "qwen3.5:9b"}]},     # the embedding model is missing
    }

    async def get_json(url, timeout=3.0):
        return next((body for path, body in replies.items() if url.endswith(path)), None)

    async def tts_down():
        return False

    async def gpu():
        return vram.GpuMemory("NVIDIA GeForce RTX 3060", 12288, 11893, 394, "nvml")

    monkeypatch.setattr(doctor, "_get_json", get_json)
    monkeypatch.setattr(tts, "health", tts_down)
    monkeypatch.setattr(vram, "gpu_memory", gpu)
    cfg = dataclasses.replace(
        CONFIG,
        models=dataclasses.replace(CONFIG.models, local={**CONFIG.models.local, "reflex": "qwen3.5:9b"}),
        memory=dataclasses.replace(CONFIG.memory, embedding=dataclasses.replace(CONFIG.memory.embedding, model="nomic-embed-text")),
        llamacpp=LlamaCppConfig(server_path=str(tmp_path / "missing.exe"), presets=(LlamaCppPreset(id="big", model_path="x"),)),
        tts=dataclasses.replace(CONFIG.tts, engine="gpt_sovits"),
    )
    rows = {r["id"]: r for r in await doctor.report(Rt(), cfg)}
    assert list(rows) == ["kernel", "ollama", "chat_model", "embeddings", "llamacpp", "tts", "stt", "gpu", "api"]
    assert rows["ollama"]["state"] == "ok" and "0.40.16" in rows["ollama"]["detail"]
    assert rows["chat_model"]["state"] == "ok"
    assert rows["embeddings"]["state"] == "fail" and rows["embeddings"]["hint"] == "Run: ollama pull nomic-embed-text"
    assert rows["llamacpp"]["state"] == "fail" and "server_path" in rows["llamacpp"]["hint"]
    assert rows["tts"]["state"] == "off"                       # voice is off: starts when turned on (D-061)
    assert rows["gpu"]["state"] == "warn" and "0.4 GB free of 12.0 GB" in rows["gpu"]["detail"]
    assert rows["api"] == {"id": "api", "label": "API models (AI Router)", "state": "ok", "detail": "Key saved, 2 models", "hint": None}
    for row in rows.values():
        assert row["state"] in ("ok", "off") or row["hint"], row       # every problem says how to fix it


@pytest.mark.asyncio
async def test_a_card_full_of_kokyus_own_models_is_not_a_warning(monkeypatch):
    held = {"models": [{"name": "qwen3.5:9b", "size_vram": 5590 * vram.MB}, {"name": "qwen3.5:4b", "size_vram": 3207 * vram.MB}]}

    async def get_json(url, timeout=3.0):
        return held if url.endswith("/api/ps") else None

    async def gpu():
        return vram.GpuMemory("NVIDIA GeForce RTX 3060", 12288, 11893, 394, "nvml")

    monkeypatch.setattr(doctor, "_get_json", get_json)
    monkeypatch.setattr(vram, "gpu_memory", gpu)
    row = await doctor.gpu_row(CONFIG)
    assert row["state"] == "ok" and row["hint"] is None
    assert "models 8.6 GB, other programs 3.0 GB" in row["detail"]

    held["models"] = held["models"][:0]                      # the same card, filled by something else
    row = await doctor.gpu_row(CONFIG)
    assert row["state"] == "warn" and "Other programs" in row["hint"]


@pytest.mark.asyncio
async def test_ollama_down_is_one_failing_row_with_the_fix(monkeypatch):
    async def nothing(url, timeout=3.0):
        return None

    monkeypatch.setattr(doctor, "_get_json", nothing)
    rows = {r["id"]: r for r in await doctor.report(object())}
    assert rows["ollama"]["state"] == "fail" and "Start Ollama" in rows["ollama"]["hint"]
    assert "chat_model" not in rows and rows["gpu"]["state"] == "warn"   # no GPU reading in tests
    assert rows["api"]["state"] == "off"
