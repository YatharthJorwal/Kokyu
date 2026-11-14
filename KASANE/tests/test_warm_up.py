"""K1-01b (D-052), K1-10 (D-054): at boot the kernel loads the model the first
message will use, through the model loader, so windows can show it waking up."""
from __future__ import annotations

import asyncio
import dataclasses

import pytest

import app
import router
from config import ChatConfig
from router.decision import LOCAL_PROVIDER, model_for
from router.types import ModelChunk


@pytest.fixture
def calls(monkeypatch, tmp_path):
    seen: dict[str, list] = {"helpers": [], "load": [], "warm": [], "embed": [], "stopped": [], "status": [], "order": []}

    async def helper_warm(model=None):
        seen["helpers"].append(model)

    async def load(model=None):
        seen["load"].append(model)
        seen["order"].append("load")

    class FakeRouter:
        async def warm(self, ref, messages, tools):
            seen["warm"].append((ref, messages, tools))

        async def stop_llamacpp(self):
            seen["stopped"].append(True)
            seen["order"].append("stop")
            return True

    async def embed(text):
        seen["embed"].append(text)
        return [0.0]

    async def listener(status):
        seen["status"].append((status["state"], status["model_ref"]))

    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(app, "_conversation_manager", None)
    monkeypatch.setattr(app.llm, "warm_up_model", helper_warm)
    monkeypatch.setattr(app.llm, "load_model", load)
    monkeypatch.setattr(app.embeddings, "embed", embed)
    monkeypatch.setattr(app.router, "get_router", lambda: FakeRouter())
    monkeypatch.setattr(app.model_loader.LOADER, "enabled", True)
    unsubscribe = app.model_loader.LOADER.subscribe(listener)
    yield seen
    unsubscribe()


def use(monkeypatch, ref, *, warm=True):
    cfg = app.CONFIG
    monkeypatch.setattr(app, "CONFIG", dataclasses.replace(
        cfg, chat=ChatConfig(default_model_ref=ref), llm=dataclasses.replace(cfg.llm, warm_up_on_start=warm),
    ))


CLASSIFIER = model_for(LOCAL_PROVIDER, "classifier", app.CONFIG.models)


@pytest.mark.asyncio
async def test_a_llamacpp_default_is_started_with_the_persona_and_tools_then_the_helpers(monkeypatch, calls):
    use(monkeypatch, "local:llamacpp/big")
    monkeypatch.setattr(app, "_system_message", lambda waifu: "PERSONA")
    await app._warm_default_chat_model()
    # not the 9B: only the small helpers that run before every reply (classifier, embeddings)
    assert calls["helpers"] == [CLASSIFIER] and calls["embed"] == ["warm-up"]
    assert calls["load"] == [] and calls["stopped"] == []
    [(ref, messages, tools)] = calls["warm"]
    assert ref == "local:llamacpp/big"
    assert messages[0] == {"role": "system", "content": "PERSONA"}   # the same first message a turn sends
    assert tools == app.tools.offered_schemas(already_looked=False)  # same tool list, so the prefix matches
    # every window saw it load, then become ready (the "waking up" card, K1-10)
    assert calls["status"] == [("loading", "local:llamacpp/big"), ("ready", "local:llamacpp/big")]


@pytest.mark.parametrize(("ref", "loaded", "stopped", "states"), [
    # no selection: the configured local chat model, as an explicit Ollama ref
    (None, [model_for(LOCAL_PROVIDER, "chat", app.CONFIG.models)], [True], ["loading", "ready"]),
    # an Ollama pick stops llama-server first: one large local model at a time (FR-M-6)
    ("local:ollama/qwen3.5:4b", ["qwen3.5:4b"], [True], ["loading", "ready"]),
    # nothing to load for an API model: ready at once, no "waking up"
    ("api:airouter/some-model", [], [], ["ready"]),
])
@pytest.mark.asyncio
async def test_other_defaults(monkeypatch, calls, ref, loaded, stopped, states):
    use(monkeypatch, ref)
    await app._warm_default_chat_model()
    assert calls["load"] == loaded and calls["warm"] == [] and calls["stopped"] == stopped
    if loaded:
        assert calls["order"] == ["stop", "load"]          # llama-server gone before Ollama loads (FR-M-6)
    assert [s for s, _ in calls["status"]] == states


@pytest.mark.asyncio
async def test_boot_loads_the_model_the_last_thread_used(monkeypatch, calls):
    # FR-M-5: the last pick, not always the configured default (the 35B is slow)
    use(monkeypatch, "local:llamacpp/big")
    manager = app._conversations()
    await manager.new_thread(waifu_id=None, model_ref="local:ollama/qwen3.5:9b")
    await app._warm_default_chat_model()
    assert calls["load"] == ["qwen3.5:9b"] and calls["warm"] == []


@pytest.mark.asyncio
async def test_switched_off_or_failing_warm_ups_never_raise(monkeypatch, calls):
    use(monkeypatch, "local:llamacpp/big", warm=False)
    await app._warm_default_chat_model()
    assert calls["warm"] == calls["load"] == calls["status"] == []

    use(monkeypatch, "local:vllm/x")                     # invalid ref: logged, skipped
    await app._warm_default_chat_model()
    assert calls["status"] == []

    class Broken:
        async def warm(self, *a):
            raise RuntimeError("model file missing")

    use(monkeypatch, "local:llamacpp/big")
    monkeypatch.setattr(app.router, "get_router", lambda: Broken())
    await app._warm_default_chat_model()                 # shown in the window, with Try again
    assert calls["status"][-1] == ("failed", "local:llamacpp/big")
    assert app.model_loader.LOADER.status()["message"] == "model file missing"


@pytest.mark.asyncio
async def test_router_warm_is_a_one_token_chat_call(monkeypatch):
    seen = []

    async def complete(request):
        seen.append(request)
        yield ModelChunk(kind="content", text="x")

    rt = router.Router()
    monkeypatch.setattr(rt, "complete", complete)
    await rt.warm("local:llamacpp/big", [{"role": "system", "content": "p"}], [{"type": "function"}])
    [req] = seen
    assert (req.role, req.model_ref, req.max_tokens, req.stream) == ("chat", "local:llamacpp/big", 1, True)
    assert req.tools == ({"type": "function"},)


@pytest.mark.asyncio
async def test_tray_quit_stops_the_model_server_before_exiting(monkeypatch):
    stopped, exits = [], []

    class Rt:
        async def shutdown(self):
            stopped.append(True)

    monkeypatch.setattr(app.router, "get_router", lambda: Rt())
    monkeypatch.setattr(app, "_shutdown_event", asyncio.Event())
    monkeypatch.setattr(app.os, "_exit", lambda code: exits.append(code))
    assert (await app.shutdown_endpoint())["status"] == "shutting down"
    assert stopped == [True]                      # before os._exit, which skips the lifespan teardown
    await asyncio.sleep(0.2)
    assert exits == [0]
