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

import context_fit
import llm
import vram
from config import CONFIG, Config, LlamaCppConfig
from provider_presets import API_PRESETS, popular_in
from router import capabilities, names
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
    return cfg.chat.default_model_ref or local_ref(cfg)


def local_ref(cfg: Config | None = None) -> str:
    """The local Ollama chat model in `llm.model`, as a reference."""
    cfg = cfg or CONFIG
    return f"local:ollama/{model_for(LOCAL_PROVIDER, 'chat', cfg.models)}"


def fallback_ref(failed: str | None, cfg: Config | None = None) -> str | None:
    """D-125: the model that may answer when `failed` (a thread's ref, None = the
    default) can't: Settings' choice, else the local chat model. None when it is the
    same model, which could only fail again."""
    cfg = cfg or CONFIG
    fallback = cfg.chat.fallback_model_ref or local_ref(cfg)
    return None if fallback == effective_ref(failed, cfg) else fallback


def listed_ids(model_ids: list[str], backend: str, cfg: Config | None = None) -> set[str]:
    """D-126: the endpoint's models the picker shows: the user's list for it, else the
    popular ones it has, else all (a custom endpoint the sets do not know)."""
    cfg = cfg or CONFIG
    chosen = cfg.chat.api_models.get(backend)
    if isinstance(chosen, (list, tuple)):
        return set(chosen) & set(model_ids)
    popular = {model_id for ids in popular_in(model_ids).values() for model_id in ids}
    return popular or set(model_ids)


def effective_ref(thread_ref: str | None, cfg: Config | None = None) -> str:
    return thread_ref or default_ref(cfg)


def label_for(ref: str, cfg: Config | None = None) -> str:
    """The short name shown for a model everywhere (FR-M-12, D-084)."""
    cfg = cfg or CONFIG
    try:
        parsed = model_refs.parse(ref)
    except model_refs.ModelRefError:
        return ref
    preset = cfg.llamacpp.preset(parsed.model) if parsed.backend == "llamacpp" else None
    return names.short(ref, preset_label=preset.label if preset is not None else None)


def is_embedding_model(name: str, details: Mapping[str, Any] | None) -> bool:
    if "embed" in name.lower():
        return True
    details = details or {}
    families = [details.get("family"), *(details.get("families") or ())]
    return any(str(f).lower() in EMBEDDING_FAMILIES for f in families if f)


LOCAL_BADGES = ("vision", "thinking", "tools")


def _key_targets(cfg: Config) -> list[dict[str, str]]:
    """The endpoints a key can be saved for (D-059): the presets, and the slot's own
    endpoint when it is a custom one (from config.yaml or Settings, D-070)."""
    targets = [{"id": pid, "label": preset["label"]} for pid, preset in API_PRESETS.items()]
    slot = cfg.providers.get("airouter")
    if slot is not None and slot.enabled and slot.preset and slot.preset not in API_PRESETS:
        targets.append({"id": slot.preset, "label": slot.label or "Custom"})
    return targets


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
                "_digest": str(item.get("digest") or ""),   # Chat memory's facts cache key; dropped in with_context
                "ref": f"local:ollama/{name}",
                "label": names.short(f"local:ollama/{name}"),
                "full": name,
                "quant": details.get("quantization_level"),   # a tie-breaker only; dropped in _distinct
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
                "label": names.short(f"local:llamacpp/{preset.id}", preset_label=preset.label),
                "full": path.name or preset.id,
                "kind": "local",
                "backend": "llamacpp",
                "detail": " · ".join(
                    p for p in ("llama.cpp", names.label_note(preset.label), f"{preset.ctx // 1024}k context") if p
                ),
                "size_bytes": size,
                "available": size is not None,
                "note": None if size is not None else "model file not found",
                "fits": None,
                "efforts": capabilities.efforts_for(f"local:llamacpp/{preset.id}"),
            }
        )
    return rows


def api_rows(
    catalog: Any, *, key_present: bool, backend: str = "airouter", caps_on: bool = False, cfg: Config | None = None
) -> list[dict[str, Any]]:
    """Chat models from the provider catalog. Without a key they are listed but
    not selectable: picking one would only be refused (CLOUD_DISABLED)."""
    if catalog is None or not catalog.available:
        return []
    rows = []
    chat_ids = [
        model_id for model_id in catalog.model_ids()
        if (info := catalog.info(model_id)) is not None and info.kind in ("language", "", "chat", "text")
    ]
    listed = listed_ids(chat_ids, backend, cfg)
    for model_id in chat_ids:
        info = catalog.info(model_id)
        detail = [f"{info.context_length // 1000}k context"] if info.context_length else []
        unpriced = caps_on and not info.priced
        if unpriced:
            detail.append("price unknown, not counted against the cap")   # D-083
        vendor, _, name = model_id.partition("/")
        rows.append(
            {
                "ref": f"api:{backend}/{model_id}",
                "label": names.short(f"api:{backend}/{model_id}"),
                "full": model_id,
                "group": names.vendor(vendor) if name else None,   # FR-M-4: grouped by provider
                "kind": "api",
                "backend": backend,
                "detail": " · ".join(detail) or None,
                "size_bytes": None,
                "available": key_present,
                "listed": model_id in listed,   # D-126: in the picker; every row is in Settings' chooser
                "note": None if key_present else "needs an API key",
                "fits": None,
                "price_in": info.price_in or None,
                "price_out": info.price_out or None,
                "unpriced": unpriced,
                "tags": list(info.tags) + (["zdr"] if getattr(info, "zdr", False) else []),
                "efforts": capabilities.efforts_for(f"api:{backend}/{model_id}", info.tags),
                # D-098: how much of the chat goes with each message; no graphics memory involved
                "context": {
                    "max": info.context_length,
                    "value": context_fit.context_for(f"api:{backend}/{model_id}"),
                    "fit": None,
                    "spills": False,
                } if info.context_length else None,
            }
        )
    return rows


def _check(
    row: Mapping[str, Any], snap: vram.Snapshot, cfg: Config, label: str | None = None, *, ctx: int | None = None
) -> vram.LoadCheck:
    """Would this local row fit as the chat model, at its Chat memory (D-098) unless
    `ctx` is given? Reads the measured cache: off the loop."""
    ref = row["ref"]
    preset = cfg.llamacpp.preset(ref.split("/", 1)[1]) if row["backend"] == "llamacpp" else None
    need = vram.need_for(
        ref,
        file_bytes=row["size_bytes"],
        ctx=ctx or context_fit.context_for(ref, cfg) or 2048,
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
    if row is None:
        return unknown
    # "It": the waking-up card already puts the model's name before the message
    check = await asyncio.to_thread(_check, row, snap, cfg, "It")
    chosen = context_fit.context_for(ref, cfg) or 0
    if check.fits is False and row["backend"] == "ollama" and chosen > (cfg.llm.num_ctx or 0):
        # D-098: a Chat memory past the fit point is a warning, not a block. Ollama keeps
        # what does not fit in RAM and runs slower; it is refused only if even the
        # usual context would not fit. (llama.cpp cannot spill: its refusal stands.)
        usual = await asyncio.to_thread(_check, row, snap, cfg, "It", ctx=cfg.llm.num_ctx)
        if usual.fits is not False:
            log.info(f"vram: {ref} at {chosen} tokens of Chat memory will not fit; loading anyway (Ollama spills)")
            return vram.LoadCheck(None, check.need_mb, check.available_mb)
    return check


# ── Chat memory (D-098): each row's context range, setting and fit point ──────────

# Ollama's model_info per model, by digest: asked once per pulled model version.
_OLLAMA_FACTS: dict[str, tuple[str, dict[str, Any] | None]] = {}


async def _facts(row: Mapping[str, Any], cfg: Config, transport: httpx.AsyncBaseTransport | None) -> dict[str, Any] | None:
    if row["backend"] == "llamacpp":
        preset = cfg.llamacpp.preset(row["ref"].split("/", 1)[1])
        return await asyncio.to_thread(context_fit.gguf_metadata, preset.model_path) if preset else None
    name, digest = row["full"], str(row.get("_digest") or "")
    cached = _OLLAMA_FACTS.get(name)
    if cached is not None and cached[0] == digest and digest:
        return cached[1]
    info = await llm.model_info(name, transport=transport)
    _OLLAMA_FACTS[name] = (digest, info)
    return info


def _room_mb(ref: str, snap: vram.Snapshot, cfg: Config) -> int | None:
    """Graphics memory this model could have as the chat model: free now, plus what
    the other chat models (and its own copy) would give back. None when unknown."""
    if snap.gpu is None:
        return None
    keep = {f"local:ollama/{name}" for name in helper_models(cfg)} - {ref}
    leaving = [mb for r, mb in snap.held.items() if r not in keep]
    if any(mb is None for mb in leaving):
        return None
    return snap.gpu.free_mb + sum(mb or 0 for mb in leaving) - cfg.vram.headroom_mb


async def with_context(
    rows: list[dict[str, Any]], snap: vram.Snapshot | None, cfg: Config, transport: httpx.AsyncBaseTransport | None = None
) -> list[dict[str, Any]]:
    """Each local row's `context`: its longest context (`max`), the Chat memory it runs
    with (`value`), the longest that fits in graphics memory (`fit`, or None), and
    whether going past that spills to RAM (Ollama) or stops the load (llama.cpp)."""
    out = []
    for row in rows:
        info = None
        try:
            info = await _facts(row, cfg, transport)
        except Exception as exc:  # noqa: BLE001 -- a slider, never a reason to fail the list
            log.warning(f"chat memory facts skipped for {row['ref']}: {type(exc).__name__}: {exc}")
        info = info or {}
        row = {k: v for k, v in row.items() if k != "_digest"}
        shape = context_fit.kv_shape(info)
        room = _room_mb(row["ref"], snap, cfg) if snap is not None else None
        fit = (
            context_fit.fit_limit(room * 1024 * 1024, row["size_bytes"], shape)
            if shape is not None and room is not None and row.get("size_bytes")
            else None
        )
        largest = context_fit.context_max(info)
        row["context"] = {
            "max": largest,
            "value": context_fit.context_for(row["ref"], cfg),
            "fit": fit,
            "spills": row["backend"] == "ollama",
        } if largest else None
        out.append(row)
    return out


def _distinct(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Two rows with one short name get their quantization appended (D-084):
    "Qwen3.5 9B Q6_K_L" beside "Qwen3.5 9B Q4_K_M"."""
    seen: dict[str, int] = {}
    for row in rows:
        seen[row["label"]] = seen.get(row["label"], 0) + 1
    for row in rows:
        quant = row.pop("quant", None)
        if seen[row["label"]] > 1 and quant:
            row["label"] = f"{row['label']} {quant}"
    return rows


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
    local = _distinct(await asyncio.to_thread(llamacpp_rows, cfg.llamacpp) + local)  # stats files: off the loop
    try:
        local = await with_fits(local, rt, cfg)
    except Exception as exc:  # noqa: BLE001 -- a hint, never a reason to fail the list
        log.warning(f"fits hints skipped: {type(exc).__name__}: {exc}")
    try:
        snap = await _snapshot(rt)
    except Exception:  # noqa: BLE001 -- no GPU reading: the slider has no fit point
        snap = None
    local = await with_context(local, snap, cfg, transport)

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
    caps = (cfg.budget.hourly_usd, cfg.budget.daily_usd, cfg.budget.monthly_usd)
    caps_on = cfg.budget.enabled and any(cap >= 0 for cap in caps)
    api = api_rows(catalog, key_present=key_present, backend=status["id"] if status else "airouter", caps_on=caps_on, cfg=cfg)
    popular = popular_in([row["full"] for row in api])   # D-126: Settings' one-click sets

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
        # D-125: the model that answers when the chosen one can't
        "fallback_ref": cfg.chat.fallback_model_ref or local_ref(cfg),
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
        "api_presets": _key_targets(cfg),
        # D-126: Settings' one-click sets, and whether the list is the user's own
        "api_popular": popular,
        "api_own_list": isinstance(cfg.chat.api_models.get(status["id"] if status else "airouter"), (list, tuple)),
        "spend": spend,
    }
