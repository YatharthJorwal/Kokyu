"""K1-01b (D-052): at boot the kernel loads the model a new thread will use."""
from __future__ import annotations

import dataclasses

import pytest

import app
import router
from config import ChatConfig
from router.decision import LOCAL_PROVIDER, model_for
from router.types import ModelChunk


@pytest.fixture
def calls(monkeypatch):
    seen: dict[str, list] = {"ollama": [], "warm": [], "embed": []}

    async def ollama_warm(model=None):
        seen["ollama"].append(model)

    class FakeRouter:
        async def warm(self, ref, messages, tools):
            seen["warm"].append((ref, messages, tools))

    async def embed(text):
        seen["embed"].append(text)
        return [0.0]

    monkeypatch.setattr(app.llm, "warm_up_model", ollama_warm)
    monkeypatch.setattr(app.embeddings, "embed", embed)
    monkeypatch.setattr(app.router, "get_router", lambda: FakeRouter())
    return seen


def use(monkeypatch, ref, *, warm=True):
    cfg = app.CONFIG
    monkeypatch.setattr(app, "CONFIG", dataclasses.replace(
        cfg, chat=ChatConfig(default_model_ref=ref), llm=dataclasses.replace(cfg.llm, warm_up_on_start=warm),
    ))


@pytest.mark.asyncio
async def test_a_llamacpp_default_is_started_with_the_persona_and_tools_then_the_helpers(monkeypatch, calls):
    use(monkeypatch, "local:llamacpp/big")
    monkeypatch.setattr(app, "_system_message", lambda waifu: "PERSONA")
    await app._warm_default_chat_model()
    # not the 9B: only the small helpers that run before every reply (classifier, embeddings)
    assert calls["ollama"] == [model_for(LOCAL_PROVIDER, "classifier", app.CONFIG.models)] and calls["embed"] == ["warm-up"]
    [(ref, messages, tools)] = calls["warm"]
    assert ref == "local:llamacpp/big"
    assert messages[0] == {"role": "system", "content": "PERSONA"}   # the same first message a turn sends
    assert tools == app.tools.offered_schemas(already_looked=False)  # same tool list, so the prefix matches


@pytest.mark.parametrize(("ref", "ollama", "warmed"), [
    (None, [None], []),                                  # no selection: the configured Ollama model, as before
    ("local:ollama/qwen3.5:4b", ["qwen3.5:4b"], []),      # the chosen Ollama model, not llm.model
    ("api:airouter/some-model", [], []),                 # nothing to load for an API model
])
@pytest.mark.asyncio
async def test_other_defaults(monkeypatch, calls, ref, ollama, warmed):
    use(monkeypatch, ref)
    await app._warm_default_chat_model()
    assert calls["ollama"] == ollama and calls["warm"] == warmed


@pytest.mark.asyncio
async def test_switched_off_or_failing_warm_ups_never_raise(monkeypatch, calls):
    use(monkeypatch, "local:llamacpp/big", warm=False)
    await app._warm_default_chat_model()
    assert calls == {"ollama": [], "warm": [], "embed": []}

    use(monkeypatch, "local:vllm/x")                     # invalid ref: logged, skipped
    await app._warm_default_chat_model()

    class Broken:
        async def warm(self, *a):
            raise RuntimeError("model file missing")

    use(monkeypatch, "local:llamacpp/big")
    monkeypatch.setattr(app.router, "get_router", lambda: Broken())
    await app._warm_default_chat_model()                 # the first message will show the error with Retry


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
    monkeypatch.setattr(app, "_shutdown_event", __import__("asyncio").Event())
    monkeypatch.setattr(app.os, "_exit", lambda code: exits.append(code))
    assert (await app.shutdown_endpoint())["status"] == "shutting down"
    assert stopped == [True]                      # before os._exit, which skips the lifespan teardown
    await __import__("asyncio").sleep(0.2)
    assert exits == [0]
