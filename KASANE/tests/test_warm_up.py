"""K1-01b (D-052), K1-10 (D-054): at boot the kernel loads the model the first
message will use, through the model loader, so windows can show it waking up."""
from __future__ import annotations

import asyncio
import dataclasses
import os

import pytest

import app
import boot
import companions
import conversation
import hub
import llm
import model_loader
import prompting
import router
import session
import tools
import waifus
from config import CONFIG, ChatConfig
from kernel_fixtures import set_config
from memory import embeddings, writer
from router.decision import LOCAL_PROVIDER, model_for
from router.types import ModelChunk
from waifu_fixtures import make_pack
from waifus import WaifuRegistry


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
    monkeypatch.setattr(conversation, "_manager", None)
    monkeypatch.setattr(llm, "warm_up_model", helper_warm)
    monkeypatch.setattr(llm, "load_model", load)
    monkeypatch.setattr(embeddings, "embed", embed)
    monkeypatch.setattr(router, "get_router", lambda: FakeRouter())
    monkeypatch.setattr(model_loader.LOADER, "enabled", True)
    unsubscribe = model_loader.LOADER.subscribe(listener)
    yield seen
    unsubscribe()


def use(monkeypatch, ref, *, warm=True):
    cfg = CONFIG
    set_config(monkeypatch, dataclasses.replace(
        cfg, chat=ChatConfig(default_model_ref=ref), llm=dataclasses.replace(cfg.llm, warm_up_on_start=warm),
    ))


@pytest.mark.asyncio
async def test_boot_never_starts_a_llamacpp_model(monkeypatch, calls):
    # D-060: a 21 GB file and every CPU core; it starts when the user picks it
    use(monkeypatch, "local:llamacpp/big")
    await boot.warm_default_chat_model()
    assert calls["warm"] == calls["load"] == calls["helpers"] == calls["status"] == []
    assert not boot.loads_without_asking("local:llamacpp/big")
    assert boot.loads_without_asking("local:ollama/qwen3.5:9b") and boot.loads_without_asking("api:airouter/x")


@pytest.mark.asyncio
async def test_a_picked_llamacpp_model_is_started_with_the_persona_and_tools_then_the_helpers(monkeypatch, calls):
    use(monkeypatch, "local:llamacpp/big")
    monkeypatch.setattr(
        companions, "system_message", lambda waifu, *, mode, scenario: f"PERSONA {mode} {scenario}"
    )
    await model_loader.LOADER.request("local:llamacpp/big")   # what a pick in the chip does
    # only the embedding model, which recall uses on every message (D-072: no classifier warm)
    assert calls["helpers"] == [] and calls["embed"] == ["warm-up"]
    assert llm.ACTIVE_MODEL == ""   # helper roles use their own config while llama-server serves
    assert calls["load"] == [] and calls["stopped"] == []
    [(ref, messages, offered)] = calls["warm"]
    assert ref == "local:llamacpp/big"
    # the same first message a turn sends: no thread yet, so a chat one (FR-MODE-2)
    assert messages[0] == {"role": "system", "content": "PERSONA chat None"}
    assert offered == tools.offered_schemas(already_looked=False)  # same tool list, so the prefix matches
    # every window saw it load, then become ready (the "waking up" card, K1-10)
    assert calls["status"] == [("loading", "local:llamacpp/big"), ("ready", "local:llamacpp/big")]


@pytest.mark.parametrize("mode", ["chat", "roleplay"])
@pytest.mark.asyncio
async def test_the_warm_up_reads_the_first_message_and_tools_of_the_last_threads_mode(monkeypatch, calls, tmp_path, mode):
    """FR-MODE-2, D-052: llama-server caches the prefix of the first turn, which runs in
    the last thread; a roleplay one has its own layer and card and offers no tools."""
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha", ref_text="alpha transcript")
    registry = WaifuRegistry(premade, tmp_path / "user")
    monkeypatch.setattr(waifus.registry, "_registry", registry)
    use(monkeypatch, "local:llamacpp/big")
    card = {"title": "Rain", "opening": "*She waves.* Over here!"} if mode == "roleplay" else None
    thread = await conversation.get_manager().new_thread(waifu_id="alpha", mode=mode, scenario=card)
    await model_loader.LOADER.request("local:llamacpp/big")
    [(_ref, messages, offered)] = calls["warm"]
    # exactly what the window's history[0] will be in that thread (Session.system_prompt)
    expected = companions.system_message(registry.get("alpha"), **conversation.prompt_layers(thread))
    assert messages[0] == {"role": "system", "content": expected}
    if mode == "roleplay":
        assert prompting.ROLEPLAY_LAYER in expected and "Title: Rain" in expected
        assert prompting.TOOL_GUIDANCE not in expected and offered == []
    else:
        assert prompting.CHAT_LAYER in expected and offered == tools.offered_schemas(already_looked=False)


@pytest.mark.parametrize(("ref", "loaded", "stopped", "states"), [
    # no selection: the configured local chat model, as an explicit Ollama ref
    (None, [model_for(LOCAL_PROVIDER, "chat", CONFIG.models)], [True], ["loading", "ready"]),
    # an Ollama pick stops llama-server first: one large local model at a time (FR-M-6)
    ("local:ollama/qwen3.5:4b", ["qwen3.5:4b"], [True], ["loading", "ready"]),
    # nothing to load for an API model: ready at once, no "waking up"; llama-server makes room (D-072)
    ("api:airouter/some-model", [], [True], ["ready"]),
])
@pytest.mark.asyncio
async def test_other_defaults(monkeypatch, calls, ref, loaded, stopped, states):
    use(monkeypatch, ref)
    await boot.warm_default_chat_model()
    assert calls["load"] == loaded and calls["warm"] == [] and calls["stopped"] == stopped
    if loaded:
        assert calls["order"] == ["stop", "load"]          # llama-server gone before Ollama loads (FR-M-6)
    assert [s for s, _ in calls["status"]] == states


@pytest.mark.asyncio
async def test_boot_loads_the_model_the_last_thread_used(monkeypatch, calls):
    # FR-M-5: the last pick, not always the configured default (the 35B is slow)
    use(monkeypatch, "local:llamacpp/big")
    manager = conversation.get_manager()
    await manager.new_thread(waifu_id=None, model_ref="local:ollama/qwen3.5:9b")
    await boot.warm_default_chat_model()
    assert calls["load"] == ["qwen3.5:9b"] and calls["warm"] == []


@pytest.mark.asyncio
async def test_switched_off_or_failing_warm_ups_never_raise(monkeypatch, calls):
    use(monkeypatch, "local:llamacpp/big", warm=False)
    await boot.warm_default_chat_model()
    assert calls["warm"] == calls["load"] == calls["status"] == []

    use(monkeypatch, "local:vllm/x")                     # invalid ref: logged, skipped
    await boot.warm_default_chat_model()
    assert calls["status"] == []

    async def broken_load(model=None):
        raise RuntimeError("model file missing")

    use(monkeypatch, "local:ollama/qwen3.5:9b")
    monkeypatch.setattr(llm, "load_model", broken_load)
    await boot.warm_default_chat_model()                 # shown in the window, with Try again
    assert calls["status"][-1] == ("failed", "local:ollama/qwen3.5:9b")
    assert model_loader.LOADER.status()["message"] == "model file missing"


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

    monkeypatch.setattr(router, "get_router", lambda: Rt())
    monkeypatch.setattr(hub, "shutdown_event", asyncio.Event())
    monkeypatch.setattr(os, "_exit", lambda code: exits.append(code))
    assert (await app.shutdown_endpoint())["status"] == "shutting down"
    assert stopped == [True]                      # before os._exit, which skips the lifespan teardown
    await asyncio.sleep(0.2)
    assert exits == [0]


@pytest.mark.asyncio
async def test_tray_quit_waits_for_a_closing_windows_memory_pass(monkeypatch):
    # The window has left (it no longer drives or hears news) but its memory pass is
    # still running: quitting must not cut it off.
    order = []

    class Rt:
        async def shutdown(self):
            order.append("router stopped")

    class SlowWriter:
        async def run_pass(self, reason):
            await asyncio.sleep(0.3)
            order.append("memory pass done")

    class Ws:
        async def close(self):
            pass

    monkeypatch.setattr(router, "get_router", lambda: Rt())
    monkeypatch.setattr(writer, "WRITER", SlowWriter())
    monkeypatch.setattr(hub, "shutdown_event", asyncio.Event())
    monkeypatch.setattr(hub, "connections", set())
    monkeypatch.setattr(hub, "closing", set())
    monkeypatch.setattr(hub, "driver", None)
    monkeypatch.setattr(os, "_exit", lambda code: order.append("exit"))
    closing = asyncio.create_task(session.Session(Ws())._close())
    await asyncio.sleep(0)   # the window has left; its memory pass is running
    await app.shutdown_endpoint()
    await closing
    await asyncio.sleep(0.2)
    assert order == ["memory pass done", "router stopped", "exit"]


# -- one chat model in memory (D-072) ------------------------------------------------


@pytest.mark.asyncio
async def test_an_ollama_pick_unloads_every_other_model_but_embeddings(monkeypatch, calls):
    kept = []

    async def unload(base_url, keep=frozenset(), transport=None):
        kept.append(keep)
        return ["qwen3.5:9b"]

    monkeypatch.setattr(boot, "unload_ollama", unload)
    embed = CONFIG.memory.embedding.model.removesuffix(":latest")
    await boot.load_chat_model("local:ollama/qwen3.5:4b")
    assert kept == [frozenset({"qwen3.5:4b", embed})] and calls["load"] == ["qwen3.5:4b"]
    assert llm.ACTIVE_MODEL == "qwen3.5:4b"
    kept.clear()
    await boot.load_chat_model("api:airouter/x")             # an API pick frees the local ones too
    assert kept == [frozenset({embed})] and llm.ACTIVE_MODEL == ""
