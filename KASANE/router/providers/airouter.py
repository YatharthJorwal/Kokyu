"""AI Router provider (OpenAI-compatible SSE).

Everything here is testable against `httpx.MockTransport`, which is how the
suite exercises 200/429/500, tool-call deltas, missing usage, and malformed
frames without a key or a network.

No retries for network errors: the router's candidate chain owns fallback, and
two retry layers fighting each other is how a 429 becomes a four-second pause.
The single exception is a 400 caused by `response_format`, retried once without
it, because some providers reject the field rather than ignoring it.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from config import ProviderConfig
from router import model_ref as model_refs
from router.errors import ProviderError, StreamFailed
from router.redact import redact
from router.types import ModelChunk, ModelRequest, Usage


def openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kernel (Ollama-shaped) messages -> OpenAI chat messages: an assistant tool
    call gets an id, type and JSON-string arguments, and the tool result after it
    the matching `tool_call_id`, as OpenAI-compatible APIs require."""
    out: list[dict[str, Any]] = []
    pending_ids: list[str] = []
    counter = 0
    for message in messages:
        role = message.get("role")
        if role == "assistant" and message.get("tool_calls"):
            calls = []
            for call in message["tool_calls"]:
                fn = call.get("function", {})
                args = fn.get("arguments", {})
                counter += 1
                call_id = call.get("id") or f"call_{counter}"
                pending_ids.append(call_id)
                calls.append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "arguments": args if isinstance(args, str) else json.dumps(args),
                    },
                })
            out.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
        elif role == "tool":
            entry = {"role": "tool", "content": message.get("content") or ""}
            if pending_ids:
                entry["tool_call_id"] = pending_ids.pop(0)
            out.append(entry)
        else:
            out.append({"role": role, "content": message.get("content") or ""})
    return out


class AirouterProvider:
    name = "airouter"
    # A paid API: a reply with no usage gets an estimated one (it is billed, FR-R-2),
    # and a reply cap used up before any answer is an error the turn shows (FR-R-5).
    paid = True

    def __init__(
        self,
        cfg: ProviderConfig,
        api_key: str | None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.cfg = cfg
        self.api_key = api_key
        self._transport = transport
        self._timeout = httpx.Timeout(timeout_s or cfg.request_timeout_s, connect=5.0)

    # -- requests ------------------------------------------------------------

    def _payload(self, request: ModelRequest, model: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": openai_messages([dict(message) for message in request.messages]),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        temperature = request.temperature
        if temperature is None:
            temperature = 0.6
        payload["temperature"] = temperature
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = list(request.tools)
            payload["tool_choice"] = "auto"
        if request.schema:
            payload["response_format"] = {"type": "json_object"}
        reasoning = model_refs.openai_reasoning_effort(request.effort)
        if reasoning:
            payload["reasoning_effort"] = reasoning
        return payload

    def _safe(self, text: str) -> str:
        """Provider text as it may be logged, audited, shown and spoken: never the
        key, even when the provider echoes it back (FR-R-6)."""
        if self.api_key:
            text = text.replace(self.api_key, "[secret]")
        return redact(text)[0]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=10.0) as client:
                response = await client.get(f"{self.cfg.base_url.rstrip('/')}/models")
            return response.status_code < 400
        except httpx.RequestError:
            return False

    # -- streaming -----------------------------------------------------------

    async def complete(self, request: ModelRequest, *, model: str) -> AsyncIterator[ModelChunk]:
        payload = self._payload(request, model)
        url = f"{self.cfg.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if self.api_key:  # a keyless local server (llama-server) rejects "Bearer " with no token
            headers["Authorization"] = f"Bearer {self.api_key}"

        accepted = False       # past HTTP 200: a failure from here on may have been billed
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code >= 400:
                            body = (await response.aread()).decode("utf-8", "replace")
                            if (
                                attempt == 0
                                and response.status_code == 400
                                and "response_format" in payload
                            ):
                                payload.pop("response_format", None)
                                continue
                            # Redact the whole text, then cut: a key across the cut would slip past.
                            raise ProviderError(
                                self._safe(f"{response.status_code} from {url}: {body!r}")[:400], status=response.status_code
                            )
                        accepted = True
                        async for chunk in self._frames(response, cap=request.max_tokens):
                            yield chunk
                        return
            except httpx.TimeoutException as exc:
                failure = StreamFailed if accepted else ProviderError
                raise failure(self._safe(f"timed out waiting for {url}: {exc}")[:400], timeout=True) from exc
            except httpx.RequestError as exc:
                failure = StreamFailed if accepted else ProviderError
                raise failure(self._safe(f"couldn't reach {url}: {exc}")[:400]) from exc

    async def _frames(self, response: httpx.Response, *, cap: int | None = None) -> AsyncIterator[ModelChunk]:
        """Chunks from an SSE body. A reply that never finishes, never starts, or
        carries an error raises ProviderError, so the turn shows it (FR-R-5); once
        frames have come, StreamFailed, because the call may have been billed."""
        usage: Usage | None = None
        tool_parts: dict[int, dict[str, str]] = {}
        frames = 0
        finished = False               # [DONE] or a finish_reason
        last_finish: str | None = None
        said = 0                       # characters of answer (content)
        generated = 0                  # characters generated: answer, reasoning, tool calls
        other: list[str] = []          # non-SSE lines: a JSON error body sent with 200

        async for raw in response.aiter_lines():
            line = raw.strip()
            if not line:
                continue
            if not line.startswith("data:"):
                if len(other) < 5:
                    other.append(line)
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                finished = True
                break
            try:
                event = json.loads(data)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            frames += 1
            reported = event.get("usage")
            if isinstance(reported, dict):
                usage = Usage(
                    prompt_tokens=_int(reported.get("prompt_tokens")),
                    completion_tokens=_int(reported.get("completion_tokens")),
                )

            if event.get("error"):
                if usage is not None:
                    yield ModelChunk(kind="usage", usage=usage)   # the bill uses the real count (D-058)
                raise StreamFailed(self._safe(f"the provider reported an error: {json.dumps(event['error'])}")[:400])

            choices = event.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            choice = choices[0] if isinstance(choices[0], dict) else {}
            if choice.get("finish_reason") == "error":
                if usage is not None:
                    yield ModelChunk(kind="usage", usage=usage)
                raise StreamFailed("the provider ended the reply with an error")
            if choice.get("finish_reason"):
                finished = True
                last_finish = str(choice["finish_reason"])
            delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}

            for key in ("reasoning_content", "reasoning"):   # DeepSeek / llama-server, OpenRouter
                thought = delta.get(key)
                if isinstance(thought, str):
                    generated += len(thought)
            text = delta.get("content")
            if isinstance(text, str) and text:
                said += len(text)
                generated += len(text)
                yield ModelChunk.content(text)

            for raw_call in delta.get("tool_calls") or []:
                if not isinstance(raw_call, dict):
                    continue
                index = raw_call.get("index", 0)
                function = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
                part = tool_parts.setdefault(int(index), {"name": "", "arguments": ""})
                if isinstance(function.get("name"), str) and function["name"]:
                    part["name"] = function["name"]
                if isinstance(function.get("arguments"), str):
                    part["arguments"] += function["arguments"]
                    generated += len(function["arguments"])

        if frames == 0:
            body = " ".join(other)
            raise ProviderError(self._safe("the provider sent no reply" + (f": {body}" if body else ""))[:400])
        if not finished:
            raise StreamFailed("the reply stream was cut off")
        calls = [call for call in _finish_tool_parts(tool_parts) if call["name"]]
        if self.paid and last_finish == "length" and not said and not calls:
            if usage is not None:
                yield ModelChunk(kind="usage", usage=usage)   # usage comes after the finish frame
            raise StreamFailed(
                f"the model used its whole reply cap ({cap or 'default'} tokens) before it answered. "
                "Lower the effort, or raise roles.chat.max_tokens / reasoning_tokens."
            )
        if self.paid and (usage is None or usage.completion_tokens is None):
            # No count from the provider: ~4 characters a token, thinking included (FR-R-2).
            usage = Usage(
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=-(-generated // 4),
                estimated=True,
            )
        if calls:
            # The caller stops reading at tool_calls, so the bill has to come first (FR-R-2).
            yield ModelChunk(kind="usage", usage=usage)
            yield ModelChunk.tool_calls(calls)
        yield ModelChunk.done(usage)


def _finish_tool_parts(parts: dict[int, dict[str, str]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for index in sorted(parts):
        part = parts[index]
        raw = part.get("arguments") or ""
        try:
            arguments = json.loads(raw) if raw.strip() else {}
        except ValueError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        calls.append({"name": part.get("name", ""), "arguments": arguments})
    return calls


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
