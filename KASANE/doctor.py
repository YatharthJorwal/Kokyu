"""The Doctor panel's checks (K1-13; FR-SET-3, FR-COMP-5).

One row per component: the kernel, Ollama, the chat and embedding models,
llama.cpp, the voice backend, speech-to-text, the GPU and the API endpoint.
Each says `ok`, `warn`, `fail` or `off` (not in use, nothing wrong), what it
found, and how to fix it. Every check is read-only and quick; none starts or
loads anything, and none raises: a check that cannot run reports why.
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import platform
from typing import Any

import httpx

import vram
from audio import stt, tts, voice_mode
from config import CONFIG, Config
from router.decision import LOCAL_PROVIDER, model_for
from router.providers.llamacpp import resolve_server

log = logging.getLogger(__name__)

OK, WARN, FAIL, OFF = "ok", "warn", "fail", "off"


def _row(id_: str, label: str, state: str, detail: str, hint: str | None = None) -> dict[str, Any]:
    return {"id": id_, "label": label, "state": state, "detail": detail, "hint": hint}


async def _get_json(url: str, timeout: float = 3.0) -> Any | None:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=1.5)) as client:
            response = await client.get(url)
        return response.json() if response.status_code < 400 else None
    except (httpx.HTTPError, ValueError):
        return None


def _bare(name: str) -> str:
    return name.removesuffix(":latest")


async def ollama_rows(cfg: Config) -> list[dict[str, Any]]:
    base = cfg.llm.base_url.rstrip("/")
    version = await _get_json(f"{base}/api/version")
    if version is None:
        return [_row("ollama", "Ollama", FAIL, f"Not reachable at {base}",
                     "Start Ollama (it sits in the tray once installed), or set llm.base_url in config.yaml.")]
    rows = [_row("ollama", "Ollama", OK, f"Version {version.get('version', '?')} at {base}")]
    tags = await _get_json(f"{base}/api/tags") or {}
    pulled = {_bare(str(m.get("name", ""))) for m in tags.get("models") or [] if isinstance(m, dict)}
    chat = _bare(model_for(LOCAL_PROVIDER, "reflex", cfg.models))
    rows.append(
        _row("chat_model", "Default local model", OK, chat) if chat in pulled
        else _row("chat_model", "Default local model", WARN, f"{chat} is not pulled", f"Run: ollama pull {chat}")
    )
    embed = _bare(cfg.memory.embedding.model or "")
    if embed:
        rows.append(
            _row("embeddings", "Memory (embeddings)", OK, embed) if embed in pulled
            else _row("embeddings", "Memory (embeddings)", FAIL, f"{embed} is not pulled: recall is off",
                      f"Run: ollama pull {embed}")
        )
    return rows


def llamacpp_row(cfg: Config, running: str | None) -> dict[str, Any]:
    presets = cfg.llamacpp.presets
    if not presets:
        return _row("llamacpp", "llama.cpp", OFF, "No presets (optional: for large MoE models)")
    server = resolve_server(cfg.llamacpp)
    if server is None:
        return _row("llamacpp", "llama.cpp", FAIL, "llama-server not found",
                    "Set llamacpp.server_path in config.yaml, or install Ollama (it bundles llama-server).")
    from pathlib import Path

    missing = [p.id for p in presets if not Path(p.model_path).is_file()]
    if missing:
        return _row("llamacpp", "llama.cpp", WARN, f"Model file missing for {', '.join(missing)}",
                    "Fix model_path for those presets in config.yaml.")
    state = f"running {running}" if running else "starts when you pick one of its models"
    return _row("llamacpp", "llama.cpp", OK, f"{len(presets)} preset(s), {state}")


async def voice_row(cfg: Config) -> dict[str, Any]:
    if cfg.tts.engine != "gpt_sovits":
        return _row("tts", "Voice (TTS)", OFF, f"Engine: {cfg.tts.engine}")
    if await tts.health():
        return _row("tts", "Voice (TTS)", OK, f"GPT-SoVITS answering at {cfg.tts.gpt_sovits.api_url}")
    if not voice_mode.VOICE.on:
        return _row("tts", "Voice (TTS)", OFF, "Starts when you turn voice on")   # D-061
    return _row("tts", "Voice (TTS)", FAIL, f"GPT-SoVITS not answering at {cfg.tts.gpt_sovits.api_url}",
                "Check tts.gpt_sovits.launch in config.yaml and logs/gpt_sovits.log.")


def stt_row(cfg: Config) -> dict[str, Any]:
    if importlib.util.find_spec("faster_whisper") is None:
        return _row("stt", "Speech to text", FAIL, "faster-whisper is not installed",
                    "Install the kernel's requirements (pip install -r KASANE/requirements.txt).")
    loaded = getattr(stt, "_model", None) is not None
    where = f"{cfg.stt.model_size} on {cfg.stt.device}"
    return _row("stt", "Speech to text", OK, f"{where}, {'loaded' if loaded else 'loads when voice turns on'}")


async def gpu_row(cfg: Config, running: str | None = None) -> dict[str, Any]:
    gpu = await vram.gpu_memory()
    if gpu is None:
        return _row("gpu", "GPU memory", WARN, "No reading from an NVIDIA driver",
                    "Local models may run on the CPU (slowly). Fits hints and load checks are off.")
    # A full card is normal when Kokyu's own models fill it; only other programs' share is worth a warning.
    ours = sum(vram.parse_ollama_ps(await _get_json(f"{cfg.llm.base_url.rstrip('/')}/api/ps")).values())
    if running:   # shortcut: an unmeasured llama-server counts as 0 MB (as "other programs") until it is measured
        ours += await asyncio.to_thread(vram.MEASURED.get, f"local:llamacpp/{running}") or 0
    others = max(gpu.used_mb - ours, 0)
    state = WARN if gpu.free_mb < 1024 and others > ours else OK
    hint = "Other programs hold most of the graphics memory: close the ones you do not need, or pick a smaller model."
    detail = (f"{gpu.name}: {gpu.free_mb / 1024:.1f} GB free of {gpu.total_mb / 1024:.1f} GB "
              f"(Kōkyū's models {ours / 1024:.1f} GB, other programs {others / 1024:.1f} GB)")
    return _row("gpu", "GPU memory", state, detail, hint if state == WARN else None)


def api_row(rt: Any) -> dict[str, Any]:
    status = rt.api_status() if hasattr(rt, "api_status") else None
    name = (status or {}).get("label") or "API"
    if not getattr(rt, "api_key_present", False):
        return _row("api", f"API models ({name})", OFF, "No API key", "Add one with Key in the model picker.")
    catalog = getattr(rt, "catalog", None)
    if catalog is None or not catalog.available:
        error = getattr(catalog, "last_error", None) if catalog is not None else None
        return _row("api", f"API models ({name})", FAIL, f"No model list{f': {error}' if error else ''}",
                    "Check the key and your connection, then refresh the list in the model picker.")
    count = len(catalog.model_ids())
    if catalog.is_stale() or catalog.last_error:
        return _row("api", f"API models ({name})", WARN, f"{count} models, from an old list",
                    "Refresh the list in the model picker.")
    return _row("api", f"API models ({name})", OK, f"Key saved, {count} models")


async def report(rt: Any, cfg: Config | None = None) -> list[dict[str, Any]]:
    """Every check, in the panel's order. Never raises."""
    cfg = cfg or CONFIG
    rows: list[dict[str, Any]] = [_row("kernel", "Engine (KASANE)", OK, f"Running (Python {platform.python_version()})")]
    try:
        running = rt.llamacpp_preset() if hasattr(rt, "llamacpp_preset") else None
        local, voice, gpu = await asyncio.gather(ollama_rows(cfg), voice_row(cfg), gpu_row(cfg, running))
        rows += [*local, llamacpp_row(cfg, running), voice, stt_row(cfg), gpu, api_row(rt)]
    except Exception as exc:  # noqa: BLE001 -- the panel must still say something
        log.warning(f"doctor: a check failed: {type(exc).__name__}: {exc}")
        rows.append(_row("doctor", "Doctor", FAIL, f"A check could not run: {exc}", "See logs/kasane.log."))
    return rows
