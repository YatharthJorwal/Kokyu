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
