"""Every filesystem location the kernel uses, in one place (RULES R-40).

Development: the repo checkout (`./data`, `./logs`, `./config`).
Packaged (K7): per-user data under `%APPDATA%\\Kokyu` and read-only resources next to
the app. Tests and tools can redirect everything with `KOKYU_DATA_DIR`.

No other module should build a path from `__file__` or hard-code `data/`, `logs/` or
`config/`. Ask this module.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Kokyu"

ENV_DATA_DIR = "KOKYU_DATA_DIR"            # redirect all user data (tests, portable runs)
ENV_RESOURCE_DIR = "KOKYU_RESOURCE_DIR"    # redirect read-only bundled resources
ENV_PACKAGED = "KOKYU_PACKAGED"            # "1" forces packaged behaviour (testing)


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False)) or os.environ.get(ENV_PACKAGED) == "1"


def repo_root() -> Path:
    """The development checkout (the folder that contains KASANE/)."""
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Read-only files that ship with the app: premade companions, config example, templates."""
    override = os.environ.get(ENV_RESOURCE_DIR)
    if override:
        return Path(override)
    if is_packaged():
        bundled = getattr(sys, "_MEIPASS", None)
        return Path(bundled) if bundled else Path(sys.executable).resolve().parent
    return repo_root()


def app_data_dir() -> Path:
    """Where user data lives: databases, waifus, attachments, caches."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override)
    if is_packaged():
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    return repo_root() / "data"


def _redirected() -> bool:
    return bool(os.environ.get(ENV_DATA_DIR)) or is_packaged()


def logs_dir() -> Path:
    # Development keeps ./logs because the Rust shell and scripts/dev.mjs write there.
    return app_data_dir() / "logs" if _redirected() else repo_root() / "logs"


def config_dir() -> Path:
    return app_data_dir() / "config" if _redirected() else repo_root() / "config"


def config_example_path() -> Path:
    return resource_dir() / "config" / "config.example.yaml"


def secrets_path() -> Path:
    return config_dir() / "secrets.local.yaml"


def dotenv_path() -> Path:
    """Developer-only `.env` (end-user keys will live in the Credential Manager, D-037)."""
    return app_data_dir() / ".env" if _redirected() else repo_root() / ".env"


def waifus_dir() -> Path:
    """User-created companions (read/write)."""
    return app_data_dir() / "waifus"


def premade_dir() -> Path:
    """Built-in companions (read-only, D-041)."""
    return resource_dir() / "assets" / "premade"


def resolve(value: str | os.PathLike[str]) -> Path:
    """Maps a config-style relative path to a real location.

    `data/x` -> app data, `logs/x` -> logs dir, `config/x` -> config dir. Any other
    relative path hangs off the repo root in development and off the data dir when
    packaged. Absolute paths are returned unchanged.
    """
    path = Path(value)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts:
        head, rest = parts[0], Path(*parts[1:]) if len(parts) > 1 else Path()
        if head == "data":
            return app_data_dir() / rest
        if head == "logs":
            return logs_dir() / rest
        if head == "config":
            return config_dir() / rest
    return (app_data_dir() if is_packaged() else repo_root()) / path
