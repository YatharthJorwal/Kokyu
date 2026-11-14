"""K1-00c: model references, effort, the `chat` role and the D-025 egress rules (FR-M-1, FR-M-8, FR-R-4, FR-R-5, FR-R-7)."""
from __future__ import annotations

import asyncio
import dataclasses

import pytest
from fastapi.testclient import TestClient

import app
import config
import llm
import protocol
import waifus
from router import decision as d
from router import model_ref
from router.errors import ProviderError, RouteBlockedError
from router.providers import OllamaNativeProvider
from router.providers.airouter import AirouterProvider
from router.types import ModelRequest, SECRET, UNTRUSTED
from waifu_fixtures import make_pack
from waifus import WaifuRegistry

from test_decision import BUDGET, MODELS, PROVIDERS, state
from test_router import drain, make_router

CHAT = config.CONFIG.roles["chat"]
API = "api:airouter/deepseek/deepseek-v4-flash"
LOCAL = "local:ollama/qwen3.5:4b"


# -- model references --------------------------------------------------------


def test_a_reference_splits_on_the_first_slash_only():
    ref = model_ref.parse("local:ollama/hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L")
    assert (ref.kind, ref.backend, ref.model) == ("local", "ollama", "hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L")
    assert ref.provider == "local_ollama" and ref.is_local
    assert str(model_ref.parse(API)) == API and model_ref.parse(API).provider == "airouter"


@pytest.mark.parametrize("bad", ["", "qwen3.5:9b", "cloud:airouter/x", "local:ollama", "local:ollama/ ", "local:vllm/x", "api:openrouter/x"])
def test_bad_or_unsupported_references_are_rejected(bad):
    with pytest.raises(model_ref.ModelRefError):
        model_ref.parse(bad)


def test_effort_maps_to_each_backend():
    assert model_ref.check_effort(None) is None and model_ref.check_effort("high") == "high"
    with pytest.raises(model_ref.ModelRefError):
        model_ref.check_effort("max")
    assert [model_ref.ollama_think(e) for e in (None, "off", "low", "high")] == [None, False, True, True]
    assert [model_ref.openai_reasoning_effort(e) for e in (None, "off", "medium")] == [None, None, "medium"]


# -- decide_chat: one test per rule --------------------------------------------


def chat(request=None, st=None, role_cfg=CHAT, budget=BUDGET, now=1000.0):
    return d.decide(
        role="chat", role_cfg=role_cfg, request=request or ModelRequest(role="chat"),
        routing=config.CONFIG.routing, budget=budget, state=st or state(),
        models=MODELS, providers=PROVIDERS, now=now,
    )


def test_chat_is_cloud_eligible_in_the_default_config():
    assert CHAT.local_only is False


def test_no_selection_is_the_local_default():
    r = chat()
    assert r.reason == d.LOCAL_DEFAULT and r.chosen.startswith("local_ollama:") and not r.blocked


def test_a_local_selection_runs_that_model_even_with_ambient_or_secret_content():
    for req in (
        ModelRequest(role="chat", model_ref=LOCAL),
        ModelRequest(role="chat", model_ref=LOCAL, ambient=True, privacy_class=SECRET),
    ):
        r = chat(req)
        assert (r.reason, r.chosen, r.blocked) == (d.USER_SELECTED, "local_ollama:qwen3.5:4b", False)


def test_an_api_selection_runs_that_model_and_nothing_else():
    r = chat(ModelRequest(role="chat", model_ref=API))
    assert r.reason == d.USER_SELECTED and r.chosen == "airouter:deepseek/deepseek-v4-flash"
    assert r.candidates == (r.chosen,) and not r.blocked          # no fallback chain


def test_user_attached_files_may_go_to_the_chosen_api_model():
    r = chat(ModelRequest(role="chat", model_ref=API, trust=UNTRUSTED))
    assert r.reason == d.USER_SELECTED and not r.blocked


@pytest.mark.parametrize(
    "request_kw, st_kw, reason",
    [
        ({"model_ref": "api:nowhere/x"}, {}, d.MODEL_UNSUPPORTED),
        ({"privacy_class": SECRET}, {}, d.PRIVACY_LOCAL_ONLY),
        ({"ambient": True}, {}, d.AMBIENT_CONTEXT),
        ({"ambient": True, "trust": UNTRUSTED}, {}, d.AMBIENT_CONTEXT),
        ({}, {"cloud_available": False}, d.CLOUD_DISABLED),
        ({}, {"offline_until": 2000.0}, d.OFFLINE),
        ({}, {"spend_hour_usd": 5.0}, d.BUDGET_EXHAUSTED),
    ],
)
def test_an_api_selection_that_may_not_run_is_blocked_never_rerouted(request_kw, st_kw, reason):
    req = ModelRequest(role="chat", **{"model_ref": API, **request_kw})
    r = chat(req, st=state(**st_kw))
    assert r.blocked and r.reason == reason
    assert not r.chosen.startswith("local_ollama:")               # never a silent local answer


def test_a_role_pinned_local_by_config_blocks_api_but_not_local():
    pinned = dataclasses.replace(CHAT, local_only=True)
    assert chat(ModelRequest(role="chat", model_ref=API), role_cfg=pinned).reason == d.ROLE_PINNED_LOCAL
    assert not chat(ModelRequest(role="chat", model_ref=LOCAL), role_cfg=pinned).blocked


def test_other_roles_are_untouched_by_a_model_ref():
    r = d.decide(
        role="reflex", role_cfg=config.CONFIG.roles["reflex"],
        request=ModelRequest(role="reflex", model_ref=API), routing=config.CONFIG.routing,
        budget=BUDGET, state=state(), models=MODELS, providers=PROVIDERS, now=1000.0,
    )
    assert r.reason == d.ROLE_PINNED_LOCAL


# -- the router executes or refuses, never falls back ---------------------------


@pytest.mark.asyncio
async def test_router_runs_the_chosen_api_model_in_shadow_mode_too(tmp_path):
    router, local, cloud = make_router(tmp_path, mode="shadow")
    await drain(router, ModelRequest(role="chat", messages=({"role": "user", "content": "hi"},), model_ref=API))
    assert [m for _, m in cloud.calls] == ["deepseek/deepseek-v4-flash"] and local.calls == []


@pytest.mark.asyncio
async def test_router_refuses_a_blocked_selection_without_calling_anyone(tmp_path):
    router, local, cloud = make_router(tmp_path, mode="enforce")
    request = ModelRequest(role="chat", messages=({"role": "user", "content": "hi"},), model_ref=API, ambient=True)
    with pytest.raises(RouteBlockedError) as info:
        await drain(router, request)
    assert info.value.reason == d.AMBIENT_CONTEXT and "never leave" in info.value.message
    assert local.calls == [] and cloud.calls == []


@pytest.mark.asyncio
async def test_a_failing_api_model_is_an_error_not_a_local_answer(tmp_path):
    router, local, cloud = make_router(tmp_path, mode="enforce", cloud_error=ProviderError("429"))
    with pytest.raises(ProviderError):
        await drain(router, ModelRequest(role="chat", messages=({"role": "user", "content": "hi"},), model_ref=API))
    assert local.calls == []


@pytest.mark.asyncio
async def test_ollama_gets_the_routed_model_always_and_effort_only_when_set(monkeypatch):
    seen = []

    async def fake_tools(messages, tools, **kwargs):
        seen.append(kwargs)
        yield {"type": "content", "text": "ok"}

    monkeypatch.setattr(llm, "stream_reply_with_tools", fake_tools)
    provider = OllamaNativeProvider()
    tools = ({"type": "function", "function": {"name": "t"}},)
    base = dict(role="chat", messages=({"role": "user", "content": "hi"},), tools=tools)
    [c async for c in provider.complete(ModelRequest(**base), model="qwen3.5:9b")]
    [c async for c in provider.complete(ModelRequest(**base, model_ref=LOCAL, effort="off"), model="qwen3.5:4b")]
    # the router's model is always passed (D-052): helper roles no longer fall back to llm.model
    assert seen == [{"model": "qwen3.5:9b"}, {"model": "qwen3.5:4b", "think": False}]


def test_the_api_payload_carries_reasoning_effort():
    provider = AirouterProvider(config.CONFIG.providers["airouter"], "test-key")
    with_effort = provider._payload(ModelRequest(role="chat", effort="high"), "m")
    without = provider._payload(ModelRequest(role="chat", effort="off"), "m")
    assert with_effort["reasoning_effort"] == "high" and "reasoning_effort" not in without


@pytest.mark.asyncio
async def test_llm_payload_uses_the_override_model_and_think(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        async def aiter_lines(self):
            yield '{"message": {"content": "hi"}, "done": true}'

    class FakeStream:
        async def __aenter__(self):
            return FakeResponse()

        async def __aexit__(self, *a):
            return False

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url, json=None, **k):
            captured.update(json)
            return FakeStream()

    monkeypatch.setattr(llm.httpx, "AsyncClient", FakeClient)
    out = [x async for x in llm._stream_ollama_native([{"role": "user", "content": "x"}], model="other:1b", think=True)]
    assert out == ["hi"] and captured["model"] == "other:1b" and captured["think"] is True


# -- over the WebSocket ---------------------------------------------------------


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha", ref_text="alpha transcript")
    monkeypatch.setattr(waifus.registry, "_registry", WaifuRegistry(premade, tmp_path / "user"))
    monkeypatch.setattr(app, "_conversation_manager", None)
    calls = []

    async def fake_stream(role, messages, tools, **kwargs):
        calls.append({"role": role, **kwargs})
        if kwargs.get("model_ref") == API:
            raise RouteBlockedError(d.CLOUD_DISABLED, "The API model isn't available.", API)
        yield {"type": "content", "text": "fine [happy]"}

    async def nothing(*_a, **_k):
        return None

    async def silent(text, voice=None):
        return b""

    class NoWriter:
        async def run_pass(self, *_a, **_k):
            return None

        def preempt(self):
            return None

    monkeypatch.setattr(app.router, "stream_with_tools", fake_stream)
    monkeypatch.setattr(app.tts, "synthesize", silent)
    monkeypatch.setattr(app.tts, "prewarm", nothing)
    monkeypatch.setattr(app.look_intent, "maybe_look", nothing)
    monkeypatch.setattr(app, "_log_transcript_turn_safely", nothing)
    monkeypatch.setattr(app.writer, "WRITER", NoWriter())
    monkeypatch.setattr(app, "_driver", None)
    monkeypatch.setattr(app, "_shutdown_event", asyncio.Event())
    return TestClient(app.app), calls


def _until(ws, kind):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == kind:
            return msg, seen


def test_model_and_effort_are_saved_on_the_thread_and_used_by_the_next_turn(kernel):
    client, calls = kernel
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"type": "set_temp_mode", "enabled": True})
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        updated, _ = _until(ws, "thread_updated")
        assert updated["data"]["thread"]["model_ref"] == LOCAL
        ws.send_json({"v": 1, "type": "set_effort", "data": {"effort": "low"}})
        updated, _ = _until(ws, "thread_updated")
        assert updated["data"]["thread"]["effort"] == "low"
        ws.send_json({"type": "user_text", "text": "hi"})
        _until(ws, "turn_end")
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": "gpt-whatever"}})
        err, _ = _until(ws, "error")
        assert err["data"]["code"] == "bad_message"
    assert calls[-1] == {"role": "chat", "model_ref": LOCAL, "effort": "low", "ambient": False}
    with client.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        thread = opened["data"]["thread"]
        assert (thread["model_ref"], thread["effort"]) == (LOCAL, "low")
        stored = [m for m in opened["data"]["messages"] if m["role"] == "assistant"]
        assert stored[0]["model_ref"] == LOCAL and stored[0]["effort"] == "low"


def test_a_blocked_api_model_shows_retry_and_switch_and_nothing_answers_instead(kernel):
    client, calls = kernel
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"type": "set_temp_mode", "enabled": True})
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": API}})
        _until(ws, "thread_updated")
        ws.send_json({"type": "user_text", "text": "hi"})
        err, seen = _until(ws, "error")
        _, rest = _until(ws, "turn_end")
    data = err["data"]
    assert data["code"] == "model_blocked" and data["reason"] == d.CLOUD_DISABLED
    assert data["actions"] == ["retry", "switch_model"] and data["model_ref"] == API
    tokens = [m for m in seen + rest if m["type"] == "token"]
    assert tokens == []                                        # no other model replied
    assert len(calls) == 1


def test_model_failure_frames_cover_blocked_and_provider_errors_only():
    assert protocol.model_failure(RouteBlockedError("OFFLINE", "x", API))["code"] == "model_blocked"
    assert protocol.model_failure(ProviderError("500"))["code"] == "model_failed"
    assert protocol.model_failure(llm.LLMUnreachableError("ollama down")) is None


# -- K1-10: the model picker over the WebSocket (FR-M-3..6, D-054) -------------


@pytest.fixture
def loads(kernel, monkeypatch):
    """The real loader, with a fake load and no pause before thread-open loads."""
    seen = []

    async def fake_load(ref):
        seen.append(ref)

    monkeypatch.setattr(app, "_load_chat_model", fake_load)
    monkeypatch.setattr(app, "CONFIG", dataclasses.replace(
        app.CONFIG, chat=dataclasses.replace(app.CONFIG.chat, default_model_ref="local:llamacpp/big", load_delay_s=0)
    ))
    monkeypatch.setattr(app.model_loader.LOADER, "enabled", True)
    return kernel[0], seen


def _status_until(ws, state, ref):
    while True:
        msg, _ = _until(ws, "model_status")
        if (msg["data"]["state"], msg["data"]["model_ref"]) == (state, ref):
            return msg["data"]


def test_a_window_sees_the_model_load_and_a_pick_loads_the_new_model(loads):
    client, seen = loads
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        first, _ = _until(ws, "model_status")                     # the current state, right away
        assert first["data"]["state"] in ("idle", "loading", "ready")
        _status_until(ws, "ready", "local:llamacpp/big")          # the thread's (default) model woke up
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        _until(ws, "thread_updated")
        loading = _status_until(ws, "loading", LOCAL)
        assert loading["label"] == "qwen3.5:4b"
        _status_until(ws, "ready", LOCAL)
        ws.send_json({"v": 1, "type": "model_load", "data": {}})  # Try again: loads even though it is up
        _status_until(ws, "ready", LOCAL)
    assert seen == ["local:llamacpp/big", LOCAL, LOCAL]


def test_a_new_thread_keeps_the_pick_and_does_not_load_again(loads):
    client, seen = loads
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _status_until(ws, "ready", "local:llamacpp/big")
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        _status_until(ws, "ready", LOCAL)
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        opened, _ = _until(ws, "thread_opened")
        assert opened["data"]["thread"]["model_ref"] == LOCAL       # FR-M-5: inherits the last selection
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
    assert seen == ["local:llamacpp/big", LOCAL]


def test_the_model_list_reaches_the_window(kernel, monkeypatch):
    client, _ = kernel

    async def no_ollama(base_url, **_kw):
        return [], "Ollama is not running"

    class Rt:
        api_key_present = False
        catalog = None
        ledger = None
        state = None                      # what the connect-time settings message reads
        use_api_model_override = None

    monkeypatch.setattr(app.model_listing, "ollama_rows", no_ollama)
    monkeypatch.setattr(app.router, "get_router", lambda: Rt())
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "model_list", "data": {"refresh": True}})
        listed, _ = _until(ws, "model_list")
    data = listed["data"]
    assert data["local_error"] == "Ollama is not running" and data["api"] == [] and data["api_key"] is False
    assert data["default_ref"] == app.model_listing.default_ref(app.CONFIG)


def test_switching_models_waits_for_the_reply(kernel, monkeypatch):
    client, _ = kernel

    async def slow_stream(role, messages, tools, **kwargs):
        await asyncio.sleep(0.4)
        yield {"type": "content", "text": "done [happy]"}

    monkeypatch.setattr(app.router, "stream_with_tools", slow_stream)
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"type": "set_temp_mode", "enabled": True})
        ws.send_json({"type": "user_text", "text": "hi"})
        _until(ws, "turn_start")
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        err, _ = _until(ws, "error")
        assert err["data"]["code"] == "turn_running"
        _until(ws, "turn_end")
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        updated, _ = _until(ws, "thread_updated")
        assert updated["data"]["thread"]["model_ref"] == LOCAL


def test_only_the_main_window_loads_models(loads, monkeypatch):
    # Review finding: a second window opening an Ollama thread used to stop
    # llama-server under the main window's streaming reply. Observers only watch.
    client, seen = loads
    manager = app._conversations()
    other = manager.store.create_thread(model_ref=LOCAL)
    manager.store.create_thread(model_ref=None)                             # newest: the one that opens
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _status_until(ws, "ready", "local:llamacpp/big")
        # shortcut: demote this window instead of opening a second one (each TestClient
        # socket gets its own event loop, which the kernel's shared objects reject)
        monkeypatch.setattr(app, "_driver", object())
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": other.id}})
        opened, _ = _until(ws, "thread_opened")
        assert opened["data"]["thread"]["model_ref"] == LOCAL
        ws.send_json({"v": 1, "type": "model_load", "data": {}})
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
    assert seen == ["local:llamacpp/big"]


def test_hello_tells_the_window_the_defaults(kernel):
    client, _ = kernel
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"v": 1, "type": "hello", "id": "h1", "data": {"client": "main", "protocol": 1}})
        hello, _ = _until(ws, "hello")
    assert hello["data"]["default_model_ref"] == app.model_listing.default_ref(app.CONFIG)
    assert hello["data"]["default_effort"] == app.CONFIG.chat.default_effort


def test_a_turn_waits_for_its_model_and_warm_up_off_loads_on_the_first_message(loads, monkeypatch):
    # Review findings: a message sent before the delayed load started reached
    # Ollama while llama-server still held the memory; and warm_up_on_start: false
    # still loaded the model as soon as the window opened.
    client, seen = loads
    monkeypatch.setattr(app, "CONFIG", dataclasses.replace(
        app.CONFIG,
        llm=dataclasses.replace(app.CONFIG.llm, warm_up_on_start=False),
        chat=dataclasses.replace(app.CONFIG.chat, load_delay_s=30),          # a load that would start much later
    ))
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"type": "set_temp_mode", "enabled": True})
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
        assert seen == []                                                   # opening did not load
        ws.send_json({"type": "user_text", "text": "hi"})
        _status_until(ws, "ready", "local:llamacpp/big")                   # the message loaded it, at once
        _until(ws, "turn_done")
    assert seen == ["local:llamacpp/big"]
