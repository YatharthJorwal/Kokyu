"""Puts KASANE/ on sys.path so tests can `import llm`, `from audio import tts`, etc."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))


import logging

import pytest


@pytest.fixture(autouse=True)
def _info_logs(caplog):
    """The kernel logs through `logging` (R-13); tests read its lines from `caplog.text`."""
    caplog.set_level(logging.INFO)


@pytest.fixture(autouse=True)
def _no_real_model_loads(monkeypatch):
    """Opening a WebSocket asks the model loader for the thread's model (K1-10).
    No test may load a real model, so the loader is off unless a test turns it on."""
    import model_loader

    model_loader.LOADER.reset()
    monkeypatch.setattr(model_loader.LOADER, "enabled", False)
    yield
    model_loader.LOADER.reset()


@pytest.fixture(autouse=True)
def _throwaway_data_dir(tmp_path_factory, monkeypatch):
    """No test writes the developer's real data or logs (audit.jsonl, spend.db,
    threads): KOKYU_DATA_DIR points at a throwaway folder, and the router singleton
    is rebuilt there on first use. Subprocesses inherit the variable."""
    import router

    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path_factory.mktemp("data")))
    monkeypatch.setattr(router, "_router", None)


@pytest.fixture(autouse=True)
def _no_app_keys():
    """No test inherits a key another test saved through shell_keys (D-059)."""
    import shell_keys

    shell_keys.clear()
    yield
    shell_keys.clear()


@pytest.fixture(autouse=True)
def _voice_off():
    """Voice mode is kernel-wide (D-061): every test starts with it off and idle."""
    from audio import voice_mode

    voice_mode.VOICE = voice_mode.VoiceMode()
    yield
