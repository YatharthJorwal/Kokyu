"""Which effort levels a model offers, and what each one means to its backend
(FR-M-8, FR-M-10, D-064).

Local models: `config/models.yaml` (the user's, optional), then the shipped
`config/models.example.yaml`; the first entry whose `match` pattern fits the
model ref wins. API models: a model the catalog marks as reasoning offers low,
medium and high, sent as the provider's `reasoning_effort`
(`model_ref.openai_reasoning_effort`).
"""

from __future__ import annotations

import fnmatch
import logging
from collections.abc import Iterable
from pathlib import Path

import yaml

import paths
from router.model_ref import EFFORTS

log = logging.getLogger(__name__)

API_EFFORTS = ("low", "medium", "high")
THINK_LEVELS = ("low", "medium", "high")   # Ollama's `think` levels (gpt-oss)

# (pattern, {effort: think value}); think is a bool or one of THINK_LEVELS
Entry = tuple[str, dict[str, bool | str]]

_entries: list[Entry] | None = None


def _read(path: Path) -> list[Entry]:
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning(f"capabilities: could not read {path.name}: {exc}")
        return []
    entries: list[Entry] = []
    for item in (data.get("local") if isinstance(data, dict) else None) or []:
        pattern = item.get("match") if isinstance(item, dict) else None
        efforts = item.get("efforts") if isinstance(item, dict) else None
        if not isinstance(pattern, str) or not isinstance(efforts, dict):
            log.warning(f"capabilities: {path.name}: an entry needs `match` and `efforts`; skipped {item!r}")
            continue
        # YAML 1.1 reads an unquoted `off` key as False; that is the level "off".
        levels = {("off" if level is False else level): think for level, think in efforts.items()}
        good = {
            level: think
            for level, think in levels.items()
            if level in EFFORTS and (isinstance(think, bool) or think in THINK_LEVELS)
        }
        if len(good) != len(efforts):
            log.warning(f"capabilities: {path.name}: {pattern}: unknown levels or values ignored")
        entries.append((pattern.lower(), good))
    return entries


def local_entries() -> list[Entry]:
    """The user's entries first, then the shipped ones. Read once per process."""
    global _entries
    if _entries is None:
        _entries = _read(paths.models_path()) + _read(paths.models_example_path())
    return _entries


def reload() -> None:
    """Forget what was read (tests; a Settings page that edits the file)."""
    global _entries
    _entries = None


def _local(ref: str) -> dict[str, bool | str] | None:
    # fnmatchcase on lowercased text: plain fnmatch would turn "/" into "\" on Windows
    low = ref.lower()
    return next((efforts for pattern, efforts in local_entries() if fnmatch.fnmatchcase(low, pattern)), None)


def efforts_for(ref: str, tags: Iterable[str] = ()) -> list[str]:
    """The effort slider's detents for a model, lowest first; empty means no slider."""
    if ref.startswith("api:"):
        return list(API_EFFORTS) if {"reasoning", "thinking"} & {str(t).lower() for t in tags} else []
    efforts = _local(ref) or {}
    return [level for level in EFFORTS if level in efforts]


def think_for(ref: str, effort: str | None) -> bool | str | None:
    """What a local backend gets as `think` for this effort. None leaves the
    model's default (`llm.think` in config.yaml): no effort picked, a model with
    no entry, or a level the model does not offer."""
    if effort is None:
        return None
    return (_local(ref) or {}).get(effort)
