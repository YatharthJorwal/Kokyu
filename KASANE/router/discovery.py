"""Model catalog discovery for the cloud provider.

`GET /v1/models` is public and returns context length, pricing, capability tags
and a `zdr` (zero-data-retention) flag per model. The router reads prices from
here instead of carrying a table that silently drifts.

Failure policy: use a cached catalog if one exists, otherwise the provider is
unavailable. Never guess a price, never invent a model id.
"""

from __future__ import annotations

import difflib
import json
import logging
import pathlib
import time
from dataclasses import dataclass
from typing import Any

import httpx

import paths

log = logging.getLogger(__name__)

def repo_path(value: str | pathlib.Path) -> pathlib.Path:
    """Kept for callers; every location now comes from paths.py (R-40)."""
    return paths.resolve(value)


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class ModelInfo:
    id: str
    context_length: int = 0
    max_tokens: int = 0
    price_in: float = 0.0      # USD per 1M prompt tokens
    price_out: float = 0.0     # USD per 1M completion tokens
    tags: tuple[str, ...] = ()
    zdr: bool = False
    kind: str = "language"
    priced: bool = True        # the catalog gave both prices (a price of 0 is a price)

    def supports(self, tag: str) -> bool:
        return tag in self.tags


class ModelCatalog:
    def __init__(
        self,
        base_url: str,
        cache_path: str | pathlib.Path,
        *,
        ttl_hours: float = 24.0,
        transport: httpx.AsyncBaseTransport | None = None,
        models_url: str | None = None,
        price_unit: str = "per_million",
        clock=time.time,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.price_unit = price_unit
        # Set by the router only when the models URL is on the endpoint's own host
        # (DeepSeek's list needs it; AI Router's and OpenRouter's are public).
        self.api_key: str | None = None
        self.models_url = (models_url or f"{self.base_url}/models").rstrip("/")
        self.cache_path = repo_path(cache_path)
        self.ttl_seconds = ttl_hours * 3600.0
        self._transport = transport
        self._clock = clock
        self._models: dict[str, ModelInfo] = {}
        self._fetched_at: float = 0.0
        self.last_error: str | None = None

    # -- state ---------------------------------------------------------------

    @property
    def available(self) -> bool:
        return bool(self._models)

    def model_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._models))

    def info(self, model_id: str) -> ModelInfo | None:
        return self._models.get(model_id)

    def price(self, model_id: str) -> tuple[float, float]:
        info = self.info(model_id)
        return (info.price_in, info.price_out) if info else (0.0, 0.0)

    def priced(self, model_id: str) -> bool:
        info = self.info(model_id)
        return info is not None and info.priced

    def context_length(self, model_id: str) -> int:
        info = self.info(model_id)
        return info.context_length if info else 0

    def closest(self, model_id: str, n: int = 3) -> list[str]:
        """Nearest ids, for the log line when a configured model vanished."""
        return difflib.get_close_matches(model_id, self.model_ids(), n=n, cutoff=0.4)

    def is_stale(self) -> bool:
        return (self._clock() - self._fetched_at) > self.ttl_seconds

    # -- persistence ---------------------------------------------------------

    def load_cache(self) -> bool:
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        models = raw.get("models") if isinstance(raw, dict) else None
        if not isinstance(models, dict) or not models:
            return False
        cached_for = str(raw.get("base_url") or "").rstrip("/")
        if cached_for and cached_for != self.base_url:
            return False   # another endpoint's list: its models and prices are not ours
        # The cache is written per 1M already (see _save_cache): never rescale it.
        self._models = {str(k): _to_info(str(k), v) for k, v in models.items() if isinstance(v, dict)}
        self._fetched_at = _as_float(raw.get("fetched_at", 0.0))
        return bool(self._models)

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": self._fetched_at,
            "base_url": self.base_url,
            "models": {
                model_id: {
                    "context_length": info.context_length,
                    "max_tokens": info.max_tokens,
                    "pricing": {"prompt": info.price_in, "completion": info.price_out} if info.priced else {},
                    "tags": list(info.tags),
                    "zdr": info.zdr,
                    "type": info.kind,
                }
                for model_id, info in self._models.items()
            },
        }
        self.cache_path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    # -- network -------------------------------------------------------------

    async def refresh(self, *, force: bool = False) -> bool:
        """Load the catalog. Returns True when models are usable afterwards."""
        if not self._models:
            self.load_cache()
        if self._models and not force and not self.is_stale():
            return True

        url = self.models_url
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            async with httpx.AsyncClient(transport=self._transport, timeout=15.0) as client:
                response = await client.get(url, headers=headers)
            if response.status_code >= 400:
                self.last_error = f"{response.status_code} from {url}"
                return self.available
            payload = response.json()
        except (httpx.RequestError, ValueError) as exc:
            detail = str(exc)
            if self.api_key and (self.api_key in detail or "Bearer" in detail):
                detail = "details hidden (they quoted the key)"
            self.last_error = f"{type(exc).__name__}: {detail}"
            return self.available

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            self.last_error = "unexpected /models payload (no data list)"
            return self.available

        parsed: dict[str, ModelInfo] = {}
        for entry in data:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            model_id = str(entry["id"])
            parsed[model_id] = _to_info(model_id, entry, self.price_unit)
        if not parsed:
            self.last_error = "catalog was empty"
            return self.available

        self._models = parsed
        self._fetched_at = self._clock()
        self.last_error = None
        try:
            self._save_cache()
        except OSError as exc:  # a read-only repo must not kill the app; the list itself is fresh
            log.warning(f"router: model list cache not written: {exc}")
        return True


# What a price is worth per 1M tokens, by the catalog's unit (D-059).
_PER_MILLION = {"per_million": 1.0, "per_token": 1_000_000.0}


def _to_info(model_id: str, entry: dict[str, Any], unit: str = "per_million") -> ModelInfo:
    pricing = entry.get("pricing") if isinstance(entry.get("pricing"), dict) else {}
    prompt, completion = pricing.get("prompt"), pricing.get("completion")
    scale = _PER_MILLION.get(unit)
    # A negative price (OpenRouter's "-1" for a router model) or no unit means no price.
    priced = (
        scale is not None
        and _is_number(prompt) and _is_number(completion)
        and float(prompt) >= 0 and float(completion) >= 0
    )
    if isinstance(entry.get("tags"), list):
        tags = [str(tag) for tag in entry["tags"]]
    else:
        tags = _derived_tags(entry)
    architecture = entry.get("architecture") if isinstance(entry.get("architecture"), dict) else {}
    outputs = architecture.get("output_modalities")
    kind = str(entry.get("type") or "language")
    if isinstance(outputs, list) and "text" not in outputs:
        kind = "image"   # makes pictures, not replies: kept out of the chat list
    top = entry.get("top_provider") if isinstance(entry.get("top_provider"), dict) else {}
    return ModelInfo(
        id=model_id,
        context_length=int(_as_float(entry.get("context_length"))),
        max_tokens=int(_as_float(entry.get("max_tokens") or top.get("max_completion_tokens"))),
        price_in=_as_float(prompt) * scale if priced else 0.0,
        price_out=_as_float(completion) * scale if priced else 0.0,
        priced=priced,
        tags=tuple(tags),
        zdr=bool(entry.get("zdr", False)),
        kind=kind,
    )


def _derived_tags(entry: dict[str, Any]) -> list[str]:
    """Badges for a catalog without `tags` (OpenRouter): from what the model accepts."""
    params = entry.get("supported_parameters") if isinstance(entry.get("supported_parameters"), list) else []
    architecture = entry.get("architecture") if isinstance(entry.get("architecture"), dict) else {}
    inputs = architecture.get("input_modalities") if isinstance(architecture.get("input_modalities"), list) else []
    tags = []
    if "tools" in params:
        tags.append("tool-use")
    if "reasoning" in params or "include_reasoning" in params:
        tags.append("reasoning")
    if "image" in inputs:
        tags.append("vision")
    return tags
