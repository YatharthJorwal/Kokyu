"""Typed WebSocket protocol, version 1 (K1-00b; ARCHITECTURE §5.3).

Every message added from K1 on travels in one envelope:

    {"v": 1, "type": "...", "id": "...", "thread": "..." | null, "data": {...}}

Client messages are validated here before the endpoint acts on them; a bad
message is answered with a typed `error` frame, never a crash. There is no
other protocol: the seed's flat messages are gone (D-049, D-062).

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


SCENARIO_TITLE_MAX = 120
SCENARIO_FIELD_MAX = 2000
SCENARIO_OPENING_MAX = 4000


class Scenario(_Data):
    """A roleplay's scenario card (FR-MODE-6, D-074). Every field may be empty."""

    title: str = Field(default="", max_length=SCENARIO_TITLE_MAX)
    setting: str = Field(default="", max_length=SCENARIO_FIELD_MAX)
    user_role: str = Field(default="", max_length=SCENARIO_FIELD_MAX)
    her_role: str = Field(default="", max_length=SCENARIO_FIELD_MAX)
    rules: str = Field(default="", max_length=SCENARIO_FIELD_MAX)
    opening: str = Field(default="", max_length=SCENARIO_OPENING_MAX)


class ThreadNew(_Data):
    """FR-MODE-1: a new thread's mode, fixed for its life. `{}` is a chat thread, as
    before modes. (Not to be confused with ScreenCompanion.mode.)"""

    mode: Literal["chat", "roleplay"] = "chat"
    scenario: Scenario | None = None
    # D-091: her profile's Chat button. The new thread starts with her; the open
    # thread gets no divider, since nobody switched in it.
    waifu_id: str | None = Field(default=None, min_length=1, max_length=64)


class ScenarioSave(_Data):
    """FR-MODE-6: save a scenario card; with `id`, the saved card with that id is replaced."""

    id: str | None = Field(default=None, min_length=1, max_length=64)
    card: Scenario


class ScenarioRef(_Data):
    id: str = Field(min_length=1, max_length=64)


class ScreenCompanion(_Data):
    """K1-05b (FR-SC-1..4): turn Task Guide or OCR watch on or off; Task Guide may
    carry the task in the user's words."""

    mode: Literal["task_guide", "ocr_watch"]
    on: bool
    task: str = Field(default="", max_length=TITLE_MAX)


class VoiceModeData(_Data):
    on: bool


class TempChat(_Data):
    on: bool


TEXT_MAX = 20_000
FILE_MAX = 12_000_000   # a resized image as base64, or a text file (capped again in the kernel)


class SendText(_Data):
    text: str = Field(min_length=1, max_length=TEXT_MAX)


class SendFile(_Data):
    filename: str = Field(default="uploaded file", max_length=260)
    kind: Literal["image", "text"]
    content: str = Field(min_length=1, max_length=FILE_MAX)
    caption: str = Field(default="", max_length=TEXT_MAX)


class SwitchWaifu(_Data):
    id: str = Field(min_length=1, max_length=64)


class SetPortrait(_Data):
    """D-091 (FR-W-9): the picture the user chose for her, as base64 (the window has
    already scaled it down), or None to go back to the model's face."""

    waifu_id: str = Field(min_length=1, max_length=64)
    image_b64: str | None = Field(default=None, min_length=1, max_length=FILE_MAX)


class CameraFrame(_Data):
    image_b64: str | None = Field(default=None, max_length=FILE_MAX)   # None: the camera could not answer


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
    effort: Literal["off", "low", "medium", "high", "max"] | None = None   # FR-M-8


class ModelUnload(_Data):
    """K1-09b (SPEC §5, D-071): unload a model the failed-load card names, then try again."""

    ref: str = Field(min_length=1, max_length=300)


class ModelListRequest(_Data):
    refresh: bool = False             # re-fetch the API catalog (FR-M-4)


class FactRef(_Data):
    """K1-13 (FR-MEM-4): one remembered fact."""

    id: int = Field(ge=1)


class FactEdit(_Data):
    id: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2000)


class BudgetSettings(_Data):
    """K1-13b (FR-SET-2, FR-M-7): the spending caps; None is no cap."""

    # Ranges and names are checked in settings_file.change, which says what is wrong
    # in the Settings form; these only bound the size.
    enabled: bool = True
    hourly_usd: float | None = None
    daily_usd: float | None = None
    monthly_usd: float | None = None


class CustomApi(_Data):
    """K1-13b (FR-R-6, D-059, D-070): an OpenAI-compatible endpoint of the user's own."""

    label: str = Field(max_length=200)
    base_url: str = Field(max_length=300)


class ScreenAtStart(_Data):
    """K1-13b (FR-SC-1): which screen companions turn on when Kōkyū starts."""

    task_guide: bool | None = None
    ocr_watch: bool | None = None


class SettingsChange(_Data):
    """K1-13b (FR-SET-2, D-070): only the keys sent change. `ollama_url` "" or null
    and `custom_api` null go back to config.yaml's value."""

    ollama_url: str | None = Field(default=None, max_length=300)
    budget: BudgetSettings | None = None
    custom_api: CustomApi | None = None
    screen: ScreenAtStart | None = None


# Client -> kernel, versioned. The data model for each type.
CLIENT_TYPES: dict[str, type[_Data]] = {
    "hello": Hello,
    "send": SendText,                 # a typed line starts a turn (FR-C-1)
    "send_file": SendFile,            # an attached file or image starts a turn (FR-C-4)
    "stop": Empty,                    # Stop the reply in flight (FR-C-2)
    "switch_waifu": SwitchWaifu,      # FR-S-1: changes only persona and voice
    "set_portrait": SetPortrait,      # D-091 (FR-W-9): her picture, chosen or reset
    "set_temp": TempChat,             # FR-MEM-5: Temp Chat on or off for the open thread
    "camera_frame": CameraFrame,      # the answer to camera_request (K2-07)
    "thread_list": Empty,
    "thread_search": ThreadSearch,
    "thread_new": ThreadNew,          # FR-MODE-1: chat, or a roleplay with its scenario card
    "thread_open": ThreadRef,
    "thread_delete": ThreadRef,
    "thread_rename": ThreadRename,
    "set_model": SetModel,
    "set_effort": SetEffort,
    "model_list": ModelListRequest,   # K1-10: what the chip's popover lists
    "model_load": Empty,              # K1-10: Try again after a failed load
    "model_unload": ModelUnload,      # K1-09b: Unload X on that card, then try again
    "regenerate": Empty,              # K1-04: run the last exchange again (FR-C-9, Retry)
    "screen_companion": ScreenCompanion,  # K1-05b: Task Guide / OCR watch on or off
    "typing": Empty,                  # K1-05b (FR-SC-5): the user is typing; OCR watch keeps quiet
    "voice_mode": VoiceModeData,      # D-061: voice on or off; it starts only when turned on
    "doctor": Empty,                  # K1-13 (FR-SET-3): run the Doctor's checks
    "memory_list": Empty,             # K1-13 (FR-MEM-4): the remembered facts
    "memory_edit": FactEdit,          # correct a fact (the old one is superseded, not deleted)
    "memory_forget": FactRef,         # forget a fact (restorable)
    "memory_restore": FactRef,        # bring a forgotten fact back
    "settings_get": Empty,            # K1-13b (FR-SET-2): the editable settings
    "settings_set": SettingsChange,   # change them; saved to settings.json, applied at once
    "scenario_list": Empty,           # FR-MODE-6: the saved scenario cards
    "scenario_save": ScenarioSave,    # save a card (new, or replacing the one with its id)
    "scenario_delete": ScenarioRef,   # delete a saved card
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
    "model_list",     # K1-10 (FR-M-3, 4, 7)
    "model_status",   # K1-10 (FR-M-6): loading / ready / failed
    "screen_companions",  # K1-05b (FR-SC-2): what is watching the screen
    "voice_status",   # D-061: voice on or off, and how its start is going
    "waifu_state",    # FR-S-1: the roster, the active companion, a pending switch
    "waifu_roster",   # D-091: the roster alone changed (a new picture), for every window
    "surface_status", # this window drives turns, or watches
    "speak",          # one spoken clause: caption text and a WAV (FR-V-2)
    "camera_request", # the kernel wants one camera frame (K2-07)
    "doctor_report",  # K1-13 (FR-SET-3): one row per component, with a fix hint
    "memory_facts",   # K1-13 (FR-MEM-4): live facts, then forgotten ones
    "settings",       # K1-13b (FR-SET-2): the editable settings in effect
    "scenarios",      # FR-MODE-6: the saved scenario cards, newest first
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
    "vision_unavailable",   # K1-05b (FR-SC-3): no local model can see the screen
    "observer",             # another window drives the conversation
    "price_unknown",        # D-083: said once; the turn goes on
    "picture_unreadable",   # D-091: a chosen picture that is not an image
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
    down: the kernel then sends a plain model_failed of its own).
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
        reason, plain = _provider_failure(exc)
        return {
            "code": "model_failed",
            "reason": reason,
            "message": f"{plain} Retry, or switch model.",
            # what the provider said, for the curious and for bug reports (redacted upstream)
            "detail": str(exc).strip().splitlines()[0][:300] if str(exc).strip() else None,
            "model_ref": None,
            "actions": ["retry", "switch_model"],
            "reply_to": None,
        }
    return None


# FR-R-5 names these failures; each gets a sentence a person can act on.
_BY_STATUS = {
    401: ("AUTH", "The API key was refused."),
    403: ("AUTH", "The API key is not allowed to use this model."),
    402: ("QUOTA", "The API account is out of credit."),
    429: ("RATE_LIMIT", "The provider is limiting requests right now."),
}


def _provider_failure(exc: Any) -> tuple[str, str]:
    status = getattr(exc, "status", None)
    if getattr(exc, "timeout", False):
        return "TIMEOUT", "The provider did not answer in time."
    if status in _BY_STATUS:
        return _BY_STATUS[status]
    if isinstance(status, int) and status >= 500:
        return "PROVIDER_ERROR", "The provider had a problem on its side."
    return "PROVIDER_ERROR", "The chosen model failed."


def is_versioned(raw: Any) -> bool:
    return isinstance(raw, dict) and "v" in raw


def parse_client(raw: Any) -> ClientMessage:
    """Validates a client frame. Raises ProtocolError for anything else."""
    if not is_versioned(raw):
        raise ProtocolError("bad_message", "Not a protocol v1 frame.")
    if raw.get("v") != PROTOCOL_VERSION:
        raise ProtocolError(
            "protocol_version",
            f"This window speaks protocol {raw.get('v')!r}; Kōkyū's engine speaks {PROTOCOL_VERSION}. Restart the app.",
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
