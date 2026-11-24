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

# D-126: one-click sets for the picker's list, matched on the id after the vendor, so
# "anthropic/claude-sonnet-5.5" and a bare "deepseek-chat" both count. Only the ones the
# endpoint has are offered. shortcut: hand-kept; refresh when the big vendors ship.
POPULAR_MODELS: dict[str, tuple[str, ...]] = {
    "Popular": (
        "claude-sonnet-5.5", "claude-haiku-5.5", "gpt-5.5", "gemini-3.8-flash", "deepseek-v4.1-flash",
        "qwen3.8-max", "grok-4.7", "kimi-k3", "glm-5.3", "mistral-large-4", "deepseek-chat",
    ),
    "Budget": (
        "qwen-3-14b", "deepseek-v4.1-flash", "gemini-3.8-flash", "gpt-5.4-mini", "claude-haiku-5.5",
        "mistral-small", "llama-3.3-70b", "gpt-oss-120b", "deepseek-chat",
    ),
    "Strongest": (
        "claude-fable-5.2", "claude-opus-5.5", "gpt-6.2-sol", "gpt-5.5-pro", "qwen4-max",
        "kimi-k3.1-pro", "deepseek-v4-pro", "deepseek-reasoner",
    ),
}


def popular_in(model_ids: list[str]) -> dict[str, list[str]]:
    """Each popular set, as the endpoint's own ids, in the set's order; empty sets left out."""
    by_name = {model_id.rpartition("/")[2]: model_id for model_id in model_ids}
    found = {label: [by_name[name] for name in names if name in by_name] for label, names in POPULAR_MODELS.items()}
    return {label: ids for label, ids in found.items() if ids}


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
