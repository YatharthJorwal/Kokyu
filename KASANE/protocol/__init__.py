"""Typed WebSocket protocol, version 1 (K1-00b; ARCHITECTURE §5.3).

Every message added from K1 on travels in one envelope:

    {"v": 1, "type": "...", "id": "...", "thread": "..." | null, "data": {...}}

Client messages are validated here before the endpoint acts on them; a bad
message is answered with a typed `error` frame, never a crash. Yuri's older
flat messages (`user_text`, `speak`, `turn_end`, ...) keep working unchanged
until the K1 shell replaces the widget (D-049); `parse_client` returns None
for them so the endpoint's existing branches handle them.

The TypeScript mirror is `src/net/protocol.ts`; a test compares the two lists
of message types so they cannot drift apart silently.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from router import model_ref as model_refs

PROTOCOL_VERSION = 1

TITLE_MAX = 200
QUERY_MAX = 200


class _Data(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Empty(_Data):
    pass


class Hello(_Data):
    client: Literal["main", "pet", "dev"] = "main"
    protocol: int


class ThreadRef(_Data):
    id: str = Field(min_length=1, max_length=64)


class ThreadRename(_Data):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(max_length=TITLE_MAX)


class ThreadSearch(_Data):
    query: str = Field(default="", max_length=QUERY_MAX)


class SetModel(_Data):
    model_ref: str | None = None      # null = the local default model

    @field_validator("model_ref")
    @classmethod
    def _valid_ref(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        try:
            return str(model_refs.parse(value))
        except model_refs.ModelRefError as exc:
            raise ValueError(str(exc)) from None


class SetEffort(_Data):
    effort: Literal["off", "low", "medium", "high"] | None = None


# Client -> kernel, versioned. The data model for each type.
CLIENT_TYPES: dict[str, type[_Data]] = {
    "hello": Hello,
    "thread_list": Empty,
    "thread_search": ThreadSearch,
    "thread_new": Empty,
    "thread_open": ThreadRef,
    "thread_delete": ThreadRef,
    "thread_rename": ThreadRename,
    "set_model": SetModel,
    "set_effort": SetEffort,
}

# Kernel -> client, versioned.
SERVER_TYPES: tuple[str, ...] = (
    "hello",
    "thread_opened",
    "thread_list",
    "thread_message",
    "thread_updated",
    "turn_start",
    "token",
    "turn_done",
    "error",
)

ERROR_CODES: tuple[str, ...] = (
    "bad_message",
    "protocol_version",
    "unknown_thread",
    "unknown_waifu",
    "turn_running",
    "threads_unavailable",
    "model_blocked",
    "model_failed",
)


class ProtocolError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ClientMessage(BaseModel):
    """A validated client frame."""

    type: str
    id: str | None = None
    thread: str | None = None
    data: Any


def frame(type_: str, data: dict[str, Any] | None = None, *, thread: str | None = None, id: str | None = None) -> dict[str, Any]:
    """A kernel -> client envelope."""
    if type_ not in SERVER_TYPES:
        raise ValueError(f"not a protocol message type: {type_}")
    return {"v": PROTOCOL_VERSION, "type": type_, "id": id or uuid.uuid4().hex[:12], "thread": thread, "data": data or {}}


def error_frame(code: str, message: str, *, thread: str | None = None, reply_to: str | None = None) -> dict[str, Any]:
    if code not in ERROR_CODES:
        raise ValueError(f"unknown error code: {code}")
    return frame("error", {"code": code, "message": message, "reply_to": reply_to}, thread=thread)


def model_failure(exc: BaseException) -> dict[str, Any] | None:
    """The `error` frame data for a failed chat model (FR-R-5), or None for an
    error that is not about the user's model choice (e.g. the local server is
    down and no model was chosen: the existing spoken line covers that).
    `actions` tells the chat view which buttons to show."""
    from router.errors import ProviderError, RouteBlockedError

    if isinstance(exc, RouteBlockedError):
        return {
            "code": "model_blocked",
            "reason": exc.reason,
            "message": exc.message,
            "model_ref": exc.model_ref,
            "actions": ["retry", "switch_model"],
            "reply_to": None,
        }
    if isinstance(exc, ProviderError):
        return {
            "code": "model_failed",
            "reason": "PROVIDER_ERROR",
            "message": "The API model returned an error. Retry, or switch model.",
            "model_ref": None,
            "actions": ["retry", "switch_model"],
            "reply_to": None,
        }
    return None


def is_versioned(raw: Any) -> bool:
    return isinstance(raw, dict) and "v" in raw


def parse_client(raw: Any) -> ClientMessage | None:
    """Validates a versioned client frame. Returns None for a legacy flat message
    (no `v`), which the endpoint handles as before. Raises ProtocolError otherwise."""
    if not is_versioned(raw):
        return None
    if raw.get("v") != PROTOCOL_VERSION:
        raise ProtocolError(
            "protocol_version",
            f"This window speaks protocol {raw.get('v')!r}; the kernel speaks {PROTOCOL_VERSION}. Restart the app.",
        )
    type_ = raw.get("type")
    model = CLIENT_TYPES.get(type_) if isinstance(type_, str) else None
    if model is None:
        raise ProtocolError("bad_message", f"Unknown message type {type_!r}.")
    data = raw.get("data")
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ProtocolError("bad_message", f"{type_}: data must be an object.")
    try:
        parsed = model.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", ())) or "data"
        raise ProtocolError("bad_message", f"{type_}: {where}: {first.get('msg', 'invalid')}") from None
    msg_id = raw.get("id")
    thread = raw.get("thread")
    return ClientMessage(
        type=type_,
        id=msg_id if isinstance(msg_id, str) else None,
        thread=thread if isinstance(thread, str) else None,
        data=parsed,
    )


def strip_trailing_tag(text: str) -> str:
    """What the user should see of a streamed reply: the trailing emotion tag
    (`[happy]`) or a tag still being written (`[hap`) is hidden. Mirrors
    `stripTrailingTag` in `src/net/protocol.ts`."""
    s = text.rstrip()
    open_at = s.rfind("[")
    if open_at == -1:
        return text
    tail = s[open_at:]
    if "]" in tail[:-1] or " " in tail.strip("[]"):
        return text
    if tail.endswith("]") or "]" not in tail:
        return s[:open_at].rstrip()
    return text
