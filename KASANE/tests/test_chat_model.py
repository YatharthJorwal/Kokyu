"""K1-00c: model references, effort, the `chat` role and the D-025 egress rules (FR-M-1, FR-M-8, FR-R-4, FR-R-5, FR-R-7)."""
from __future__ import annotations

import asyncio
import dataclasses
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app
import boot
import config
import conversation
import hub
import llm
import model_loader
import protocol
import router
import turns
import waifus
from audio import tts
from config import CONFIG
from kernel_fixtures import set_config
from memory import writer
from router import listing as model_listing
from router import decision as d
from router import model_ref
from router.errors import ProviderError, RouteBlockedError
from router.providers import OllamaNativeProvider
from router.providers.airouter import AirouterProvider
from router.types import SECRET, UNTRUSTED, ModelRequest, Usage
from senses import look_intent
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


@pytest.mark.parametrize("bad", ["", "qwen3.5:9b", "cloud:airouter/x", "local:ollama", "local:ollama/ ", "local:vllm/x", "api:Open-Router/x", "api:/x"])
def test_bad_or_unsupported_references_are_rejected(bad):
    with pytest.raises(model_ref.ModelRefError):
        model_ref.parse(bad)


def test_effort_maps_to_each_backend():
    assert model_ref.check_effort(None) is None and model_ref.check_effort("max") == "max"
    with pytest.raises(model_ref.ModelRefError):
        model_ref.check_effort("extreme")
    # API: the provider's reasoning_effort for low, medium and high only (FR-M-10)
    assert [model_ref.openai_reasoning_effort(e) for e in (None, "off", "medium", "max")] == [None, None, "medium", None]


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
        ({"model_ref": "api:Bad-Id/x"}, {}, d.MODEL_UNSUPPORTED),
        ({"model_ref": "api:openrouter/x"}, {}, d.OTHER_PROVIDER),   # D-059: not the active endpoint
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
    [c async for c in provider.complete(ModelRequest(**base, model_ref=LOCAL, effort="high"), model="qwen3.5:4b")]
    # the router's model is always passed (D-052): helper roles no longer fall back to llm.model
    assert seen[:2] == [{"model": "qwen3.5:9b"}, {"model": "qwen3.5:4b", "think": False}]
    # thinking counts against num_predict: it gets room on top of the reply cap (D-064)
    room = llm.CONFIG.llm.max_tokens + llm.CONFIG.llm.reasoning_tokens
    assert seen[2] == {"model": "qwen3.5:4b", "think": True, "num_predict": room}


@pytest.mark.asyncio
async def test_ollama_gets_the_callers_reply_cap(monkeypatch):
    """FR-MODE-5: a story fold asks for more than llm.max_tokens; the local call must
    send it as num_predict (with the thinking room on top when thinking)."""
    seen = []

    async def fake_reply(messages, **kwargs):
        seen.append(kwargs)
        yield "ok"

    monkeypatch.setattr(llm, "stream_reply", fake_reply)
    provider = OllamaNativeProvider()
    base = dict(role="memory_writer", messages=({"role": "user", "content": "hi"},), max_tokens=928)
    [c async for c in provider.complete(ModelRequest(**base, model_ref=LOCAL, effort="off"), model="qwen3.5:4b")]
    [c async for c in provider.complete(ModelRequest(**base, model_ref=LOCAL, effort="high"), model="qwen3.5:4b")]
    assert seen[0] == {"model": "qwen3.5:4b", "think": False, "num_predict": 928}
    assert seen[1]["num_predict"] == 928 + llm.CONFIG.llm.reasoning_tokens


@pytest.mark.asyncio
async def test_ollamas_token_counts_reach_the_router_as_usage(monkeypatch):
    # FR-C-10: Ollama reports the counts on its last chunk; the stored reply records them.
    async def fake_tools(messages, tools, **kwargs):
        yield {"type": "content", "text": "ok"}
        yield {"type": "usage", "prompt_tokens": 300, "completion_tokens": 4}

    monkeypatch.setattr(llm, "stream_reply_with_tools", fake_tools)
    request = ModelRequest(role="chat", messages=({"role": "user", "content": "hi"},), tools=({"type": "function"},))
    chunks = [c async for c in OllamaNativeProvider().complete(request, model="qwen3.5:9b")]
    assert [(c.kind, c.usage) for c in chunks if c.kind == "usage"] == [("usage", Usage(300, 4))]


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
    assert captured["options"]["num_predict"] == llm.CONFIG.llm.max_tokens
    [x async for x in llm._stream_ollama_native([{"role": "user", "content": "x"}], num_predict=4608)]
    assert captured["options"]["num_predict"] == 4608 and captured["options"]["num_ctx"] == llm.CONFIG.llm.num_ctx


# -- over the WebSocket ---------------------------------------------------------


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha", ref_text="alpha transcript")
    monkeypatch.setattr(waifus.registry, "_registry", WaifuRegistry(premade, tmp_path / "user"))
    monkeypatch.setattr(conversation, "_manager", None)
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

    monkeypatch.setattr(router, "stream_with_tools", fake_stream)
    monkeypatch.setattr(tts, "synthesize", silent)
    monkeypatch.setattr(tts, "prewarm", nothing)
    monkeypatch.setattr(look_intent, "maybe_look", nothing)
    monkeypatch.setattr(turns, "log_transcript_turn", nothing)
    monkeypatch.setattr(writer, "WRITER", NoWriter())
    monkeypatch.setattr(hub, "driver", None)
    monkeypatch.setattr(hub, "shutdown_event", asyncio.Event())
    return TestClient(app.app), calls


def _until(ws, kind):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == kind:
            return msg, seen


def _temp_on(ws):
    """Temp Chat on (keeps memory out of the test); the kernel confirms it."""
    ws.send_json({"v": 1, "type": "set_temp", "data": {"on": True}})
    return _until(ws, "thread_updated")


def test_model_and_effort_are_saved_on_the_thread_and_used_by_the_next_turn(kernel):
    client, calls = kernel
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        updated, _ = _until(ws, "thread_updated")
        assert updated["data"]["thread"]["model_ref"] == LOCAL
        ws.send_json({"v": 1, "type": "set_effort", "data": {"effort": "low"}})
        updated, _ = _until(ws, "thread_updated")
        assert updated["data"]["thread"]["effort"] == "low"
        ws.send_json({"v": 1, "type": "send", "data": {"text": "hi"}})
        _until(ws, "turn_done")
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


def test_effort_is_remembered_per_model_in_the_thread(kernel):
    # FR-M-11: back on a model, its effort comes back; a model used for the first time starts at its default
    client, _ = kernel
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)

        def pick(ref):
            ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": ref}})
            thread = _until(ws, "thread_updated")[0]["data"]["thread"]
            return thread["model_ref"], thread["effort"]

        def effort(level):
            ws.send_json({"v": 1, "type": "set_effort", "data": {"effort": level}})
            _until(ws, "thread_updated")

        assert pick(LOCAL) == (LOCAL, None)
        effort("off")
        assert pick(API) == (API, None)
        effort("high")
        assert pick(LOCAL) == (LOCAL, "off")
        assert pick(API) == (API, "high")
    store = conversation.get_manager().store   # stored with the thread, so it survives a restart
    [thread] = [t for t in store.list_threads() if t.model_ref == API]
    assert thread.efforts == {LOCAL: "off", API: "high"} and thread.effort == "high"


def test_a_blocked_api_model_shows_retry_and_switch_and_nothing_answers_instead(kernel):
    client, calls = kernel
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": API}})
        _until(ws, "thread_updated")
        ws.send_json({"v": 1, "type": "send", "data": {"text": "hi"}})
        err, seen = _until(ws, "error")
        _, rest = _until(ws, "turn_done")
    data = err["data"]
    assert data["code"] == "model_blocked" and data["reason"] == d.CLOUD_DISABLED
    assert data["actions"] == ["retry", "switch_model"] and data["model_ref"] == API
    tokens = [m for m in seen + rest if m["type"] == "token"]
    assert tokens == []                                        # no other model replied
    assert len(calls) == 1


def test_an_api_model_is_never_offered_the_screen_or_camera_tools(kernel, monkeypatch):
    # FR-R-7 (audit finding): an API model could call capture_screen and be sent
    # the description of the user's screen
    client, _ = kernel
    offered = []

    async def recording(role, messages, tools, **kwargs):
        offered.append({t["function"]["name"] for t in tools})
        yield {"type": "content", "text": "ok [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", recording)
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        for ref in (LOCAL, API):
            ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": ref}})
            _until(ws, "thread_updated")
            ws.send_json({"v": 1, "type": "send", "data": {"text": "hi"}})
            _until(ws, "turn_done")
    local_only = {"capture_screen", "capture_camera", "read_clipboard"}
    assert local_only <= offered[0] and not local_only & offered[1]


def test_an_attachment_sent_to_an_api_model_is_badged_and_an_empty_one_refused(kernel, monkeypatch):
    # FR-R-7: an attached file may go to the chosen API model, with a badge on that
    # message, kept when the thread reopens and when Regenerate runs it again.
    # An empty upload ends the turn the client already started (review findings).
    client, _ = kernel

    async def answering(role, messages, tools, **kwargs):
        yield {"type": "content", "text": "nice [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", answering)
    upload = {"filename": "notes.txt", "kind": "text", "content": "milk, eggs"}
    with client.websocket_connect("/ws") as ws:
        opened, _ = _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "send_file", "data": {**upload, "content": ""}})
        refused, _ = _until(ws, "error")
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        _until(ws, "thread_updated")
        ws.send_json({"v": 1, "type": "send_file", "data": upload})
        local, _ = _until(ws, "turn_start")
        _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": API}})
        _until(ws, "thread_updated")
        ws.send_json({"v": 1, "type": "send_file", "data": upload})
        sent, _ = _until(ws, "turn_start")
        _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "regenerate", "data": {}})
        again, _ = _until(ws, "turn_start")
        _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": opened["data"]["thread"]["id"]}})
        reopened, _ = _until(ws, "thread_opened")
    assert refused["data"]["code"] == "bad_message"
    assert local["data"]["sent_to"] is None and sent["data"]["sent_to"] == API and again["data"]["sent_to"] == API
    metas = [m["meta"] for m in reopened["data"]["messages"] if m["role"] == "user"]
    assert metas == [{"attachment": "text"}, {"attachment": "text", "sent_to": API}]


def test_an_image_the_vision_model_cannot_see_ends_the_turn_without_a_line(kernel, monkeypatch):
    # The window shows a turn from the moment it sends the file; the refusal has to close it.
    client, _ = kernel

    async def blind(*_a, **_k):
        raise llm.LLMUnreachableError("vision server down")

    monkeypatch.setattr(router, "describe_image", blind)
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "send_file", "data": {"filename": "cat.jpg", "kind": "image", "content": "abc"}})
        err, _ = _until(ws, "error")
        done, seen = _until(ws, "turn_done")
    assert err["data"]["code"] == "vision_unavailable"
    assert done["data"]["text"] == "" and "turn_start" not in [m["type"] for m in seen]


@pytest.mark.asyncio
async def test_screen_remarks_stay_out_of_an_api_models_context(tmp_path, monkeypatch):
    # FR-SC-3 (review finding): a Task Guide or OCR remark was written from a screen
    # capture; it stays in a local model's context and never reaches an API model
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha")
    waifu = WaifuRegistry(premade, tmp_path / "user").get("alpha")
    seen = []

    async def recording(role, messages, tools, **kwargs):
        seen.append(" ".join(m["content"] for m in messages))
        yield {"type": "content", "text": "ok [neutral]"}

    async def nothing(*_a, **_k):
        return None

    async def silent(text, voice=None):
        return b""

    class Socket:
        state = SimpleNamespace(waifu=waifu)

        async def send_json(self, payload):
            pass

    monkeypatch.setattr(router, "stream_with_tools", recording)
    monkeypatch.setattr(tts, "synthesize", silent)
    monkeypatch.setattr(look_intent, "maybe_look", nothing)
    monkeypatch.setattr(turns, "log_transcript_turn", nothing)
    for ref in (LOCAL, API):
        history, unprompted = [{"role": "system", "content": "sys"}], []
        turns.record_unprompted(history, "Whoa, $4,210 in checking?", True, [], unprompted)
        await turns.run_turn(Socket(), history, "hm?", True, [], model_ref=ref, unprompted=unprompted)
    assert "$4,210" in seen[0] and "$4,210" not in seen[1]


@pytest.mark.asyncio
async def test_a_reply_with_no_words_is_an_error_not_silence(tmp_path, monkeypatch):
    # Found live (D-064): qwen3.5:9b on High spent the whole reply cap thinking, and
    # the turn ended with nothing on screen and nothing said.
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha")
    waifu = WaifuRegistry(premade, tmp_path / "user").get("alpha")
    sent = []

    async def thought_only(role, messages, tools, **kwargs):
        yield {"type": "usage", "tokens_in": 2710, "tokens_out": 512}

    async def nothing(*_a, **_k):
        return None

    async def silent(text, voice=None):
        return b""

    class Socket:
        state = SimpleNamespace(waifu=waifu)

        async def send_json(self, payload):
            sent.append(payload)

    monkeypatch.setattr(router, "stream_with_tools", thought_only)
    monkeypatch.setattr(tts, "synthesize", silent)
    monkeypatch.setattr(look_intent, "maybe_look", nothing)
    monkeypatch.setattr(turns, "log_transcript_turn", nothing)
    history = [{"role": "system", "content": "sys"}]
    await turns.run_turn(Socket(), history, "17 times 23?", True, [], model_ref=LOCAL, effort="high")
    errors = [f["data"] for f in sent if f["type"] == "error"]
    assert [(e["code"], e["reason"]) for e in errors] == [("model_failed", "EMPTY_REPLY")]
    assert errors[0]["actions"] == ["retry", "switch_model"] and errors[0]["model_ref"] == LOCAL
    assert sent[-1]["type"] == "turn_done" and sent[-1]["data"]["text"] == ""
    assert history == [{"role": "system", "content": "sys"}]   # no one-sided exchange left behind


def test_api_failures_say_which_kind_in_plain_words():
    # FR-R-5: quota, auth, rate limit, timeout and provider error, each with Retry / Switch model
    cases = [
        (ProviderError("401 from https://api.example/v1: 'bad key'", status=401), "AUTH", "The API key was refused."),
        (ProviderError("402 from https://api.example/v1", status=402), "QUOTA", "The API account is out of credit."),
        (ProviderError("429 from https://api.example/v1", status=429), "RATE_LIMIT", "The provider is limiting requests"),
        (ProviderError("timed out waiting", timeout=True), "TIMEOUT", "The provider did not answer in time."),
        (ProviderError("503 from https://api.example/v1", status=503), "PROVIDER_ERROR", "a problem on its side"),
        (ProviderError("the reply stream was cut off"), "PROVIDER_ERROR", "The chosen model failed."),
    ]
    for exc, reason, words in cases:
        failure = protocol.model_failure(exc)
        assert failure["reason"] == reason and words in failure["message"], reason
        assert failure["message"].endswith("Retry, or switch model.") and failure["actions"] == ["retry", "switch_model"]
        assert failure["detail"] == str(exc)   # the provider's own words stay available


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

    monkeypatch.setattr(boot, "load_chat_model", fake_load)
    set_config(monkeypatch, dataclasses.replace(
        CONFIG, chat=dataclasses.replace(CONFIG.chat, default_model_ref=DEFAULT, load_delay_s=0)
    ))
    monkeypatch.setattr(model_loader.LOADER, "enabled", True)
    return kernel[0], seen


DEFAULT = "local:ollama/qwen3.5:9b"   # D-060: an Ollama default wakes up on its own
BIG = "local:llamacpp/big"


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
        _status_until(ws, "ready", DEFAULT)                       # the thread's (default) model woke up
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        _until(ws, "thread_updated")
        loading = _status_until(ws, "loading", LOCAL)
        assert loading["label"] == "qwen3.5:4b"
        _status_until(ws, "ready", LOCAL)
        ws.send_json({"v": 1, "type": "model_load", "data": {}})  # Try again: loads even though it is up
        _status_until(ws, "ready", LOCAL)
    assert seen == [DEFAULT, LOCAL, LOCAL]


def test_a_new_thread_keeps_the_pick_and_does_not_load_again(loads):
    client, seen = loads
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _status_until(ws, "ready", DEFAULT)
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        _status_until(ws, "ready", LOCAL)
        ws.send_json({"v": 1, "type": "thread_new", "data": {}})
        opened, _ = _until(ws, "thread_opened")
        assert opened["data"]["thread"]["model_ref"] == LOCAL       # FR-M-5: inherits the last selection
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
    assert seen == [DEFAULT, LOCAL]


def test_a_llamacpp_thread_starts_its_server_only_when_picked(loads, monkeypatch):
    # D-060: opening a thread whose model is the 35B loads nothing; picking it does
    client, seen = loads
    set_config(monkeypatch, dataclasses.replace(
        CONFIG, chat=dataclasses.replace(CONFIG.chat, default_model_ref=BIG, load_delay_s=0)
    ))
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        first, _ = _until(ws, "model_status")
        assert first["data"]["state"] == "idle"
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": BIG}})
        _status_until(ws, "ready", BIG)
    assert seen == [BIG]


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

    monkeypatch.setattr(model_listing, "ollama_rows", no_ollama)
    monkeypatch.setattr(router, "get_router", lambda: Rt())
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        ws.send_json({"v": 1, "type": "model_list", "data": {"refresh": True}})
        listed, _ = _until(ws, "model_list")
    data = listed["data"]
    assert data["local_error"] == "Ollama is not running" and data["api"] == [] and data["api_key"] is False
    assert data["default_ref"] == model_listing.default_ref(CONFIG)


def test_switching_models_waits_for_the_reply(kernel, monkeypatch):
    client, _ = kernel

    async def slow_stream(role, messages, tools, **kwargs):
        await asyncio.sleep(0.4)
        yield {"type": "content", "text": "done [happy]"}

    monkeypatch.setattr(router, "stream_with_tools", slow_stream)
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "send", "data": {"text": "hi"}})
        _until(ws, "turn_start")
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        err, _ = _until(ws, "error")
        assert err["data"]["code"] == "turn_running"
        _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": LOCAL}})
        updated, _ = _until(ws, "thread_updated")
        assert updated["data"]["thread"]["model_ref"] == LOCAL


def test_only_the_main_window_loads_models(loads, monkeypatch):
    # Review finding: a second window opening an Ollama thread used to stop
    # llama-server under the main window's streaming reply. Observers only watch.
    client, seen = loads
    manager = conversation.get_manager()
    other = manager.store.create_thread(model_ref=LOCAL)
    manager.store.create_thread(model_ref=None)                             # newest: the one that opens
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _status_until(ws, "ready", DEFAULT)
        # shortcut: demote this window instead of opening a second one (each TestClient
        # socket gets its own event loop, which the kernel's shared objects reject)
        monkeypatch.setattr(hub, "driver", object())
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": other.id}})
        opened, _ = _until(ws, "thread_opened")
        assert opened["data"]["thread"]["model_ref"] == LOCAL
        ws.send_json({"v": 1, "type": "model_load", "data": {}})
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
    assert seen == [DEFAULT]


def test_hello_tells_the_window_the_defaults(kernel):
    client, _ = kernel
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"v": 1, "type": "hello", "id": "h1", "data": {"client": "main", "protocol": 1}})
        hello, _ = _until(ws, "hello")
    assert hello["data"]["default_model_ref"] == model_listing.default_ref(CONFIG)
    assert hello["data"]["default_effort"] == CONFIG.chat.default_effort


def test_a_turn_waits_for_its_model_and_warm_up_off_loads_on_the_first_message(loads, monkeypatch):
    # Review findings: a message sent before the delayed load started reached
    # Ollama while llama-server still held the memory; and warm_up_on_start: false
    # still loaded the model as soon as the window opened.
    client, seen = loads
    set_config(monkeypatch, dataclasses.replace(
        CONFIG,
        llm=dataclasses.replace(CONFIG.llm, warm_up_on_start=False),
        # a load that would start much later; and a llama.cpp model: a message is a pick (D-060)
        chat=dataclasses.replace(CONFIG.chat, load_delay_s=30, default_model_ref=BIG),
    ))
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "thread_list", "data": {}})
        _until(ws, "thread_list")
        assert seen == []                                                   # opening did not load
        ws.send_json({"v": 1, "type": "send", "data": {"text": "hi"}})
        _status_until(ws, "ready", "local:llamacpp/big")                   # the message loaded it, at once
        _until(ws, "turn_done")
    assert seen == ["local:llamacpp/big"]


def test_unload_x_unloads_only_what_the_card_offers_then_loads_again(loads, monkeypatch):
    # K1-09b (SPEC §5, D-071): the refusal names the 4B; Unload drops it and tries again
    import vram

    client, seen = loads
    unloaded = []
    four = "local:ollama/qwen3.5:4b"

    async def load(ref):
        seen.append(ref)
        if not unloaded:
            raise vram.VramFullError("It needs about 8.1 GB.", (vram.Resident("qwen3.5:4b", 3207, four),))

    async def unload(name):
        unloaded.append(name)

    monkeypatch.setattr(boot, "load_chat_model", load)
    monkeypatch.setattr(llm, "unload_model", unload)
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        failed = _status_until(ws, "failed", DEFAULT)
        assert failed["unload"] == [{"ref": four, "label": "qwen3.5:4b"}]
        ws.send_json({"v": 1, "type": "model_unload", "data": {"ref": "local:ollama/llama3:8b"}})
        err, _ = _until(ws, "error")
        assert err["data"]["code"] == "bad_message" and unloaded == []      # only what the card offers
        ws.send_json({"v": 1, "type": "model_unload", "data": {"ref": four}})
        _status_until(ws, "ready", DEFAULT)
    assert unloaded == ["qwen3.5:4b"] and seen == [DEFAULT, DEFAULT]
