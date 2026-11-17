"""Chat memory (D-098): how long a context a local model can hold in graphics memory.

Pure arithmetic over the facts Ollama already reports for a model (`/api/show`
model_info): the weights, plus the KV cache at a context length, plus a working
margin. It only warns (the picker says where the model stops fitting); it never
blocks a choice, and it never touches Ollama. API models get no estimate.

KV cache per token = layers holding attention x KV heads x (key length + value
length) x bytes per element. Hybrid models that keep attention in only some layers
(`full_attention_interval`) count only those. An estimate, never a measurement: it
leans high, so the warning comes a little early rather than late.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Bytes per cache element by Ollama's OLLAMA_KV_CACHE_TYPE (f16 unless set). q8_0 and
# q4_0 store 32 values in 34 and 18 bytes.
KV_BYTES = {"f16": 2.0, "q8_0": 34 / 32, "q4_0": 18 / 32}

# What the runtime needs besides weights and cache (compute buffers, the CUDA
# context): about 0.75 GB at small contexts on a 9B, and it grows with the context.
OVERHEAD_BYTES = 768 * 1024 * 1024
OVERHEAD_PER_TOKEN = 16 * 1024


@dataclass(frozen=True)
class KvShape:
    """What one token costs in the cache, from a model's model_info."""

    layers: int          # layers that keep a KV cache
    kv_heads: int
    key_length: int
    value_length: int

    def bytes_per_token(self, cache_type: str = "f16") -> float:
        return self.layers * self.kv_heads * (self.key_length + self.value_length) * KV_BYTES.get(cache_type, 2.0)


def _int(info: Mapping[str, Any], key: str) -> int | None:
    value = info.get(key)
    if isinstance(value, list):   # some models list a value per layer
        value = max((v for v in value if isinstance(v, (int, float))), default=None)
    return int(value) if isinstance(value, (int, float)) and value > 0 else None


def kv_shape(model_info: Mapping[str, Any]) -> KvShape | None:
    """The cache shape from Ollama's model_info (`<arch>.block_count`,
    `<arch>.attention.head_count_kv`, `.key_length`, `.value_length`; the lengths
    default to embedding_length / head_count). None when the facts are missing."""
    arch = model_info.get("general.architecture")
    if not isinstance(arch, str) or not arch:
        return None
    blocks = _int(model_info, f"{arch}.block_count")
    heads = _int(model_info, f"{arch}.attention.head_count")
    kv_heads = _int(model_info, f"{arch}.attention.head_count_kv") or heads
    embedding = _int(model_info, f"{arch}.embedding_length")
    head_dim = embedding // heads if embedding and heads else None
    key_length = _int(model_info, f"{arch}.attention.key_length") or head_dim
    value_length = _int(model_info, f"{arch}.attention.value_length") or key_length
    if not (blocks and kv_heads and key_length and value_length):
        return None
    interval = _int(model_info, f"{arch}.full_attention_interval")
    layers = math.ceil(blocks / interval) if interval and interval > 1 else blocks
    return KvShape(layers=layers, kv_heads=kv_heads, key_length=key_length, value_length=value_length)


def context_max(model_info: Mapping[str, Any]) -> int | None:
    """The longest context the model was trained for (`<arch>.context_length`)."""
    arch = model_info.get("general.architecture")
    return _int(model_info, f"{arch}.context_length") if isinstance(arch, str) else None


def needed_bytes(weights_bytes: int, shape: KvShape, tokens: int, cache_type: str = "f16") -> int:
    """Graphics memory the model needs at a context of `tokens`."""
    per_token = shape.bytes_per_token(cache_type) + OVERHEAD_PER_TOKEN
    return int(weights_bytes + OVERHEAD_BYTES + per_token * tokens)


def fit_limit(budget_bytes: int, weights_bytes: int, shape: KvShape, cache_type: str = "f16") -> int:
    """The longest context that fits in `budget_bytes` (0 when not even the weights do)."""
    room = budget_bytes - weights_bytes - OVERHEAD_BYTES
    if room <= 0:
        return 0
    return int(room // (shape.bytes_per_token(cache_type) + OVERHEAD_PER_TOKEN))
