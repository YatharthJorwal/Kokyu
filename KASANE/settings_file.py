"""settings.json (K1-13b, FR-SET-2, D-070): what the user changes in Settings.

It sits over `config/config.yaml`: a key set here wins, every other key comes from
config.yaml, then the defaults. It holds only what Settings edits (the Ollama
address, the budget, a custom API endpoint, which screen companions start with
Kōkyū) in config.yaml's own layout, lives in
the app data folder, and is read at kernel start and after every change. A change
applies at once (`config.install`), no restart. config.yaml stays the developer's
and the advanced file.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import config
import paths
from provider_presets import API_PRESETS, PROVIDER_ID, url_problem

log = logging.getLogger(__name__)

VERSION = 1
THIS_PC = ("127.0.0.1", "localhost", "::1")
MAX_CAP_USD = 10_000.0
CAPS = ("hourly_usd", "daily_usd", "monthly_usd")
SCREEN = ("task_guide", "ocr_watch")

# One change at a time: read, change, write and apply happen together.
LOCK = asyncio.Lock()


class SettingsError(ValueError):
    """A change Settings cannot save. The message is shown to the user."""


def path() -> Path:
    return paths.app_data_dir() / "settings.json"


def read() -> dict[str, Any]:
    """The saved settings, {} when there are none. A broken file is ignored with a
    warning (the app still starts, on config.yaml alone)."""
    file = path()
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log.warning(f"settings: {file} could not be read and is ignored: {exc}")
        _keep_broken(file)
        return {}
    if not isinstance(data, dict):
        log.warning(f"settings: {file} is not a JSON object and is ignored")
        return {}
    data.pop("version", None)
    for key in [k for k, v in data.items() if not isinstance(v, dict)]:
        # every key here is a config.yaml section; a plain value would wipe that section
        log.warning(f"settings: '{key}' in {file} is not a section and is ignored")
        data.pop(key)
    return data


def _keep_broken(file: Path) -> None:
    """The next change rewrites settings.json from scratch: the unreadable one is copied
    to settings.json.broken first (once), so a typo never costs every saved setting."""
    broken = file.with_name(file.name + ".broken")
    if broken.exists():
        return
    try:
        broken.write_bytes(file.read_bytes())
        log.warning(f"settings: kept the unreadable file as {broken}")
    except OSError as exc:
        log.warning(f"settings: could not keep a copy of {file}: {exc}")


def write(data: dict[str, Any]) -> None:
    """Replaces the file in one step, so a crash never leaves half a file."""
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(file.name + ".tmp")
    tmp.write_text(json.dumps({"version": VERSION, **data}, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, file)


# ── checks ─────────────────────────────────────────────────────────────────────


def ollama_url_problem(url: str) -> str | None:
    """Ollama must run on this PC: what the companions see and hear goes to the local
    model and must never leave it (CLAUDE.md invariant 3)."""
    try:
        parts = urlsplit(url)
        parts.port   # raises on a port out of range
    except ValueError:
        return "That is not a web address."
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return "Use an address like http://127.0.0.1:11434."
    if parts.username or parts.password or parts.query or parts.fragment:
        return "The address must not carry a user name, a query or a fragment."
    if parts.hostname not in THIS_PC:
        return "Ollama must run on this PC (127.0.0.1 or localhost): what Kōkyū sees and hears never leaves it."
    return None


def custom_id(base_url: str) -> str:
    """A custom endpoint's provider id comes from its host, so a key saved for one
    host is never sent to another after the address is edited (D-059, D-070)."""
    parts = urlsplit(base_url)
    origin = f"{parts.scheme}://{parts.hostname}:{parts.port or ''}"
    return "custom_" + hashlib.sha256(origin.encode()).hexdigest()[:8]


def _drop(data: dict[str, Any], *keys: str) -> None:
    """Removes data[k1][k2]...; then any section it left empty."""
    trail = [data]
    for key in keys[:-1]:
        nxt = trail[-1].get(key)
        if not isinstance(nxt, dict):
            return
        trail.append(nxt)
    trail[-1].pop(keys[-1], None)
    for parent, key in zip(reversed(trail[:-1]), reversed(keys[:-1])):
        if parent.get(key) == {}:
            parent.pop(key)


def change(saved: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """`saved` with the requested changes, checked. Only the keys in `request`
    change; `ollama_url` "" and `custom_api` None go back to config.yaml's value.
    Raises SettingsError with a message for the user."""
    out = copy.deepcopy(saved)

    if "ollama_url" in request:
        url = (request["ollama_url"] or "").strip().rstrip("/")
        _drop(out, "llm", "base_url")
        _drop(out, "providers", "local_ollama", "base_url")
        if url:
            problem = ollama_url_problem(url)
            if problem:
                raise SettingsError(problem)
            # config.yaml may set it in either place (the legacy `llm:` one wins there)
            out.setdefault("llm", {})["base_url"] = url
            out.setdefault("providers", {}).setdefault("local_ollama", {})["base_url"] = url

    if "budget" in request:
        asked = request["budget"] or {}
        budget: dict[str, Any] = {"enabled": bool(asked.get("enabled", True))}
        for key in CAPS:
            value = asked.get(key)
            if value is None:
                budget[key] = -1.0   # no cap (BudgetConfig: a negative cap is unlimited)
                continue
            value = float(value)
            if not 0 <= value <= MAX_CAP_USD:
                raise SettingsError(f"A cap must be between $0 and ${MAX_CAP_USD:,.0f}, or empty for no cap.")
            budget[key] = value
        out["budget"] = {**out.get("budget", {}), **budget}

    if "custom_api" in request:
        for key in ("enabled", "preset", "label", "base_url", "models_url", "api_key_env", "price_unit", "models_cache"):
            _drop(out, "providers", "airouter", key)
        custom = request["custom_api"]
        if custom is not None:
            label = str(custom.get("label") or "").strip()
            url = str(custom.get("base_url") or "").strip().rstrip("/")
            if not label or len(label) > 40:
                raise SettingsError("Give the endpoint a name of at most 40 characters.")
            problem = url_problem(url)
            if problem:
                raise SettingsError(f"The address {problem}.")
            pid = custom_id(url)
            out.setdefault("providers", {}).setdefault("airouter", {}).update({
                "enabled": True,
                "preset": pid,
                "label": label,
                "base_url": url,
                "models_url": "",          # its own /models
                "api_key_env": "",         # never a developer key: only a key saved for it in the app
                "price_unit": "none",      # unknown prices (D-058)
                "models_cache": f"data/{pid}_models.json",
            })

    if "screen" in request:
        for mode, on in (request["screen"] or {}).items():
            if mode in SCREEN and on is not None:
                out.setdefault(mode, {})["on_at_start"] = bool(on)

    if "context" in request:
        # D-098: Chat memory per model, in config.yaml's own layout (llm.context_by_model).
        asked = request["context"] or {}
        ref = str(asked.get("ref") or "").strip()
        if not ref:
            raise SettingsError("Pick a model first.")
        by_model = dict((out.get("llm") or {}).get("context_by_model") or {})
        tokens = asked.get("tokens")
        if tokens is None:
            by_model.pop(ref, None)
        else:
            by_model[ref] = int(tokens)
        if by_model:
            out.setdefault("llm", {})["context_by_model"] = by_model
        else:
            _drop(out, "llm", "context_by_model")

    if "fallback" in request:
        # D-125: no model = the local chat model; the mode is always written.
        asked = request["fallback"] or {}
        _drop(out, "chat", "fallback_model_ref")
        if asked.get("model_ref"):
            out.setdefault("chat", {})["fallback_model_ref"] = str(asked["model_ref"])
        mode = asked.get("mode") or "ask"
        if mode not in ("ask", "auto"):
            raise SettingsError("Choose Ask me or Answer by itself.")
        out.setdefault("chat", {})["on_model_failure"] = mode

    if "api_models" in request:
        # D-126: the picker's API list for one endpoint; None = its popular models again.
        asked = request["api_models"] or {}
        endpoint = str(asked.get("endpoint") or "")
        if not PROVIDER_ID.match(endpoint):
            raise SettingsError("That endpoint is unknown.")
        lists = dict((out.get("chat") or {}).get("api_models") or {})
        models = asked.get("models")
        if models is None:
            lists.pop(endpoint, None)
        else:
            ids = list(dict.fromkeys(str(m).strip() for m in models if str(m).strip()))
            if any(len(m) > 200 for m in ids):
                raise SettingsError("A model id is too long.")
            lists[endpoint] = ids
        _drop(out, "chat", "api_models")
        if lists:
            out.setdefault("chat", {})["api_models"] = lists

    if "read_aloud" in request:
        # D-097: the composer's Read aloud, kept between restarts.
        out.setdefault("tts", {})["read_aloud"] = bool(request["read_aloud"])
    return out


# ── the running config ───────────────────────────────────────────────────────


async def _build(saved: dict[str, Any]) -> config.Config:
    return await asyncio.to_thread(config.load_config, quiet=True, overlay=saved)


async def save(saved: dict[str, Any]) -> config.Config:
    """Builds the config with `saved` over config.yaml, writes the file, then makes
    the config the running one. Nothing changes if building or writing fails."""
    cfg = await _build(saved)
    await asyncio.to_thread(write, saved)
    config.install(cfg)
    return cfg


async def apply_saved() -> None:
    """At kernel start, before anything builds on the config. A file that does not
    build is ignored with a warning: the app starts on config.yaml alone."""
    saved = await asyncio.to_thread(read)
    if not saved:
        return
    try:
        cfg = await _build(saved)
    except Exception as exc:  # noqa: BLE001 - any bad value in a hand-edited file
        log.warning(f"settings: {path()} is ignored, it does not apply over config.yaml: {exc}")
        return
    config.install(cfg)
    log.info(f"settings: {path()} applied over config.yaml")


def view(cfg: config.Config, saved: dict[str, Any], problem: str | None = None) -> dict[str, Any]:
    """What Settings shows: the values in effect, and which come from settings.json."""
    slot = cfg.providers.get("airouter")
    custom = None
    if slot is not None and slot.preset and slot.preset not in API_PRESETS:
        custom = {"id": slot.preset, "label": slot.label, "base_url": slot.base_url}
    budget = cfg.budget

    def cap(value: float) -> float | None:
        return None if value < 0 else value

    providers = saved.get("providers") if isinstance(saved.get("providers"), dict) else {}
    return {
        "ollama_url": cfg.llm.base_url,
        "budget": {
            "enabled": budget.enabled,
            "hourly_usd": cap(budget.hourly_usd),
            "daily_usd": cap(budget.daily_usd),
            "monthly_usd": cap(budget.monthly_usd),
        },
        "custom_api": custom,
        "screen": {"task_guide": cfg.task_guide.on_at_start, "ocr_watch": cfg.ocr_watch.on_at_start},
        # D-125: None = the local chat model (model_list's fallback_ref names it)
        "fallback": {"model_ref": cfg.chat.fallback_model_ref, "mode": cfg.chat.on_model_failure},
        "saved": sorted(
            name for name, here in (
                ("ollama_url", "base_url" in (saved.get("llm") or {})),
                ("budget", "budget" in saved),
                ("custom_api", "preset" in (providers.get("airouter") or {})),
                ("screen", any("on_at_start" in (saved.get(mode) or {}) for mode in SCREEN)),
                ("fallback", "on_model_failure" in (saved.get("chat") or {})),
            ) if here
        ),
        "file": str(path()),
        "problem": problem,
    }
