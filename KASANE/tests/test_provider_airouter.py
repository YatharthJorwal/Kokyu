"""AI Router provider against a fake SSE server. No key, no network."""

import json

import httpx
import pytest

from config import ProviderConfig
from router.errors import ProviderError, StreamFailed
from router.providers.airouter import AirouterProvider
from router.providers.llamacpp import LlamaCppProvider
from router.types import ModelRequest, Usage

CFG = ProviderConfig(
    name="airouter",
    base_url="https://api.example/v1",
    api_style="openai",
)


def sse(*events: dict) -> bytes:
    lines = [f"data: {json.dumps(event)}\n\n" for event in events]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode("utf-8")


def chunk(delta: dict, finish: str | None = None) -> dict:
    return {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}


def provider(handler, *, key="test-key"):
    return AirouterProvider(CFG, key, transport=httpx.MockTransport(handler))


async def collect(p):
    return [
        c
        async for c in p.complete(ModelRequest(role="mind", messages=({"role": "user", "content": "hi"},)), model="m")
    ]


@pytest.mark.asyncio
async def test_streams_content_chunks():
    body = sse(chunk({"content": "Hel"}), chunk({"content": "lo"}, "stop"))
    events = await collect(provider(lambda request: httpx.Response(200, content=body)))
    assert "".join(c.text for c in events if c.kind == "content") == "Hello"
    assert events[-1].kind == "done"


@pytest.mark.asyncio
async def test_tool_call_fragments_are_assembled():
    body = sse(
        chunk(
            {
                "tool_calls": [
                    {"index": 0, "function": {"name": "capture_screen", "arguments": '{"reg'}}
                ]
            }
        ),
        chunk({"tool_calls": [{"index": 0, "function": {"arguments": 'ion": "full"}'}}]}, "tool_calls"),
    )
    events = await collect(provider(lambda request: httpx.Response(200, content=body)))
    calls = [c for e in events if e.kind == "tool_calls" for c in e.calls]
    assert calls == [{"name": "capture_screen", "arguments": {"region": "full"}}]


@pytest.mark.asyncio
async def test_usage_is_reported():
    body = sse(chunk({"content": "x"}), {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 3}})
    events = await collect(provider(lambda request: httpx.Response(200, content=body)))
    done = events[-1]
    assert done.usage is not None
    assert done.usage.prompt_tokens == 10
    assert done.usage.completion_tokens == 3


@pytest.mark.asyncio
async def test_missing_usage_is_estimated_thinking_included():
    # FR-R-2 (K1-08 review): the call is billed either way; reasoning is billed as output.
    body = sse(chunk({"reasoning_content": "r" * 30}), chunk({"content": "x" * 10}, "stop"))
    events = await collect(provider(lambda request: httpx.Response(200, content=body)))
    assert events[-1].usage == Usage(prompt_tokens=None, completion_tokens=10, estimated=True)


@pytest.mark.asyncio
async def test_rate_limit_raises_provider_error():
    p = provider(lambda request: httpx.Response(429, json={"error": "slow down"}))
    with pytest.raises(ProviderError) as err:
        await collect(p)
    assert "429" in str(err.value) and err.value.status == 429 and not err.value.timeout   # FR-R-5


@pytest.mark.asyncio
async def test_a_timeout_says_so():
    def slow(request):
        raise httpx.ReadTimeout("no answer")

    with pytest.raises(ProviderError) as err:
        await collect(provider(slow))
    assert err.value.timeout and err.value.status is None


@pytest.mark.asyncio
async def test_server_error_raises_provider_error():
    p = provider(lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(ProviderError):
        await collect(p)


@pytest.mark.asyncio
async def test_malformed_frames_are_ignored():
    body = b'data: {"choices": [{"delta": {"content": "a"}}]}\n\ndata: not json\n\ndata: [DONE]\n\n'
    events = await collect(provider(lambda request: httpx.Response(200, content=body)))
    assert "".join(c.text for c in events if c.kind == "content") == "a"


@pytest.mark.asyncio
async def test_json_schema_retried_without_response_format():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append("response_format" in payload)
        if "response_format" in payload:
            return httpx.Response(400, json={"error": "unsupported response_format"})
        return httpx.Response(200, content=sse(chunk({"content": '{"ok":true}'}, "stop")))

    p = provider(handler)
    events = [
        c
        async for c in p.complete(
            ModelRequest(
                role="mind",
                messages=({"role": "user", "content": "json"},),
                schema={"type": "object"},
            ),
            model="m",
        )
    ]
    assert seen == [True, False]
    assert "".join(c.text for c in events if c.kind == "content") == '{"ok":true}'


@pytest.mark.asyncio
async def test_authorization_header_is_sent():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, content=sse(chunk({"content": "x"}, "stop")))

    await collect(provider(handler, key="secret-key"))
    assert captured["auth"] == "Bearer secret-key"


# -- K1-08 review gaps (FR-R-2, FR-R-5, FR-R-6) ---------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        sse(chunk({"content": "Hel"}), {"error": {"message": "upstream overloaded"}}),     # an error mid-reply
        sse(chunk({"content": "Hel"}, "error")),                                           # finish_reason error
        b'{"error": {"message": "no credits"}}',                                            # JSON error sent with 200
        b'data: {"choices": [{"delta": {"content": "Hel"}}]}\n\n',                          # cut off: no [DONE]
        b"data: [DONE]\n\n",                                                                 # nothing at all
    ],
)
async def test_a_reply_that_fails_inside_the_stream_raises(body):
    with pytest.raises(ProviderError):
        await collect(provider(lambda request: httpx.Response(200, content=body)))


@pytest.mark.asyncio
async def test_a_key_the_provider_echoes_back_never_reaches_the_error():
    p = provider(lambda request: httpx.Response(401, text="invalid key test-key-0123456789abcdef"), key="test-key-0123456789abcdef")
    with pytest.raises(ProviderError) as err:
        await collect(p)
    assert "test-key-0123456789abcdef" not in str(err.value) and "[secret]" in str(err.value)


@pytest.mark.asyncio
async def test_usage_comes_before_the_tool_calls_because_the_caller_stops_there():
    body = sse(
        chunk({"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "capture_screen", "arguments": "{}"}}]}, "tool_calls"),
        {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 3}},
    )
    events = await collect(provider(lambda request: httpx.Response(200, content=body)))
    assert [e.kind for e in events] == ["usage", "tool_calls", "done"] and events[0].usage.prompt_tokens == 10


@pytest.mark.asyncio
async def test_a_tool_round_goes_out_in_openai_shape():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=sse(chunk({"content": "ok"}, "stop")))

    history = (
        {"role": "user", "content": "what's on screen?"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "capture_screen", "arguments": {"region": "full"}}}]},
        {"role": "tool", "content": "a code editor"},
    )
    await collect_request(provider(handler), ModelRequest(role="chat", messages=history))
    call, result = seen[0]["messages"][1], seen[0]["messages"][2]
    assert call["tool_calls"] == [
        {"id": "call_1", "type": "function", "function": {"name": "capture_screen", "arguments": '{"region": "full"}'}}
    ]
    assert result == {"role": "tool", "content": "a code editor", "tool_call_id": "call_1"}


async def collect_request(p, request):
    return [c async for c in p.complete(request, model="m")]


@pytest.mark.asyncio
async def test_a_failure_after_thinking_alone_is_a_billable_stream_failure():
    body = b'data: {"choices": [{"delta": {"reasoning_content": "let me think"}}]}\n\n'   # then the line drops
    with pytest.raises(StreamFailed):
        await collect(provider(lambda request: httpx.Response(200, content=body)))


@pytest.mark.asyncio
async def test_a_cap_spent_on_thinking_is_an_error_for_an_api_model_only():
    body = sse(chunk({"reasoning_content": "hmm " * 50}, "length"))
    with pytest.raises(StreamFailed, match="reply cap"):
        await collect(provider(lambda request: httpx.Response(200, content=body)))
    local = provider(lambda request: httpx.Response(200, content=body))
    local.paid = False                                          # llama-server's one-token warm-up
    assert LlamaCppProvider.paid is False
    assert [e.kind for e in await collect(local)] == ["done"]


@pytest.mark.asyncio
async def test_a_key_across_the_error_cut_is_still_redacted():
    key = "test-key-0123456789abcdef"
    p = provider(lambda request: httpx.Response(401, text="x" * 290 + key), key=key)
    with pytest.raises(ProviderError) as err:
        await collect(p)
    assert "test-key-0" not in str(err.value) and "[secret]" in str(err.value)


@pytest.mark.asyncio
async def test_usage_sent_after_a_failed_finish_still_reaches_the_bill():
    body = sse(chunk({"reasoning_content": "hmm"}, "length"), {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 7200}})
    events = []
    with pytest.raises(StreamFailed):
        async for event in provider(lambda request: httpx.Response(200, content=body)).complete(
            ModelRequest(role="chat", messages=({"role": "user", "content": "hi"},)), model="m"
        ):
            events.append(event)
    assert [e.kind for e in events] == ["usage"] and events[0].usage.completion_tokens == 7200
