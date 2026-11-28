"""The OpenAI-compatible endpoints Kokyu knows by name (D-037, D-059).

One endpoint is active at a time. Pure data and checks: no I/O, no imports from
the app, so `config.py` and `router/` can both use it.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

# A provider id is the backend of an API model ref (`api:<id>/<model>`) and the
# suffix of its Credential Manager entry (`Kokyu/api-key/<id>`). The shell checks
# the same rule (src-tauri/src/credentials.rs).
PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

# per_million: USD per 1M tokens (AI Router). per_token: USD per token (OpenRouter).
# none: the catalog has no prices (DeepSeek), so its models are unpriced (D-058).
PRICE_UNITS = ("per_million", "per_token", "none")

API_PRESETS: dict[str, dict[str, str]] = {
    "airouter": {
        "label": "AI Router",
        "base_url": "https://api.airouter.in/v1",
        "models_url": "https://api.airouter.in/v1/models",
        "price_unit": "per_million",
        "api_key_env": "AIROUTER_API_KEY",
        "models_cache": "data/airouter_models.json",
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models_url": "https://openrouter.ai/api/v1/models",
        "price_unit": "per_token",
        "api_key_env": "OPENROUTER_API_KEY",
        "models_cache": "data/openrouter_models.json",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models_url": "https://api.deepseek.com/models",
        "price_unit": "none",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models_cache": "data/deepseek_models.json",
    },
}

# D-126, D-127: one-click sets for the picker's list. Each rule is a model *family*
# (matched on the id after the vendor, so "anthropic/claude-sonnet-5.5" on AI Router or
# OpenRouter and a bare "deepseek-chat" on DeepSeek all count), and a set takes the
# newest version of each family the endpoint lists today: when claude-sonnet-6 ships,
# it replaces 5.5 at the next catalog refresh. Speed tiers, dated snapshots and side
# variants are never picked; previews only where a maker ships a line that way (Gemini),
# and a stable release of the same version wins. shortcut: a new family (a new maker or a renamed
# line) still needs a rule here.
# A version: one or two numbers ("5", "5.5", "4.20"); never a date (2411, 0731).
V = r"\d{1,2}(?:\.\d{1,2})?"
# Some makers name tiers, not sizes: OpenAI's luna < terra < sol < astra, Google's
# Gemini 4 hydrogen < argon/carbon < neon (by the catalog's prices, 2026-11).
# A rule starting with ^ is matched on the whole id: "^deepseek-chat" is DeepSeek's
# own bare id, not OpenRouter's "deepseek/deepseek-chat" (an old V3).
POPULAR_FAMILIES: dict[str, tuple[str, ...]] = {
    "Popular": (
        rf"claude-sonnet-{V}", rf"gpt-{V}(-sol)?", rf"gemini-{V}-(flash|hydrogen)(-preview)?",
        rf"deepseek-v{V}-flash", rf"qwen{V}-max", rf"grok-{V}", rf"kimi-k{V}", rf"glm-{V}",
        rf"mistral-large-{V}", r"^deepseek-chat",
    ),
    "Budget": (
        rf"claude-haiku-{V}", rf"gpt-{V}-(mini|luna)", rf"gemini-{V}-flash-lite", rf"deepseek-v{V}-flash",
        rf"qwen{V}-flash", rf"glm-{V}-flash", rf"mistral-small(-{V})?", rf"llama-{V}-(\d+b|scout)", r"^deepseek-chat",
    ),
    "Strongest": (
        rf"claude-fable-{V}", rf"claude-opus-{V}", rf"gpt-{V}-(pro|astra)", rf"gemini-{V}-(pro|neon)(-preview)?",
        rf"qwen{V}-max", rf"kimi-k{V}-pro", rf"deepseek-v{V}-pro", rf"grok-{V}", r"^deepseek-reasoner",
    ),
}


def _version(name: str) -> tuple[int, ...]:
    """claude-sonnet-5.5 -> (5, 5); qwen4-max -> (4,), newer than qwen3.8-max's (3, 8)."""
    return tuple(int(n) for n in re.findall(r"\d+", name))


def newest(model_ids: list[str], family: str) -> str | None:
    """The endpoint's newest model of `family` (a regex over the whole id after the vendor)."""
    rule = re.compile(family)
    whole = family.startswith("^")   # a bare id only (see POPULAR_FAMILIES)
    found = [m for m in model_ids if rule.fullmatch(m if whole else m.rpartition("/")[2])]
    # the highest version; between equals a stable release before a preview, then the
    # A–Z first (gpt-6.2-astra before gpt-6.2-sol)
    return max(
        found,
        key=lambda m: (_version(m.rpartition("/")[2]), not m.endswith("-preview"), [-ord(c) for c in m]),
        default=None,
    )


def popular_in(model_ids: list[str]) -> dict[str, list[str]]:
    """Each set as the endpoint's own ids, one per family, in the set's order; empty sets left out."""
    found: dict[str, list[str]] = {}
    for label, families in POPULAR_FAMILIES.items():
        picks = [newest(model_ids, family) for family in families]
        ids = list(dict.fromkeys(m for m in picks if m))
        if ids:
            found[label] = ids
    return found


# Fields that describe *where* the endpoint is; everything else in the config slot
# (timeouts, refresh hours, zdr) applies to whichever endpoint is active.
ENDPOINT_FIELDS = ("label", "base_url", "models_url", "price_unit", "api_key_env", "models_cache")


def url_problem(url: str) -> str | None:
    """Why `url` may not carry a key, or None. https only, except plain http to this
    PC; no user info, query or fragment."""
    try:
        parts = urlsplit(url)
        parts.port   # raises on a port out of range
    except ValueError:
        return "not a URL"
    if parts.username or parts.password or parts.query or parts.fragment:
        return "must not carry a user name, a query or a fragment"
    if parts.scheme == "https" and parts.hostname:
        return None
    if parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost", "::1"):
        return None
    return "must be https (plain http only to this PC)"


def same_host(a: str, b: str) -> bool:
    """The models URL may receive the key only when it is on the endpoint's own host."""
    try:
        x, y = urlsplit(a), urlsplit(b)
    except ValueError:
        return False
    return bool(x.hostname) and (x.scheme, x.hostname, x.port) == (y.scheme, y.hostname, y.port)
