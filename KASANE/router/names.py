"""Short display names for models (FR-M-12, D-084).

The picker, the chip and the kernel's own messages show a short name ("Qwen3.5 9B",
"Claude Sonnet 5.5"); the backend's exact id and the details are only shown on
hover. Names are computed here so every client shows the same one.

Precedence: a `names:` override in models.yaml (the user's file, then the shipped
example), then a llama.cpp preset label, then a name derived from the id. A ref
that cannot be parsed is shown as it is, never as an empty name.
"""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path

import yaml

import paths
from router import model_ref as model_refs

log = logging.getLogger(__name__)

# How each family writes its own name. Qwen glues the version on ("Qwen3.5");
# the others put a space before it ("Llama 3.2").
FAMILIES = {
    "qwen": "Qwen", "llama": "Llama", "deepseek": "DeepSeek", "gpt": "GPT", "gemini": "Gemini",
    "claude": "Claude", "gemma": "Gemma", "mistral": "Mistral", "phi": "Phi", "grok": "Grok",
}
GLUED = frozenset({"qwen"})
ACRONYMS = frozenset({"oss", "vl", "moe"})
VENDORS = {
    "anthropic": "Anthropic", "openai": "OpenAI", "google": "Google", "meta-llama": "Meta",
    "x-ai": "xAI", "mistralai": "Mistral", "deepseek": "DeepSeek", "qwen": "Qwen",
    "microsoft": "Microsoft", "nvidia": "NVIDIA", "cohere": "Cohere", "amazon": "Amazon",
    "moonshotai": "Moonshot AI", "z-ai": "Z.ai", "minimax": "MiniMax", "perplexity": "Perplexity",
}

QUANT = re.compile(r"^(i?q\d+(_[a-z0-9]+)*|ud|f16|bf16|fp16|fp8|f32|mxfp4|awq|gptq|int[48]|\d+bit|qat)$", re.I)
NOISE = frozenset({"instruct", "it", "hf", "gguf", "latest"})
SIZE = re.compile(r"^(\d+x)?\d+(\.\d+)?[bm]$", re.I)
ACTIVE = re.compile(r"^a\d+(\.\d+)?b$", re.I)      # MoE active parameters, "a3b"
EFFECTIVE = re.compile(r"^e\d+(\.\d+)?b$", re.I)   # Gemma's "e4b"
CONTEXT = re.compile(r"^\d+k$", re.I)
DATE = re.compile(r"[-_](\d{8}|\d{4}-\d{2}-\d{2})$")

_overrides: list[tuple[str, str]] | None = None


def _read(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning(f"names: could not read {path.name}: {exc}")
        return []
    names = data.get("names") if isinstance(data, dict) else None
    if not isinstance(names, dict):
        return []
    return [(str(p).lower(), str(n)) for p, n in names.items() if str(n).strip()]


def overrides() -> list[tuple[str, str]]:
    """The user's `names:` first, then the shipped ones. Read once per process."""
    global _overrides
    if _overrides is None:
        _overrides = _read(paths.models_path()) + _read(paths.models_example_path())
    return _overrides


def reload() -> None:
    global _overrides
    _overrides = None


def _word(token: str) -> str:
    low = token.lower()
    if low in FAMILIES:
        return FAMILIES[low]
    if low in ACRONYMS:
        return low.upper()
    if re.fullmatch(r"o\d+", low):   # OpenAI's o-series stays lowercase
        return low
    for family, shown in FAMILIES.items():
        rest = low[len(family):]
        if low.startswith(family) and rest[:1].isdigit():
            return f"{shown}{rest}" if family in GLUED else f"{shown} {rest}"
    if SIZE.match(token) or EFFECTIVE.match(token):
        return token[:-1] + token[-1].upper() if not EFFECTIVE.match(token) else token.upper()
    return token[:1].upper() + token[1:]


def derive(model: str) -> str:
    """A short name from a backend's model id (no ref prefix)."""
    name, tag = model, ""
    if model.lower().startswith("hf.co/") or ("/" not in model and ":" in model):
        name, _, tag = model.rpartition(":") if ":" in model else (model, "", "")
        name = name.rsplit("/", 1)[-1]
    elif "/" in model:
        name = model.split("/", 1)[1]
    name = re.sub(r"([-_]gguf|\.gguf)$", "", name, flags=re.I)
    dup = re.match(r"^([a-z]+)_(.+)$", name, re.I)   # "Qwen_Qwen3.5-9B"
    if dup and dup.group(2).lower().startswith(dup.group(1).lower()):
        name = dup.group(2)
    name = DATE.sub("", name)

    tokens: list[str] = []
    for part in re.split(r"[-\s:]+", f"{name}-{tag}" if tag else name):
        if not part or QUANT.match(part):
            continue
        tokens += [t for t in part.split("_") if t]
    words: list[str] = []
    prev = ""
    for token in tokens:
        low = token.lower()
        if low in NOISE or QUANT.match(token) or CONTEXT.match(token):
            continue
        if words and ACTIVE.match(token) and SIZE.match(prev):
            words[-1] += "-" + token.upper()
        elif words and token.isdigit() and len(token) <= 2 and prev.replace(".", "").isdigit() and len(prev) <= 4:
            words[-1] += "." + token   # "claude-3-5-sonnet" -> 3.5
        elif words and words[-1] == "GPT":
            words[-1] += "-" + _word(token)   # GPT-4o, GPT-5.5, GPT-OSS
        else:
            words.append(_word(token))
        prev = token
    return " ".join(words) or model


def short(ref: str, *, preset_label: str | None = None) -> str:
    """The name shown for a model ref."""
    low = ref.lower()
    for pattern, shown in overrides():
        # fnmatchcase on lowercased text: plain fnmatch turns "/" into "\" on Windows
        if fnmatch.fnmatchcase(low, pattern):
            return shown
    if preset_label:
        return re.sub(r"\s*\([^)]*\)\s*$", "", preset_label).strip() or preset_label
    try:
        parsed = model_refs.parse(ref)
    except model_refs.ModelRefError:
        return ref
    return derive(parsed.model)


def label_note(preset_label: str | None) -> str | None:
    """A preset label's trailing "(...)", which belongs with the details."""
    found = re.search(r"\(([^)]*)\)\s*$", preset_label or "")
    return found.group(1).strip() or None if found else None


def vendor(slug: str) -> str:
    """A provider's display name for the picker's group headings."""
    return VENDORS.get(slug.lower()) or " ".join(w[:1].upper() + w[1:] for w in re.split(r"[-_]", slug) if w)
