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
def _no_gpu(monkeypatch):
    """No test reads the real GPU or remembers a measurement between tests (K1-09):
    the VRAM manager sees no GPU unless a test gives it one."""
    import vram

    async def no_gpu():
        return None

    monkeypatch.setattr(vram, "gpu_memory", no_gpu)
    monkeypatch.setattr(vram, "MEASURED", vram.MeasuredCache())


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
def _read_aloud_off():
    """Read aloud is kernel-wide (D-097): every test starts with it off and its voice
    idle, and ends with the running config it started with (turning Read aloud on
    saves settings.json and installs a new config)."""
    import dataclasses

    import config
    from audio import read_aloud

    original = config.CONFIG
    if original.tts.read_aloud:
        config.install(dataclasses.replace(original, tts=dataclasses.replace(original.tts, read_aloud=False)))
    read_aloud.READ_ALOUD = read_aloud.ReadAloud()
    yield
    if config.CONFIG is not original:
        config.install(original)


@pytest.fixture
def read_aloud_on(monkeypatch):
    """Read aloud on and its voice up, for one test: no settings.json, no voice server.
    _read_aloud_off puts the config back afterwards."""
    import dataclasses

    import config
    from audio import read_aloud

    cfg = config.CONFIG
    config.install(dataclasses.replace(cfg, tts=dataclasses.replace(cfg.tts, read_aloud=True)))

    async def ready() -> bool:
        return True

    monkeypatch.setattr(read_aloud.READ_ALOUD, "ready", ready)
    return read_aloud.READ_ALOUD
