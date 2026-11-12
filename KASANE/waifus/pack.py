"""One waifu pack on disk: parsed, validated, never partially loaded (FR-W-1, 4, 6).

There are deliberately NO model, tool, permission, memory or scene keys: a waifu is a
voice and a persona only (D-003). Unknown keys are rejected so nobody can smuggle one in.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

SCHEMA_VERSION = 1
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
MAX_PROMPT_CHARS = 20_000
MIN_PROMPT_CHARS = 20
MAX_TRAITS = 12


class PackError(ValueError):
    """A pack is unusable. The message is written for the user, not for a log."""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug[:32].strip("-")


class VoiceSpec(BaseModel):
    """Voice block of waifu.yaml. Only `gpt_sovits` exists in K0 (D-036 adds the others)."""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["gpt_sovits"] = "gpt_sovits"
    ref_audio: str
    ref_text: str = Field(min_length=1)
    ref_lang: str = Field(default="en", min_length=2, max_length=8)

    @field_validator("ref_text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("the transcript of the voice clip is empty")
        return value


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(alias="schema")
    id: str
    name: str = Field(min_length=1, max_length=32)
    traits: list[str] = Field(min_length=1, max_length=MAX_TRAITS)
    vrm: str
    prompt: str
    voice: VoiceSpec
    created: str | None = None

    @field_validator("id")
    @classmethod
    def _slug(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("id must be 2-32 characters of a-z, 0-9 and '-', starting with a letter or digit")
        return value

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is empty")
        return value

    @field_validator("traits")
    @classmethod
    def _traits(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip() for t in value]
        for trait in cleaned:
            if not 2 <= len(trait) <= 24:
                raise ValueError(f"trait {trait!r} must be 2-24 characters")
        return cleaned


class Waifu(BaseModel):
    """A validated waifu. `prompt` is the persona text itself, already loaded."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    id: str
    name: str
    traits: tuple[str, ...]
    prompt: str
    vrm_path: Path
    voice: VoiceSpec
    ref_audio_path: Path
    premade: bool
    root: Path


def _fail(root: Path, message: str) -> PackError:
    return PackError(f"{root.name}: {message}")


def load_pack(root: Path, *, premade: bool = False) -> Waifu:
    """Reads and validates one pack folder, or raises PackError with a plain message."""
    root = Path(root)
    manifest_path = root / "waifu.yaml"
    if not manifest_path.is_file():
        raise _fail(root, "waifu.yaml is missing")
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise _fail(root, f"waifu.yaml cannot be read ({exc})") from exc
    if not isinstance(raw, dict):
        raise _fail(root, "waifu.yaml must be a mapping")
    if raw.get("schema") != SCHEMA_VERSION:
        raise _fail(root, f"unsupported schema {raw.get('schema')!r} (expected {SCHEMA_VERSION})")
    try:
        manifest = _Manifest.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise _fail(root, f"{where}: {first['msg']}") from exc

    prompt_path = _inside(root, manifest.prompt, "prompt")
    if not prompt_path.is_file():
        raise _fail(root, f"prompt file {manifest.prompt!r} is missing")
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if len(prompt) < MIN_PROMPT_CHARS:
        raise _fail(root, "the system prompt is empty or far too short")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise _fail(root, f"the system prompt is longer than {MAX_PROMPT_CHARS} characters")

    vrm_path = _inside(root, manifest.vrm, "vrm")
    if vrm_path.suffix.lower() != ".vrm":
        raise _fail(root, f"vrm must be a .vrm file, got {vrm_path.name!r}")
    if not vrm_path.is_file():
        raise _fail(root, f"VRM file {manifest.vrm!r} is missing")

    ref_audio = _inside(root, manifest.voice.ref_audio, "voice.ref_audio")
    if ref_audio.suffix.lower() != ".wav":
        raise _fail(root, f"voice clip must be a .wav file, got {ref_audio.name!r}")
    if not ref_audio.is_file():
        raise _fail(root, f"voice clip {manifest.voice.ref_audio!r} is missing")

    return Waifu(
        id=manifest.id,
        name=manifest.name,
        traits=tuple(manifest.traits),
        prompt=prompt,
        vrm_path=vrm_path,
        voice=manifest.voice,
        ref_audio_path=ref_audio,
        premade=premade,
        root=root,
    )


def _inside(root: Path, relative: str, field: str) -> Path:
    """A pack may only reference files inside its own folder."""
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        raise PackError(f"{root.name}: {field} points outside the pack folder") from None
    return candidate
