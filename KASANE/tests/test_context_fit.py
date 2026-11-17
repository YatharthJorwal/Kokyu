"""Chat memory (D-098): the KV-cache estimate and the longest context that fits.

Shapes are the published ones, written as Ollama's /api/show model_info reports them."""
import pytest

import context_fit as fit

GIB = 1024**3

LLAMA3_8B = {
    "general.architecture": "llama",
    "llama.block_count": 32,
    "llama.attention.head_count": 32,
    "llama.attention.head_count_kv": 8,
    "llama.embedding_length": 4096,
    "llama.context_length": 8192,
}

QWEN3_8B = {
    "general.architecture": "qwen3",
    "qwen3.block_count": 36,
    "qwen3.attention.head_count": 32,
    "qwen3.attention.head_count_kv": 8,
    "qwen3.attention.key_length": 128,
    "qwen3.attention.value_length": 128,
    "qwen3.embedding_length": 4096,
    "qwen3.context_length": 40960,
}


def test_llama3_8b_costs_128_kib_per_token_at_f16():
    shape = fit.kv_shape(LLAMA3_8B)
    assert shape == fit.KvShape(layers=32, kv_heads=8, key_length=128, value_length=128)  # 4096 / 32
    assert shape.bytes_per_token() == 128 * 1024
    assert shape.bytes_per_token() * 8192 == 1 * GIB      # the well-known 1 GiB at 8K


def test_qwen3_8b_costs_144_kib_per_token_and_quantized_caches_less():
    shape = fit.kv_shape(QWEN3_8B)
    assert shape.bytes_per_token() == 144 * 1024
    assert shape.bytes_per_token() * 32768 == pytest.approx(4.5 * GIB)
    assert shape.bytes_per_token("q8_0") == pytest.approx(144 * 1024 * 34 / 64)
    assert shape.bytes_per_token("q4_0") < shape.bytes_per_token("q8_0") < shape.bytes_per_token("f16")
    assert fit.context_max(QWEN3_8B) == 40960


def test_a_hybrid_model_counts_only_its_attention_layers():
    hybrid = {**QWEN3_8B, "qwen3.full_attention_interval": 4}
    assert fit.kv_shape(hybrid).layers == 9
    assert fit.kv_shape(hybrid).bytes_per_token() == pytest.approx(QWEN3_8B_PER_TOKEN / 4)


QWEN3_8B_PER_TOKEN = 144 * 1024


def test_missing_facts_give_no_estimate():
    assert fit.kv_shape({}) is None
    assert fit.kv_shape({"general.architecture": "llama"}) is None
    assert fit.kv_shape({**LLAMA3_8B, "llama.block_count": 0}) is None
    assert fit.context_max({"general.architecture": "llama"}) is None


def test_per_layer_lists_take_the_largest():
    per_layer = {**LLAMA3_8B, "llama.attention.head_count_kv": [8, 8, 4, 8]}
    assert fit.kv_shape(per_layer).kv_heads == 8


def test_the_fit_point_is_where_weights_cache_and_margin_fill_the_budget():
    shape = fit.kv_shape(QWEN3_8B)
    weights = int(5.6 * GIB)
    budget = 10 * GIB
    limit = fit.fit_limit(budget, weights, shape)
    assert fit.needed_bytes(weights, shape, limit) <= budget < fit.needed_bytes(weights, shape, limit + 1)
    assert 20000 < limit < 25000                         # about 22K tokens on a 10 GiB budget
    assert fit.fit_limit(budget, weights, shape, "q8_0") > limit
    assert fit.fit_limit(4 * GIB, weights, shape) == 0   # not even the weights fit
