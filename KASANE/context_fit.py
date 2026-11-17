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

import functools
import math
import os
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import config

# The smallest Chat memory offered (the picker's first detent).
MIN_CONTEXT = 8192


def context_for(ref: str | None, cfg: "config.Config | None" = None) -> int | None:
    """The context length a model runs with: the user's Chat memory for it (D-098),
    else a llama.cpp preset's own ctx, else llm.num_ctx. Every Ollama request for the
    model and the history budget read this one value, so Ollama never reloads a model
    because two calls disagreed."""
    cfg = cfg or config.CONFIG
    if ref and ref in cfg.llm.context_by_model:
        return cfg.llm.context_by_model[ref]
    if ref and ref.startswith("local:llamacpp/"):
        from router import model_ref as model_refs   # here: the router package imports llm, which imports this

        try:
            preset = cfg.llamacpp.preset(model_refs.parse(ref).model)
        except model_refs.ModelRefError:
            preset = None
        if preset is not None:
            return preset.ctx
    return cfg.llm.num_ctx

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


# ---------------------------------------------------------------------------
# llama.cpp presets: the same facts, read from the GGUF file's own header (Ollama's
# model_info is that header). Arrays (the tokenizer's vocabulary) are skipped.

_GGUF_SCALARS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
_GGUF_STRING, _GGUF_ARRAY = 8, 9
_SKIPPED = object()


def _gguf_string(f: Any) -> str:
    (length,) = struct.unpack("<Q", f.read(8))
    if length > 1 << 20:
        raise ValueError("implausible GGUF string")
    return f.read(length).decode("utf-8")


def _gguf_skip_or_read(f: Any, kind: int) -> Any:
    if kind in _GGUF_SCALARS:
        fmt = _GGUF_SCALARS[kind]
        return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]
    if kind == _GGUF_STRING:
        return _gguf_string(f)
    if kind == _GGUF_ARRAY:
        item, count = struct.unpack("<IQ", f.read(12))
        if item in _GGUF_SCALARS:
            f.seek(struct.calcsize(_GGUF_SCALARS[item]) * count, 1)
        else:
            for _ in range(count):
                _gguf_skip_or_read(f, item)
        return _SKIPPED
    raise ValueError(f"unknown GGUF value type {kind}")


def _read_gguf(path: str) -> dict[str, Any]:
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            return {}
        (version,) = struct.unpack("<I", f.read(4))
        if version < 2:
            return {}
        _tensors, count = struct.unpack("<QQ", f.read(16))
        out: dict[str, Any] = {}
        for _ in range(min(count, 100_000)):
            key = _gguf_string(f)
            (kind,) = struct.unpack("<I", f.read(4))
            value = _gguf_skip_or_read(f, kind)
            if value is not _SKIPPED:
                out[key] = value
        return out


@functools.lru_cache(maxsize=32)
def _gguf_cached(path: str, _mtime_ns: int, _size: int) -> dict[str, Any]:
    try:
        return _read_gguf(path)
    except (OSError, ValueError, struct.error, UnicodeDecodeError):
        return {}


def gguf_metadata(path: str) -> dict[str, Any]:
    """A GGUF file's header keys, {} when it cannot be read. Remembered per file
    version. File I/O: call it off the event loop."""
    try:
        stat = os.stat(path)
    except OSError:
        return {}
    return _gguf_cached(str(path), stat.st_mtime_ns, stat.st_size)
