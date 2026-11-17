"""UI1-01 (FR-M-12, D-084): short model names."""
from __future__ import annotations

import pytest

import paths
from router import names

CASES = [
    ("local:ollama/hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L", "Qwen3.5 9B"),
    ("local:ollama/qwen3.5:9b", "Qwen3.5 9B"),
    ("local:ollama/qwen3.5:4b", "Qwen3.5 4B"),
    ("api:airouter/anthropic/claude-sonnet-5-5", "Claude Sonnet 5.5"),
    ("api:airouter/deepseek/deepseek-v4-chat", "DeepSeek V4 Chat"),
    ("api:airouter/openai/gpt-5.5-mini", "GPT-5.5 Mini"),
    ("api:airouter/google/gemini-3-pro", "Gemini 3 Pro"),
    ("api:airouter/meta-llama/llama-4-scout", "Llama 4 Scout"),
    ("api:airouter/anthropic/claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
    ("api:airouter/openai/gpt-4o-2024-08-06", "GPT-4o"),
    ("api:airouter/o3-mini", "o3 Mini"),
    ("local:ollama/llama3.2", "Llama 3.2"),
    ("local:ollama/llama3.2:3b", "Llama 3.2 3B"),
    ("local:ollama/phi4-mini", "Phi 4 Mini"),
    ("local:ollama/mistral-small:24b", "Mistral Small 24B"),
    ("local:ollama/gpt-oss:20b", "GPT-OSS 20B"),
    ("local:ollama/deepseek-r1:8b", "DeepSeek R1 8B"),
    ("local:ollama/gemma3:27b-it-qat", "Gemma 3 27B"),
    ("local:ollama/gemma3n:e4b", "Gemma 3n E4B"),
    ("local:ollama/hf.co/unsloth/gemma-3-12b-it-GGUF:UD-Q4_K_XL", "Gemma 3 12B"),
    ("local:ollama/qwen3.6:35b-a3b", "Qwen3.6 35B-A3B"),
    ("api:airouter/mistralai/mistral-small-3.2-24b-instruct", "Mistral Small 3.2 24B"),
    ("api:airouter/qwen/qwen3-235b-a22b-2507", "Qwen3 235B-A22B 2507"),
    ("api:airouter/x-ai/grok-4", "Grok 4"),
    ("api:airouter/acme/foo_bar-v2", "Foo Bar V2"),
    ("not-a-ref", "not-a-ref"),
]


@pytest.fixture(autouse=True)
def no_overrides(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "models_path", lambda: tmp_path / "models.yaml")
    monkeypatch.setattr(paths, "models_example_path", lambda: tmp_path / "models.example.yaml")
    names.reload()
    yield tmp_path
    names.reload()


@pytest.mark.parametrize(("ref", "expected"), CASES)
def test_short_names(ref, expected):
    assert names.short(ref) == expected


def test_preset_label_wins_and_its_note_moves_to_details():
    label = "Qwen3.6 35B-A3B (Q4, experts on CPU)"
    assert names.short("local:llamacpp/big", preset_label=label) == "Qwen3.6 35B-A3B"
    assert names.label_note(label) == "Q4, experts on CPU"
    assert names.label_note("Plain") is None


def test_user_override_comes_first(no_overrides):
    (no_overrides / "models.yaml").write_text("names:\n  'local:ollama/qwen3.5:*': 'My Qwen'\n", encoding="utf-8")
    (no_overrides / "models.example.yaml").write_text("names:\n  'local:ollama/*': 'Shipped'\n", encoding="utf-8")
    names.reload()
    assert names.short("local:ollama/qwen3.5:9b", preset_label="ignored") == "My Qwen"
    assert names.short("local:ollama/llama3.2") == "Shipped"


def test_shipped_example_parses():
    names.reload()
    names._read(paths.resource_dir() / "config" / "models.example.yaml")   # no exception, any content


def test_vendor_display_names():
    assert [names.vendor(v) for v in ("anthropic", "meta-llama", "x-ai", "mistralai", "acme-labs")] == [
        "Anthropic", "Meta", "xAI", "Mistral", "Acme Labs"
    ]
