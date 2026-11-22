"""Ollama started when a model needs it (D-105). Never the real one: spawn is faked."""
from __future__ import annotations

import importlib

import pytest

import ollama_service as stubbed


@pytest.fixture
def svc(monkeypatch):
    """The real module (conftest replaces ensure and spawn), with spawn and is_up faked."""
    real = importlib.reload(stubbed)
    started: list[str] = []
    state = {"up": False, "calls": 0}

    async def is_up(base_url, transport=None):
        state["calls"] += 1
        return state["up"]

    def spawn(exe):
        started.append(str(exe))
        state["up"] = True

    monkeypatch.setattr(real, "is_up", is_up)
    monkeypatch.setattr(real, "spawn", spawn)
    monkeypatch.setattr(real, "find_exe", lambda: "C:/ollama.exe")
    return real, started, state


@pytest.mark.asyncio
async def test_a_running_ollama_is_left_alone(svc):
    real, started, state = svc
    state["up"] = True
    assert await real.ensure("http://127.0.0.1:11434") is True
    assert started == []


@pytest.mark.asyncio
async def test_a_stopped_local_ollama_is_started_and_waited_for(svc):
    real, started, _ = svc
    assert await real.ensure("http://127.0.0.1:11434", poll_s=0) is True
    assert started == ["C:/ollama.exe"]


@pytest.mark.asyncio
async def test_a_remote_server_is_never_started(svc):
    real, started, _ = svc
    assert await real.ensure("http://192.168.1.20:11434") is False
    assert started == []


@pytest.mark.asyncio
async def test_no_ollama_installed_is_a_plain_failure(svc, monkeypatch):
    real, started, _ = svc
    monkeypatch.setattr(real, "find_exe", lambda: None)
    assert await real.ensure("http://localhost:11434") is False
    assert started == []


@pytest.mark.asyncio
async def test_it_gives_up_when_ollama_never_answers(svc, monkeypatch):
    real, started, state = svc
    monkeypatch.setattr(real, "spawn", lambda exe: started.append(exe))   # starts, never comes up
    assert await real.ensure("http://127.0.0.1:11434", wait_s=0.05, poll_s=0.01) is False
    assert started == ["C:/ollama.exe"]
