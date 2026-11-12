"""paths.py is the only module that knows where things live (RULES R-40)."""
from __future__ import annotations

from pathlib import Path

import pytest

import paths


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (paths.ENV_DATA_DIR, paths.ENV_RESOURCE_DIR, paths.ENV_PACKAGED):
        monkeypatch.delenv(name, raising=False)


def test_dev_layout_hangs_off_the_repo_root():
    root = paths.repo_root()
    assert (root / "KASANE").is_dir()
    assert paths.app_data_dir() == root / "data"
    assert paths.logs_dir() == root / "logs"
    assert paths.config_dir() == root / "config"
    assert paths.waifus_dir() == root / "data" / "waifus"
    assert paths.premade_dir() == root / "assets" / "premade"
    assert paths.config_example_path() == root / "config" / "config.example.yaml"
    assert paths.config_example_path().is_file()


def test_resolve_maps_config_style_paths_in_dev():
    root = paths.repo_root()
    assert paths.resolve("data/spend.db") == root / "data" / "spend.db"
    assert paths.resolve("logs/audit.jsonl") == root / "logs" / "audit.jsonl"
    assert paths.resolve("config/config.yaml") == root / "config" / "config.yaml"
    assert paths.resolve("something/else.txt") == root / "something" / "else.txt"


def test_resolve_leaves_absolute_paths_alone(tmp_path):
    assert paths.resolve(tmp_path / "x.db") == tmp_path / "x.db"


def test_data_dir_override_redirects_everything_user_owned(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.ENV_DATA_DIR, str(tmp_path))
    assert paths.app_data_dir() == tmp_path
    assert paths.logs_dir() == tmp_path / "logs"
    assert paths.config_dir() == tmp_path / "config"
    assert paths.waifus_dir() == tmp_path / "waifus"
    assert paths.resolve("data/memory.db") == tmp_path / "memory.db"
    assert paths.resolve("logs/a.log") == tmp_path / "logs" / "a.log"
    # read-only resources are not user data and do not move
    assert paths.premade_dir() == paths.repo_root() / "assets" / "premade"


def test_packaged_mode_uses_appdata_and_resource_dir(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.ENV_PACKAGED, "1")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv(paths.ENV_RESOURCE_DIR, str(tmp_path / "res"))
    assert paths.is_packaged()
    assert paths.app_data_dir() == tmp_path / "Roaming" / "Kokyu"
    assert paths.logs_dir() == tmp_path / "Roaming" / "Kokyu" / "logs"
    assert paths.premade_dir() == tmp_path / "res" / "assets" / "premade"
    assert paths.resolve("data/memory.db") == tmp_path / "Roaming" / "Kokyu" / "memory.db"
    assert paths.resolve("other.txt") == tmp_path / "Roaming" / "Kokyu" / "other.txt"


def test_no_module_builds_data_paths_from_file():
    """Guard: kernel modules must not rebuild data/logs paths from __file__ (R-40)."""
    root = paths.repo_root() / "KASANE"
    offenders = []
    for py in root.rglob("*.py"):
        if "tests" in py.parts or py.name == "paths.py" or "voice_files" in py.parts:
            continue
        text = py.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "__file__" in line and any(w in line for w in ('"data"', "'data'", '"logs"', "'logs'", "config.db", "_DB_PATH")):
                offenders.append(f"{py.relative_to(root)}: {line.strip()}")
    assert not offenders, offenders
