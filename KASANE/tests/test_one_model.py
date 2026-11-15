"""D-072: one chat model in memory; the helper roles follow the picked Ollama model."""
from __future__ import annotations

import dataclasses

import llm
from config import CONFIG
from router.decision import LOCAL_PROVIDER, model_for


def test_helper_roles_run_on_the_picked_model(monkeypatch):
    models = dataclasses.replace(CONFIG.models, local={**CONFIG.models.local, "classifier": "small:2b", "memory_writer": "small:2b"})
    assert model_for(LOCAL_PROVIDER, "classifier", models) == "small:2b"   # nothing picked yet: the config
    monkeypatch.setattr(llm, "ACTIVE_MODEL", "gemma3:12b")
    for role in ("classifier", "memory_writer", "vision"):
        assert model_for(LOCAL_PROVIDER, role, models) == "gemma3:12b"
    assert model_for(LOCAL_PROVIDER, "embed", models) != "gemma3:12b"     # embeddings keep their own model
    monkeypatch.setattr(llm, "ACTIVE_MODEL", "")                         # llama.cpp or API picked: the config
    assert model_for(LOCAL_PROVIDER, "classifier", models) == "small:2b"


def test_only_the_picked_and_embedding_models_stay_loaded(monkeypatch):
    assert llm.keep_alive_for("anything") == {}                          # nothing picked: Ollama's default
    monkeypatch.setattr(llm, "ACTIVE_MODEL", "gemma3:12b")
    keep = CONFIG.providers["local_ollama"].keep_alive
    assert llm.keep_alive_for("gemma3:12b") == {"keep_alive": keep}
    assert llm.keep_alive_for(CONFIG.memory.embedding.model) == {"keep_alive": keep}
    assert llm.keep_alive_for("qwen3.5:4b") == {"keep_alive": 0}          # loads for its call, then leaves


def test_vision_uses_the_picked_model_unless_one_is_configured(monkeypatch):
    monkeypatch.setattr(llm, "ACTIVE_MODEL", "gemma3:12b")
    monkeypatch.setattr(llm, "CONFIG", dataclasses.replace(CONFIG, llm=dataclasses.replace(CONFIG.llm, vision_model=None)))
    assert llm.vision_model_name() == "gemma3:12b"
