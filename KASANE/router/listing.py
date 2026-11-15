"""What the model picker lists (K1-07, K1-10; FR-M-3, 4, 7; D-054).

One `model_list` payload for the chip's popover:

- **Local**: the llama.cpp presets from `config.yaml` (`llamacpp.presets`) and
  the chat models Ollama has pulled (`GET /api/tags`, embedding models left
  out because they cannot chat).
- **API**: the catalog the router already keeps (`/v1/models`, cached; offline
  it is the cache, marked stale).
- The spend so far and the caps, for the popover footer (FR-M-7).

Every row is a plain dict that becomes JSON as is. A source that cannot be read
(Ollama not running, no catalog yet) leaves its section empty with a reason; it
never fails the whole list. Each local row carries the VRAM manager's *fits /
won't fit* hint (K1-09): `None` when there is no GPU reading or nothing to
estimate from. `load_check` is the same verdict, asked before a load.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
from collections.abc import Mapping
from typing import Any

import httpx

import llm
import vram
from config import CONFIG, Config, LlamaCppConfig
from provider_presets import API_PRESETS
from router import capabilities
from router import model_ref as model_refs
from router.decision import LOCAL_PROVIDER, model_for
from router.providers.llamacpp import helper_models

log = logging.getLogger(__name__)

# Ollama model families that only embed (nomic-embed-text is "nomic-bert").
EMBEDDING_FAMILIES = frozenset({"bert", "nomic-bert", "jina-bert", "xlm-roberta", "gte", "e5"})


def default_ref(cfg: Config | None = None) -> str:
    """The model a thread without a choice uses, as an explicit reference:
    `chat.default_model_ref`, else the local Ollama chat model (D-050)."""
    cfg = cfg or CONFIG
    if cfg.chat.default_model_ref:
        return cfg.chat.default_model_ref
    return f"local:ollama/{model_for(LOCAL_PROVIDER, 'chat', cfg.models)}"


def effective_ref(thread_ref: str | None, cfg: Config | None = None) -> str:
    return thread_ref or default_ref(cfg)


def label_for(ref: str, cfg: Config | None = None) -> str:
    """A short name for the chip: the preset's label, else the backend's model id."""
    cfg = cfg or CONFIG
    try:
        parsed = model_refs.parse(ref)
    except model_refs.ModelRefError:
        return ref
    if parsed.backend == "llamacpp":
        preset = cfg.llamacpp.preset(parsed.model)
        if preset is not None and preset.label:
            return preset.label
    return parsed.model


def is_embedding_model(name: str, details: Mapping[str, Any] | None) -> bool:
    if "embed" in name.lower():
        return True
    details = details or {}
    families = [details.get("family"), *(details.get("families") or ())]
    return any(str(f).lower() in EMBEDDING_FAMILIES for f in families if f)


LOCAL_BADGES = ("vision", "thinking", "tools")


def _bare(name: str) -> str:
    return name[: -len(":latest")] if name.endswith(":latest") else name


async def ollama_rows(
    base_url: str,
    *,
    exclude: frozenset[str] = frozenset(),
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Chat-capable models Ollama has pulled, largest first, and an error text
    when Ollama could not be asked."""
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(5.0, connect=2.0)) as client:
            response = await client.get(url)
        if response.status_code >= 400:
            return [], f"Ollama answered {response.status_code}"
        models = response.json().get("models") or []
    except (httpx.HTTPError, ValueError, AttributeError):
        return [], "Ollama is not running"
    rows = []
    for item in models:
        if not isinstance(item, Mapping) or not item.get("name"):
            continue
        name = _bare(str(item["name"]))
        details = item.get("details") if isinstance(item.get("details"), Mapping) else {}
        if is_embedding_model(name, details) or name in exclude:
            continue
        parts = [str(details.get(k)) for k in ("parameter_size", "quantization_level") if details.get(k)]
        size = item.get("size")
        rows.append(
            {
                "ref": f"local:ollama/{name}",
                "label": name,
                "kind": "local",
                "backend": "ollama",
                "detail": " · ".join(["Ollama", *parts]),
                "size_bytes": int(size) if isinstance(size, (int, float)) else None,
                "available": True,
                "note": None,
                "fits": None,
                # the picker's badges (D-068): what Ollama itself says the model can do
                "tags": [c for c in item.get("capabilities") or () if c in LOCAL_BADGES],
                "efforts": capabilities.efforts_for(f"local:ollama/{name}"),   # FR-M-8, FR-M-10
            }
        )
    rows.sort(key=lambda r: (-(r["size_bytes"] or 0), r["label"]))
    return rows, None


def llamacpp_rows(cfg: LlamaCppConfig) -> list[dict[str, Any]]:
    rows = []
    for preset in cfg.presets:
        path = pathlib.Path(preset.model_path)
        try:
            size = path.stat().st_size if path.is_file() else None
        except OSError:
            size = None
        rows.append(
            {
                "ref": f"local:llamacpp/{preset.id}",
                "label": preset.label or preset.id,
                "kind": "local",
                "backend": "llamacpp",
                "detail": f"llama.cpp · {preset.ctx // 1024}k context",
                "size_bytes": size,
                "available": size is not None,
                "note": None if size is not None else "model file not found",
                "fits": None,
                "efforts": capabilities.efforts_for(f"local:llamacpp/{preset.id}"),
            }
        )
    return rows


def api_rows(catalog: Any, *, key_present: bool, backend: str = "airouter") -> list[dict[str, Any]]:
    """Chat models from the provider catalog. Without a key they are listed but
    not selectable: picking one would only be refused (CLOUD_DISABLED)."""
    if catalog is None or not catalog.available:
        return []
    rows = []
    for model_id in catalog.model_ids():
        info = catalog.info(model_id)
        if info is None or info.kind not in ("language", "", "chat", "text"):
            continue
        detail = [f"{info.context_length // 1000}k context"] if info.context_length else []
        vendor, _, name = model_id.partition("/")
        rows.append(
            {
                "ref": f"api:{backend}/{model_id}",
                "label": name or model_id,
                "group": vendor if name else None,   # FR-M-4: grouped by provider
                "kind": "api",
                "backend": backend,
                "detail": " · ".join(detail) or None,
                "size_bytes": None,
                "available": key_present,
                "note": None if key_present else "needs an API key",
                "fits": None,
                "price_in": info.price_in or None,
                "price_out": info.price_out or None,
                "tags": list(info.tags) + (["zdr"] if getattr(info, "zdr", False) else []),
                "efforts": capabilities.efforts_for(f"api:{backend}/{model_id}", info.tags),
            }
        )
    return rows


def _check(row: Mapping[str, Any], snap: vram.Snapshot, cfg: Config, label: str | None = None) -> vram.LoadCheck:
    """Would this local row fit as the chat model? Reads the measured cache: off the loop."""
    ref = row["ref"]
    preset = cfg.llamacpp.preset(ref.split("/", 1)[1]) if row["backend"] == "llamacpp" else None
    need = vram.need_for(
        ref,
        file_bytes=row["size_bytes"],
        ctx=preset.ctx if preset else (cfg.llm.num_ctx or 2048),
        cfg=cfg.vram,
        experts_on_cpu=bool(preset and preset.n_cpu_moe),
    )
    return vram.plan(
        ref,
        label or row["label"],
        need,
        snap,
        helpers={f"local:ollama/{name}" for name in helper_models(cfg)},
        label_of=lambda r: label_for(r, cfg),
        headroom_mb=cfg.vram.headroom_mb,
    )


async def _snapshot(rt: Any) -> vram.Snapshot:
    preset = rt.llamacpp_preset() if hasattr(rt, "llamacpp_preset") else None
    return await vram.snapshot(lambda: llm.loaded_models(), preset)


async def with_fits(rows: list[dict[str, Any]], rt: Any, cfg: Config) -> list[dict[str, Any]]:
    """FR-M-3: each local row's fits / won't fit hint (K1-09)."""
    snap = await _snapshot(rt)
    if snap.gpu is None or not rows:
        return rows
    verdicts = await asyncio.to_thread(lambda: [_check(row, snap, cfg).fits for row in rows])
    return [{**row, "fits": fits} for row, fits in zip(rows, verdicts)]


async def load_check(
    ref: str, rt: Any, cfg: Config | None = None, *, transport: httpx.AsyncBaseTransport | None = None
) -> vram.LoadCheck:
    """Before loading a local chat model (FR-M-6, ARCHITECTURE §7.3): would it fit
    beside the helpers once the other chat model is gone? `fits` is None (go
    ahead) when the kernel cannot tell."""
    cfg = cfg or CONFIG
    unknown = vram.LoadCheck(None, None, None)
    if not ref.startswith("local:"):
        return unknown
    snap = await _snapshot(rt)
    if snap.gpu is None:
        return unknown
    if ref.startswith("local:llamacpp/"):
        rows = await asyncio.to_thread(llamacpp_rows, cfg.llamacpp)
    else:
        rows, _ = await ollama_rows(cfg.llm.base_url, transport=transport)
    row = next((r for r in rows if r["ref"] == ref), None)
    # "It": the waking-up card already puts the model's name before the message
    return unknown if row is None else await asyncio.to_thread(_check, row, snap, cfg, "It")


def _cap(value: float) -> float | None:
    """A negative cap means unlimited (BudgetConfig)."""
    return None if value < 0 else value


async def model_list(
    rt: Any,
    *,
    refresh: bool = False,
    cfg: Config | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """The `model_list` frame's data. Never raises."""
    cfg = cfg or CONFIG
    exclude = frozenset({_bare(cfg.memory.embedding.model)}) if cfg.memory.embedding.model else frozenset()
    local, local_error = await ollama_rows(cfg.llm.base_url, exclude=exclude, transport=transport)
    local = await asyncio.to_thread(llamacpp_rows, cfg.llamacpp) + local  # stats files: off the loop
    try:
        local = await with_fits(local, rt, cfg)
    except Exception as exc:  # noqa: BLE001 -- a hint, never a reason to fail the list
        log.warning(f"fits hints skipped: {type(exc).__name__}: {exc}")

    catalog = getattr(rt, "catalog", None)
    refresh_error = None
    if refresh and catalog is not None:
        try:
            await catalog.refresh(force=True)
        except Exception as exc:  # noqa: BLE001 -- the catalog records the usual failures itself
            refresh_error = f"{type(exc).__name__}: {exc}"
        ensure_cloud = getattr(rt, "ensure_cloud", None)
        if ensure_cloud is not None:
            await ensure_cloud(fetch=False)   # a list that came back must also be usable (FR-M-4)
    catalog = getattr(rt, "catalog", None)   # a key change during the refresh swaps it
    key_present = bool(getattr(rt, "api_key_present", False))
    status = rt.api_status() if hasattr(rt, "api_status") else None
    api = api_rows(catalog, key_present=key_present, backend=status["id"] if status else "airouter")

    spend = None
    ledger = getattr(rt, "ledger", None)
    if ledger is not None:
        try:
            hour, day, month = await asyncio.to_thread(ledger.totals)
            spend = {
                "enabled": cfg.budget.enabled,
                "hour_usd": round(hour, 4),
                "hourly_cap_usd": _cap(cfg.budget.hourly_usd),
                "day_usd": round(day, 4),
                "month_usd": round(month, 4),
                "daily_cap_usd": _cap(cfg.budget.daily_usd),
                "monthly_cap_usd": _cap(cfg.budget.monthly_usd),
            }
        except Exception:  # noqa: BLE001 -- a footer, not a reason to fail the list
            spend = None

    return {
        "default_ref": default_ref(cfg),
        "local": local,
        "api": api,
        "local_error": local_error,
        "api_error": refresh_error or (getattr(catalog, "last_error", None) if catalog is not None else None),
        # a failed refresh keeps the cached list: mark it stale, not fresh (FR-M-4)
        "api_stale": bool(
            catalog is not None and catalog.available and (catalog.is_stale() or refresh_error or catalog.last_error)
        ),
        "api_key": key_present,
        # D-059: the one active endpoint and the ones a key can be saved for. Never a key.
        "api_provider": status,
        "api_presets": [{"id": pid, "label": preset["label"]} for pid, preset in API_PRESETS.items()],
        "spend": spend,
    }
