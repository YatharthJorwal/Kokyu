"""Puts KASANE/ on sys.path so tests can `import llm`, `from audio import tts`, etc."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))


import pytest


@pytest.fixture(autouse=True)
def _no_real_model_loads(monkeypatch):
    """Opening a WebSocket asks the model loader for the thread's model (K1-10).
    No test may load a real model, so the loader is off unless a test turns it on."""
    import model_loader

    model_loader.LOADER.reset()
    monkeypatch.setattr(model_loader.LOADER, "enabled", False)
    yield
    model_loader.LOADER.reset()
