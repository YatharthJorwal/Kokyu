"""Model references and effort (SPEC §3.4, FR-M-8; K1-00c).

A thread names its model as `<kind>:<backend>/<id>`, for example
`local:ollama/qwen3.5:9b` or `api:airouter/<catalog-id>`. This module parses
that string and maps the backend to a router provider name. Pure: no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

# backend -> router provider. llama.cpp and generic OpenAI-compatible providers
# arrive with K1-01 / K1-08b; until then they are rejected with a clear message.
PROVIDERS: dict[tuple[str, str], str] = {
    ("local", "ollama"): "local_ollama",
    ("api", "airouter"): "airouter",
}

EFFORTS = ("off", "low", "medium", "high")


class ModelRefError(ValueError):
    pass


@dataclass(frozen=True)
class ModelRef:
    kind: str       # local | api
    backend: str    # ollama | airouter | ...
    model: str      # the backend's own model id

    @property
    def provider(self) -> str:
        try:
            return PROVIDERS[(self.kind, self.backend)]
        except KeyError:
            raise ModelRefError(f"{self.kind}:{self.backend} models are not supported yet") from None

    @property
    def is_local(self) -> bool:
        return self.kind == "local"

    def __str__(self) -> str:
        return f"{self.kind}:{self.backend}/{self.model}"


def parse(ref: str) -> ModelRef:
    """`local:ollama/qwen3.5:9b` -> ModelRef("local", "ollama", "qwen3.5:9b").
    Only the first `/` splits backend from model; model ids may contain `:` and `/`."""
    text = (ref or "").strip()
    kind, sep, rest = text.partition(":")
    if not sep or kind not in ("local", "api"):
        raise ModelRefError(f"not a model reference: {ref!r} (expected local:<backend>/<id> or api:<backend>/<id>)")
    backend, sep, model = rest.partition("/")
    if not sep or not backend or not model.strip():
        raise ModelRefError(f"not a model reference: {ref!r} (missing backend or model id)")
    parsed = ModelRef(kind, backend, model.strip())
    parsed.provider  # noqa: B018 -- raises for an unsupported backend
    return parsed


def check_effort(effort: str | None) -> str | None:
    if effort is None:
        return None
    if effort not in EFFORTS:
        raise ModelRefError(f"effort must be one of {EFFORTS}, not {effort!r}")
    return effort


def ollama_think(effort: str | None) -> bool | None:
    """Ollama's `think` flag for hybrid-thinking models. None leaves the config default."""
    if effort is None:
        return None
    return effort != "off"


def openai_reasoning_effort(effort: str | None) -> str | None:
    """OpenAI-style `reasoning_effort`. `off` and None send nothing."""
    return effort if effort in ("low", "medium", "high") else None
