"""K1-10 (FR-M-6, D-054): the background chat-model loader and its status."""
from __future__ import annotations

import asyncio

import pytest

from model_loader import FAILED, IDLE, LOADING, READY, ModelLoader, failure_text


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def make(**kw):
    """A loader whose loads finish when the test releases them."""
    gates: dict[str, asyncio.Event] = {}
    started: list[str] = []
    cancelled: list[str] = []
    failures: dict[str, Exception] = {}

    async def warm(ref: str) -> None:
        started.append(ref)
        gate = gates.setdefault(ref, asyncio.Event())
        try:
            await gate.wait()
        except asyncio.CancelledError:
            cancelled.append(ref)
            raise
        if ref in failures:
            raise failures[ref]

    loader = ModelLoader(warm, **kw)
    seen: list[tuple[str, str | None]] = []

    async def listener(status):
        seen.append((status["state"], status["model_ref"]))

    loader.subscribe(listener)
    return loader, gates, started, cancelled, failures, seen


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_a_load_goes_loading_then_ready_and_reports_the_time():
    clock = Clock()
    loader, gates, started, _, _, seen = make(clock=clock, label=lambda ref: ref.upper())
    assert loader.status()["state"] == IDLE
    task = loader.request("local:llamacpp/big")
    await settle()
    assert seen == [(LOADING, "local:llamacpp/big")]
    clock.t += 42.0
    assert loader.status()["elapsed_s"] == 42.0           # the window counts from here
    assert loader.status()["label"] == "LOCAL:LLAMACPP/BIG"
    gates["local:llamacpp/big"].set()
    await task
    assert seen[-1] == (READY, "local:llamacpp/big") and started == ["local:llamacpp/big"]
    clock.t += 100.0
    assert loader.status()["elapsed_s"] == 42.0           # frozen once ready


@pytest.mark.asyncio
async def test_asking_for_the_same_model_twice_loads_it_once():
    loader, gates, started, _, _, _ = make()
    gates["local:ollama/a"] = asyncio.Event()
    first = loader.request("local:ollama/a")
    assert loader.request("local:ollama/a") is first      # still loading: the same task
    gates["local:ollama/a"].set()
    await first
    assert loader.request("local:ollama/a") is None       # already up: nothing to do
    assert started == ["local:ollama/a"]


@pytest.mark.asyncio
async def test_a_new_pick_cancels_the_load_in_progress():
    loader, gates, started, cancelled, _, seen = make()
    loader.request("local:llamacpp/big")
    await settle()
    second = loader.request("local:ollama/small")         # the user changed their mind
    await settle()
    assert cancelled == ["local:llamacpp/big"]
    gates["local:ollama/small"].set()
    await second
    assert started == ["local:llamacpp/big", "local:ollama/small"]
    assert seen[-1] == (READY, "local:ollama/small") and loader.model_ref == "local:ollama/small"


@pytest.mark.asyncio
async def test_a_delayed_request_waits_and_going_back_to_the_loaded_model_cancels_it():
    loader, gates, started, _, _, _ = make()
    gates["local:ollama/a"] = asyncio.Event()
    gates["local:ollama/a"].set()
    await loader.request("local:ollama/a")
    loader.request("local:llamacpp/big", delay_s=5)         # opened an old thread
    await settle()
    assert started == ["local:ollama/a"]                    # nothing heavy yet
    assert loader.request("local:ollama/a", delay_s=5) is None  # clicked back within the pause
    await settle()
    assert not loader.busy() and loader.state == READY and started == ["local:ollama/a"]


@pytest.mark.asyncio
async def test_a_failed_load_says_why_and_try_again_runs_it_again():
    loader, gates, started, _, failures, seen = make()
    failures["local:llamacpp/big"] = RuntimeError("model file for 'big' not found: D:\\models\\big.gguf\nmore detail")
    gates["local:llamacpp/big"] = asyncio.Event()
    gates["local:llamacpp/big"].set()
    await loader.request("local:llamacpp/big")
    status = loader.status()
    assert status["state"] == FAILED and status["message"] == "model file for 'big' not found: D:\\models\\big.gguf"
    again = loader.request("local:llamacpp/big")
    assert again is not None                                  # not stuck on the failure
    await again                                               # (fails again: same cause)
    del failures["local:llamacpp/big"]
    await loader.request("local:llamacpp/big", force=True)
    assert loader.state == READY and len(started) == 3


@pytest.mark.asyncio
async def test_a_reply_clears_a_stale_failure():
    loader, gates, _, _, failures, seen = make()
    failures["local:ollama/a"] = ConnectionError("Ollama is not running")
    gates["local:ollama/a"] = asyncio.Event()
    gates["local:ollama/a"].set()
    await loader.request("local:ollama/a")
    await loader.mark_ready("local:ollama/other")             # another model: unchanged
    assert loader.state == FAILED
    await loader.mark_ready("local:ollama/a")
    assert loader.state == READY and seen[-1] == (READY, "local:ollama/a")


@pytest.mark.asyncio
async def test_api_models_are_ready_at_once_and_a_closed_window_does_not_break_the_others():
    loader, _, started, _, _, seen = make(instant=lambda ref: ref.startswith("api:"))

    async def closed(status):
        raise RuntimeError("websocket closed")

    loader.subscribe(closed)
    await loader.request("api:airouter/x")
    assert started == [] and seen == [(READY, "api:airouter/x")] and loader.status()["elapsed_s"] is None


@pytest.mark.asyncio
async def test_disabled_or_unconfigured_loaders_do_nothing_and_stop_cancels():
    assert ModelLoader().request("local:ollama/a") is None      # no warm function yet
    loader, gates, started, cancelled, _, _ = make()
    loader.enabled = False
    assert loader.request("local:ollama/a") is None and started == []
    loader.enabled = True
    loader.request("local:llamacpp/big")
    await settle()
    await loader.stop()                                         # kernel shutdown
    assert cancelled == ["local:llamacpp/big"] and not loader.busy()


def test_failure_text_is_one_short_line():
    assert failure_text(RuntimeError("")) == "RuntimeError"
    assert failure_text(RuntimeError("a\nb")) == "a"
    assert len(failure_text(RuntimeError("x" * 1000))) == 240
