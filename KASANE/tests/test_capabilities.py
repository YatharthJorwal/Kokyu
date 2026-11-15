"""FR-M-8, FR-M-10, D-064: a model's effort levels come from data."""

from __future__ import annotations

import pytest

import paths
from router import capabilities


@pytest.fixture(autouse=True)
def _fresh():
    capabilities.reload()
    yield
    capabilities.reload()


def _files(monkeypatch, tmp_path, user: str | None, shipped: str):
    (tmp_path / "shipped.yaml").write_text(shipped, encoding="utf-8")
    monkeypatch.setattr(paths, "models_example_path", lambda: tmp_path / "shipped.yaml")
    if user is not None:
        (tmp_path / "models.yaml").write_text(user, encoding="utf-8")
    monkeypatch.setattr(paths, "models_path", lambda: tmp_path / "models.yaml")


def test_the_shipped_file_gives_qwen_on_and_off_and_gpt_oss_levels():
    # the real config/models.example.yaml
    assert capabilities.efforts_for("local:ollama/qwen3.5:9b") == ["off", "high"]
    assert capabilities.efforts_for("local:llamacpp/qwen3.6-35b-a3b") == ["off", "high"]
    assert capabilities.efforts_for("local:ollama/hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L") == ["off", "high"]
    assert capabilities.efforts_for("local:ollama/gpt-oss:20b") == ["low", "medium", "high"]
    assert capabilities.think_for("local:ollama/gpt-oss:20b", "medium") == "medium"
    assert capabilities.think_for("local:ollama/qwen3.5:9b", "off") is False


def test_a_model_without_data_has_no_slider_and_keeps_its_default():
    assert capabilities.efforts_for("local:ollama/llama3.2:3b") == []
    assert capabilities.think_for("local:ollama/llama3.2:3b", "high") is None
    assert capabilities.think_for("local:ollama/qwen3.5:9b", None) is None
    assert capabilities.think_for("local:ollama/qwen3.5:9b", "low") is None   # a level it does not offer


def test_api_models_offer_reasoning_levels_only_when_the_catalog_says_so():
    assert capabilities.efforts_for("api:airouter/deepseek/r1", ["reasoning", "tools"]) == ["low", "medium", "high"]
    assert capabilities.efforts_for("api:airouter/meta/llama", ["tools"]) == []


def test_the_users_file_wins_and_bad_entries_are_skipped(monkeypatch, tmp_path, caplog):
    _files(
        monkeypatch,
        tmp_path,
        user="local:\n  - match: 'local:ollama/qwen3*'\n    efforts: {off: false, low: true, max: true, extreme: true}\n  - {match: 7}\n",
        shipped="local:\n  - match: 'local:*qwen3*'\n    efforts: {off: false, high: true}\n",
    )
    assert capabilities.efforts_for("local:ollama/qwen3.5:9b") == ["off", "low", "max"]   # canonical order
    assert capabilities.efforts_for("local:llamacpp/qwen3.6") == ["off", "high"]          # the shipped entry
    assert "unknown levels or values ignored" in caplog.text and "skipped" in caplog.text


def test_a_broken_file_is_ignored(monkeypatch, tmp_path, caplog):
    _files(monkeypatch, tmp_path, user="local: [", shipped="local: []\n")
    assert capabilities.efforts_for("local:ollama/qwen3.5:9b") == []
    assert "could not read models.yaml" in caplog.text
