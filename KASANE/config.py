"""
Yuri config loader.

One YAML file holds every model, engine, budget and routing choice. Two shapes
are accepted:

- **v2** (what `config/config.example.yaml` documents): `providers`, `models`,
  `roles`, `routing`, `privacy`, `budget`, `voice`, `speech`, plus the v1
  sections.
- **legacy** (the original flat shape, which the older tests still use):
  `llm.base_url/model/api_style` inline, `stt`, `tts`, `memory.embedding`.

Legacy files are derived into the v2 view rather than rejected, because the
ported test suite and any existing user config must keep loading. The rule that
matters: **every key has a code default**. A missing key is
never a startup crash.

Search order when no path is given:
    KASANE/config.yaml
    config/config.yaml
    config/config.example.yaml      (ships with the repo, so a fresh clone runs)
    built-in defaults               (a config-less process still starts)

Secrets are never in the YAML. `resolve_api_key()` reads, in order: the key the
desktop shell handed over (Windows Credential Manager, FR-R-6), then, in a
developer checkout only, the env var named by `api_key_env`, that provider's
section of `secrets.local.yaml` (gitignored), `.env`.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import yaml

import paths
import shell_keys  # noqa: F401 -- takes the shell's keys out of os.environ before any child starts
from provider_presets import API_PRESETS, ENDPOINT_FIELDS, PROVIDER_ID

_ORCHESTRATOR_DIR = pathlib.Path(__file__).parent
EXAMPLE_PATH = paths.config_example_path()
SECRETS_PATH = paths.secrets_path()

_SEARCH_PATHS = (
    _ORCHESTRATOR_DIR / "config.yaml",
    paths.config_dir() / "config.yaml",
    EXAMPLE_PATH,
)

LOCAL_PROVIDERS = frozenset({"local_ollama"})


# ─── helpers ─────────────────────────────────────────────────────────────────


def _section(raw: Mapping[str, Any], key: str) -> dict[str, Any]:
    """A YAML section as a dict, tolerating null/missing/wrong-typed values."""
    value = raw.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any, default: Iterable[Any]) -> tuple[Any, ...]:
    if value is None:
        return tuple(default)
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _build(cls: type, data: Mapping[str, Any]) -> Any:
    """Construct `cls` from a mapping, ignoring unknown keys.

    Unknown keys are ignored on purpose: a config written for a newer build
    must not crash an older one, and vice versa. Required fields are given
    defaults at the dataclass, so a partial section still constructs.
    """
    names = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


# ─── v2 sections ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProviderConfig:
    """One model backend. `local_ollama` is the default for every role; any
    other provider is only reachable by a role that is not `local_only`."""

    name: str = ""
    enabled: bool = True
    # The API slot (`airouter`, D-059): which endpoint this describes, its label and
    # how its catalog prices models. Unused by the local providers.
    preset: str = ""
    label: str = ""
    price_unit: str = "per_million"
    base_url: str = "http://127.0.0.1:11434"
    # "ollama_native" | "openai". The native path is required for num_ctx,
    # think, inline images and `format` schemas -- do not switch the local
    # provider to "openai" unless the model is served by llama.cpp.
    api_style: str = "ollama_native"
    api_key_env: str = ""
    models_url: str = ""
    models_refresh_hours: int = 24
    models_cache: str = "data/provider_models.json"
    prefer_zdr: bool = True
    keep_alive: str = "30m"
    request_timeout_s: float = 120.0


@dataclass(frozen=True)
class ModelsConfig:
    # role name -> model tag, used when that role resolves to a local provider
    local: Mapping[str, str | None] = field(
        default_factory=lambda: {
            "reflex": "qwen3.5:9b",
            "vision": None,              # None = same as reflex
            "classifier": None,          # None = same as reflex: one model in VRAM (D-052)
            "memory_writer": None,
            "embed": "nomic-embed-text",
            "mind": "qwen3.5:9b",
        }
    )
    # role name -> model id from the cloud provider's catalog
    cloud: Mapping[str, str] = field(
        default_factory=lambda: {
            "mind": "deepseek/deepseek-v4-flash",
            "mind_fallback": "alibaba/qwen-3-235b",
        }
    )

    def local_model(self, role: str, fallback: str = "qwen3.5:9b") -> str:
        return self.local.get(role) or fallback


@dataclass(frozen=True)
class RoleConfig:
    """A capability slot, not a model. `local_only` is enforced at load time:
    a non-local provider in a local-only role is a startup error."""

    chain: tuple[str, ...] = ()
    local_only: bool = True
    max_tokens: int | None = None
    temperature: float | None = None
    # API calls only: extra reply cap when the model may think (effort set, or the
    # catalog tags it a reasoner). Thinking is billed as output (D-058).
    reasoning_tokens: int | None = None


@dataclass(frozen=True)
class RoutingConfig:
    mode: str = "shadow"                 # "shadow" | "enforce"
    enforce_roles: tuple[str, ...] = ("mind",)
    escalate_when: Mapping[str, Any] = field(
        default_factory=lambda: {
            "task_steps_gte": 4,
            "tool_calls_gte": 2,
            "prompt_tokens_gte": 6000,
            "explicit_think_hard": True,
            "background_job": True,
        }
    )
    never_escalate: tuple[str, ...] = (
        "reflex",
        "vision",
        "classifier",
        "embed",
        "memory_writer",
    )
    untrusted_context_blocks_cloud: bool = True


@dataclass(frozen=True)
class PrivacyConfig:
    cloud_allowed_classes: tuple[str, ...] = ("public", "internal")
    local_only_classes: tuple[str, ...] = ("secret",)
    redaction: Mapping[str, Any] = field(
        default_factory=lambda: {
            "secrets": True,
            "file_paths": True,
            "emails": True,
            "long_digit_runs": True,
            "memory_excerpt_max_chars": 600,
            "transcript_max_chars": 1200,
        }
    )


@dataclass(frozen=True)
class BudgetConfig:
    enabled: bool = True
    hourly_usd: float = 0.25
    daily_usd: float = 1.50
    monthly_usd: float = 20.00
    on_exhausted: str = "local_only"
    prices: str = "from_provider"
    # SQLite ledger, so caps survive a restart. A cap of 0 means "never spend";
    # a negative cap means unlimited.
    ledger_path: str = "data/spend.db"


@dataclass(frozen=True)
class AuditConfig:
    path: str = "logs/audit.jsonl"
    log_prompts: bool = False
    log_responses: bool = False
    log_redaction_counts: bool = True


@dataclass(frozen=True)
class VoiceConfig:
    enabled: bool = True
    stt: Mapping[str, Any] = field(
        default_factory=lambda: {
            "engine": "faster_whisper",
            "model_size": "small",
            "device": "cpu",
            "compute_type": "int8",
            "language": "en",
            "timeout_s": 20,
        }
    )
    vad: Mapping[str, Any] = field(
        default_factory=lambda: {
            "engine": "silero_onnx",
            "speech_threshold": 0.5,
            "end_silence_ms": 500,
            "min_utterance_ms": 250,
            "max_utterance_ms": 30000,
            "pre_roll_ms": 200,
        }
    )
    barge_in: Mapping[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "min_speech_ms": 300,
            "stop_within_ms": 150,
            "aec": "browser",
            "fallback": "half_duplex",
        }
    )
    push_to_talk_key: str = "F9"
    mic: Mapping[str, Any] = field(
        default_factory=lambda: {"save_audio": False, "indicator": "tray"}
    )


@dataclass(frozen=True)
class SpeechConfig:
    """Deterministic speech-safe text (PHASE-2-FAST-PATH.md §1). The prompt
    asks; this module enforces."""

    enabled: bool = True
    max_segment_chars: int = 160
    min_segment_chars: int = 12
    code_blocks: str = "say_marker"      # "say_marker" | "skip"
    acronym_allowlist: tuple[str, ...] = (
        "AI", "API", "CPU", "CSS", "DLL", "FPS", "GPU", "HTML", "HTTP", "HTTPS",
        "IP", "JS", "JSON", "LLM", "ML", "NLP", "OCR", "OS", "PC", "RAM", "SQL",
        "SSD", "STT", "TV", "TTS", "URL", "USB", "VAD", "VPN", "VRAM", "VRM",
        "VRMA", "YAML",
    )


@dataclass(frozen=True)
class LatencyConfig:
    log: str = "logs/latency.jsonl"
    report_after_turns: int = 20
    targets_ms: Mapping[str, Any] = field(
        default_factory=lambda: {
            "stt": 700,
            "ttft": 400,
            "clause": 200,
            "tts": 900,
            "playback": 50,
            "total_p50": 1200,
            "total_p95": 1800,
            "inter_clause_gap": 300,
        }
    )


@dataclass(frozen=True)
class PersonaConfig:
    # Where the swappable persona will live (P5). The prompt is inline in
    # KASANE/persona.py today, so this may be empty.
    file: str = ""
    name: str = "Yuri"
    emotion_tag: str = "[emotion]"


@dataclass(frozen=True)
class LogsConfig:
    path: str = "logs/yuri.log"
    level: str = "info"
    rotate_mb: int = 20
    keep_files: int = 5


# ─── v1 views (the flat shape the older modules read) ────────────────────────


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3.5:9b"
    api_key: str = "ollama"
    temperature: float = 0.8
    max_tokens: int = 512
    api_style: str = "ollama_native"
    think: bool | None = False
    num_ctx: int | None = 8192
    vision_model: str | None = None
    warm_up_on_start: bool = True
    top_p: float | None = 0.95
    top_k: int | None = 20
    presence_penalty: float | None = 1.5


@dataclass(frozen=True)
class GPTSoVITSConfig:
    api_url: str = "http://127.0.0.1:9880/tts"
    ref_audio_path: str = ""
    prompt_text: str = ""
    prompt_lang: str = "en"
    text_lang: str = "en"
    media_type: str = "wav"
    prefetch_depth: int = 2
    first_clause_buffer_ms: int = 800
    # Where the server lives and how to start it. Yuri launches it; the user
    # never has to remember to start GPT-SoVITS first.
    launch: Mapping[str, Any] = field(
        default_factory=lambda: {
            # Off by default and no machine paths in code (R-40). Point `dir` at the
            # GPT-SoVITS install in config/config.yaml (gitignored); the kernel starts
            # it after the window is up and the chat model has loaded (D-060).
            "enabled": False,
            "dir": "",
            "python": "",
            "script": "",
            "cwd": "",
            "args": [
                "-a", "127.0.0.1", "-p", "9880",
                "-c", "GPT_SoVITS/configs/tts_infer.yaml",
            ],
            "startup_timeout_s": 120,
            "restart_max": 2,
        }
    )


@dataclass(frozen=True)
class TTSConfig:
    engine: str = "gpt_sovits"
    stream: str = "per_clause"           # "per_clause" | "off"
    # "none" (default): if the voice backend is down, the reply stays text-only. "pyttsx3"
    # opts in to the robotic placeholder voice (it breaks voice identity, FR-V-7).
    fallback_engine: str = "none"
    gpt_sovits: GPTSoVITSConfig = field(default_factory=GPTSoVITSConfig)


@dataclass(frozen=True)
class STTConfig:
    model_size: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str | None = "en"
    timeout_s: int = 20
    # Load the model at boot (after the chat model and the voice server) so the first
    # voice turn doesn't pay for it. Off by default: the mic arrives with K2 (D-060).
    warm_up_on_start: bool = False


@dataclass(frozen=True)
class SessionConfig:
    max_history_turns: int = 20
    user_name: str = "Yatharth"
    max_unprompted_in_history: int = 3


@dataclass(frozen=True)
class EmbeddingConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "nomic-embed-text"
    dimension: int = 768


@dataclass(frozen=True)
class MemoryConfig:
    db_path: str = "data/memory.db"
    recall_top_k: int = 5
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    writer: Mapping[str, Any] = field(
        default_factory=lambda: {
            "on_session_end": True,
            "interval_s": 600,
            "max_tokens": 800,
            "window_tokens": 2500,
            "busy_retry_s": 30,
        }
    )
    decay: Mapping[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "half_life_days": 30,
            "fact_half_life_days": 180,
            "compress_below": 0.15,
            "compress_batch": 10,
            "drop_below": 0.05,
            "drop_after_days": 90,
        }
    )
    recall: Mapping[str, Any] = field(
        default_factory=lambda: {
            "reflex": {"tokens": 300, "facts": 3, "episodes": 2},
            "mind": {"tokens": 1200, "facts": 8, "episodes": 5},
            "fact_similarity_floor": 0.45,
            "episode_similarity_floor": 0.30,
        }
    )
    contradiction: Mapping[str, Any] = field(
        default_factory=lambda: {"candidates": 5, "model_similarity_floor": 0.55}
    )
    profile_card: Mapping[str, Any] = field(default_factory=lambda: {"max_chars": 800})


@dataclass(frozen=True)
class TaskGuideConfig:
    capture_interval_seconds: int = 90
    idle_timeout_seconds: int = 1800
    model_can_start_tasks: bool = False


@dataclass(frozen=True)
class OCRWatchConfig:
    comment_interval_seconds: int = 240
    min_comment_gap_seconds: int = 120
    same_screen_similarity: float = 0.6
    pause_during_task: bool = True


@dataclass(frozen=True)
class VisionConfig:
    ambient_max_long_edge: int = 1024
    look_max_long_edge: int = 1600
    jpeg_quality: int = 85


@dataclass(frozen=True)
class LlamaCppPreset:
    """One llama.cpp model the user can pick (`local:llamacpp/<id>`). Machine paths
    live only in the user's gitignored config/config.yaml."""

    id: str = ""
    label: str = ""
    model_path: str = ""
    n_cpu_moe: int | None = None       # MoE expert layers kept in system RAM
    gpu_layers: int = 99
    ctx: int = 8192
    threads: int | None = None
    flash_attn: str = "on"
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class LlamaCppConfig:
    """The llama.cpp backend (K1-01, D-051). `server_path` empty = use the
    llama-server that ships inside Ollama, if present (development)."""

    server_path: str = ""
    host: str = "127.0.0.1"
    port: int = 8080
    startup_timeout_s: float = 600.0
    request_timeout_s: float = 600.0
    presets: tuple[LlamaCppPreset, ...] = ()

    def preset(self, preset_id: str) -> LlamaCppPreset | None:
        return next((p for p in self.presets if p.id == preset_id), None)


@dataclass(frozen=True)
class ChatConfig:
    """The conversation (`chat` role). `default_model_ref` is used by threads
    that have no model chosen; null = the local Ollama model in `llm.model`."""

    default_model_ref: str | None = None
    default_effort: str | None = None
    # Opening a thread whose model is not loaded starts loading it after this
    # pause, so clicking through old threads does not start a load per click
    # (K1-10, D-054). Picking a model in the chip loads at once.
    load_delay_s: float = 1.5


@dataclass(frozen=True)
class Config:
    # v2 surface
    providers: Mapping[str, ProviderConfig] = field(default_factory=dict)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    roles: Mapping[str, RoleConfig] = field(default_factory=dict)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    latency: LatencyConfig = field(default_factory=LatencyConfig)
    persona: PersonaConfig = field(default_factory=PersonaConfig)
    logs: LogsConfig = field(default_factory=LogsConfig)
    llamacpp: LlamaCppConfig = field(default_factory=LlamaCppConfig)
    chat: ChatConfig = field(default_factory=ChatConfig)

    # v1 views, derived -- the ported modules read these unchanged
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    task_guide: TaskGuideConfig = field(default_factory=TaskGuideConfig)
    ocr_watch: OCRWatchConfig = field(default_factory=OCRWatchConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)

    # where this config came from ("<defaults>" when no file was found)
    source_path: str = "<defaults>"
    # non-fatal problems found while loading (missing key, unusable provider)
    warnings: tuple[str, ...] = ()


# ─── secrets ─────────────────────────────────────────────────────────────────


def _read_dotenv(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def resolve_api_key(
    api_key_env: str,
    *,
    provider: str | None = None,
    secrets_path: pathlib.Path | None = None,
    dotenv_path: pathlib.Path | None = None,
) -> str | None:
    """The key for a provider, or None. Never guesses, never defaults to a
    placeholder that would silently 401.

    Order: the key saved in the app (handed over by the shell, FR-R-6). Then, in a
    developer checkout only: environment variable, `secrets.local.yaml`, `.env`."""
    app_key = shell_keys.get(provider)
    if app_key:
        return app_key
    if paths.is_packaged() or not api_key_env:
        return None   # FR-R-6: .env and secrets.local.yaml are developer-only
    key = _developer_key(api_key_env, provider, secrets_path, dotenv_path)
    if key is not None and not shell_keys.valid_key(key):
        # A space or control character would put the key into an HTTP error message.
        print(f"[kokyu] config: the developer key for {api_key_env} has spaces or odd characters; ignored", file=sys.stderr)
        return None
    return key


def _developer_key(
    api_key_env: str,
    provider: str | None,
    secrets_path: pathlib.Path | None,
    dotenv_path: pathlib.Path | None,
) -> str | None:
    value = os.environ.get(api_key_env)
    if value and value.strip():
        return value.strip()

    try:
        file = secrets_path or paths.secrets_path()
        secrets = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        secrets = {}
    if not isinstance(secrets, Mapping):
        secrets = {}

    # Two accepted layouts: {"airouter": {"api_key": ...}} and a flat map. With a
    # provider, only its own section: never hand one provider's key to another host.
    sections = [secrets.get(provider)] if provider else list(secrets.values())
    for section in sections:
        if isinstance(section, Mapping):
            for key_name in (api_key_env, "api_key", "key"):
                candidate = section.get(key_name)
                if candidate:
                    return str(candidate).strip()
    flat = secrets.get(api_key_env) or (None if provider else secrets.get("api_key"))
    if flat:
        return str(flat).strip()

    return _read_dotenv(dotenv_path or paths.dotenv_path()).get(api_key_env)


# ─── loading ─────────────────────────────────────────────────────────────────


def _find_config_path() -> pathlib.Path | None:
    for candidate in _SEARCH_PATHS:
        if candidate.is_file():
            return candidate
    return None


def _normalize_providers(
    raw: Mapping[str, Any], llm_raw: Mapping[str, Any], warnings: list[str] | None = None
) -> dict[str, ProviderConfig]:
    providers_raw = _section(raw, "providers")
    local_raw = dict(providers_raw.get("local_ollama") or {})
    airouter_raw = dict(providers_raw.get("airouter") or {})

    # Legacy files carry the local endpoint inline in `llm:`.
    for target, key in (
        (local_raw, "base_url"),
        (local_raw, "api_style"),
        (local_raw, "request_timeout_s"),
    ):
        if key not in target and key in llm_raw:
            target[key] = llm_raw[key]
    if "keep_alive" not in local_raw:
        local_raw["keep_alive"] = "30m"

    local = _build(ProviderConfig, {**local_raw, "name": "local_ollama"})
    # The one API slot keeps its old name so existing configs and role chains still
    # load (D-059); `preset` says which endpoint it is.
    notes = warnings if warnings is not None else []
    preset = str(airouter_raw.get("preset") or "airouter")
    known = API_PRESETS.get(preset)
    if known is not None:
        # A preset fixes where its key goes: a URL left from another preset (say, only
        # `preset:` changed in a copied config) must never receive this key.
        for name in ENDPOINT_FIELDS:
            if name in airouter_raw and airouter_raw[name] != known[name]:
                notes.append(
                    f"providers.airouter.{name} is ignored with preset '{preset}'; "
                    "give your own id to use another endpoint."
                )
        fields = {**airouter_raw, **{name: known[name] for name in ENDPOINT_FIELDS}}
    else:
        fields = {"label": "Custom", "price_unit": "none", "models_cache": f"data/{preset}_models.json", **airouter_raw}
        if not PROVIDER_ID.match(preset):
            notes.append(
                f"providers.airouter.preset '{preset}' is not a valid id (a lower-case letter, then "
                "a-z, 0-9 or _; at most 32). API models are off."
            )
            fields = {**fields, "enabled": False, "models_cache": "data/custom_models.json"}
    airouter = _build(ProviderConfig, {**fields, "name": "airouter", "preset": preset})
    if not airouter.models_url and airouter.base_url:
        airouter = dataclasses.replace(airouter, models_url=airouter.base_url.rstrip("/") + "/models")
    return {"local_ollama": local, "airouter": airouter}


def active_api_id(slot: ProviderConfig | None) -> str:
    """Which endpoint the API slot uses (D-059): the provider of the key saved in the
    app, when it names an endpoint this config knows; else the slot's own preset.
    A key left for an endpoint that is gone is ignored, never sent elsewhere."""
    app = shell_keys.app_provider()
    if slot is None:
        return app or "airouter"
    if app and api_endpoint(slot, app) is not None:
        return app
    return slot.preset or "airouter"


def api_endpoint(slot: ProviderConfig, provider_id: str) -> ProviderConfig | None:
    """The API slot pointed at `provider_id`: the configured endpoint itself, or a
    known preset with the slot's other settings. None for an unknown id."""
    if provider_id == slot.preset:
        return slot
    preset = API_PRESETS.get(provider_id)
    if preset is None:
        return None
    return dataclasses.replace(slot, preset=provider_id, **{k: preset[k] for k in ENDPOINT_FIELDS})


def _normalize_models(raw: Mapping[str, Any], llm_raw: Mapping[str, Any]) -> ModelsConfig:
    models_raw = _section(raw, "models")
    local = dict(models_raw.get("local") or {})
    cloud = dict(models_raw.get("cloud") or {})

    # Legacy: llm.model / llm.vision_model are the only model names in the file.
    legacy_model = llm_raw.get("model")
    if legacy_model and not models_raw:
        local.setdefault("reflex", legacy_model)
        local.setdefault("mind", legacy_model)
    if "vision_model" in llm_raw and "vision" not in local:
        local["vision"] = llm_raw.get("vision_model")

    defaults = ModelsConfig()
    merged_local = {**defaults.local, **{k: v for k, v in local.items() if v is not None}}
    # An explicit null is meaningful for these: "same as reflex" (D-052).
    for role in ("vision", "classifier", "memory_writer"):
        if local.get(role, "unset") is None:
            merged_local[role] = None
    return ModelsConfig(local=merged_local, cloud={**defaults.cloud, **{k: v for k, v in cloud.items() if v}})


def _normalize_roles(raw: Mapping[str, Any], never_escalate: tuple[str, ...]) -> dict[str, RoleConfig]:
    roles_raw = _section(raw, "roles")
    defaults = {
        "reflex": RoleConfig(chain=("local_ollama",), local_only=True, max_tokens=220),
        "vision": RoleConfig(chain=("local_ollama",), local_only=True, max_tokens=400),
        "classifier": RoleConfig(chain=("local_ollama",), local_only=True, max_tokens=300),
        "embed": RoleConfig(chain=("local_ollama",), local_only=True),
        "memory_writer": RoleConfig(chain=("local_ollama",), local_only=True, max_tokens=800),
        "mind": RoleConfig(chain=("airouter", "local_ollama"), local_only=False, max_tokens=2000, reasoning_tokens=6000),
        # K1-00c (D-025): the conversation itself, on the thread's chosen model.
        # The chain only names the providers a user may pick; there is no fallback.
        "chat": RoleConfig(chain=("airouter", "local_ollama"), local_only=False, max_tokens=1200, reasoning_tokens=6000),
    }
    out: dict[str, RoleConfig] = {}
    for name, default in defaults.items():
        section = roles_raw.get(name)
        if not isinstance(section, Mapping):
            out[name] = default
            continue
        data = dict(section)
        if "chain" in data:
            data["chain"] = _list(data["chain"], default.chain)
        if name in never_escalate:
            data["local_only"] = True     # the deny-list wins over the chain
        out[name] = _build(RoleConfig, {**dataclasses.asdict(default), **data})
    # Roles declared only in the config file (future roles) pass through.
    for name, section in roles_raw.items():
        if name in out or not isinstance(section, Mapping):
            continue
        data = dict(section)
        data["chain"] = _list(data.get("chain"), ("local_ollama",))
        out[name] = _build(RoleConfig, data)
    return out


def _validate_roles(roles: Mapping[str, RoleConfig]) -> None:
    for name, role in roles.items():
        if not role.local_only:
            continue
        remote = [p for p in role.chain if p not in LOCAL_PROVIDERS]
        if remote:
            raise ValueError(
                f"role '{name}' is local_only but its chain contains {remote}. "
                "A local-only role may only use local providers (config/ROUTING.md D-006)."
            )


def _derive_llm(
    raw: Mapping[str, Any],
    providers: Mapping[str, ProviderConfig],
    models: ModelsConfig,
) -> LLMConfig:
    llm_raw = _section(raw, "llm")
    local = providers["local_ollama"]
    defaults = LLMConfig()

    data = {
        "base_url": llm_raw.get("base_url") or local.base_url or defaults.base_url,
        "model": llm_raw.get("model") or models.local_model("reflex", defaults.model),
        "api_style": llm_raw.get("api_style") or local.api_style or defaults.api_style,
        "api_key": llm_raw.get("api_key") or "ollama",
        "temperature": llm_raw.get("temperature", defaults.temperature),
        "max_tokens": llm_raw.get("max_tokens", defaults.max_tokens),
        "think": llm_raw.get("think", defaults.think),
        "num_ctx": llm_raw.get("num_ctx", defaults.num_ctx),
        "vision_model": llm_raw.get("vision_model", models.local.get("vision")),
        "warm_up_on_start": llm_raw.get("warm_up_on_start", defaults.warm_up_on_start),
        "top_p": llm_raw.get("top_p", defaults.top_p),
        "top_k": llm_raw.get("top_k", defaults.top_k),
        "presence_penalty": llm_raw.get("presence_penalty", defaults.presence_penalty),
    }
    return _build(LLMConfig, data)


def _derive_tts(raw: Mapping[str, Any]) -> TTSConfig:
    tts_raw = _section(raw, "tts")
    sovits = dict(tts_raw.get("gpt_sovits") or {})
    defaults = TTSConfig()
    return TTSConfig(
        engine=tts_raw.get("engine", defaults.engine),
        stream=tts_raw.get("stream", defaults.stream),
        fallback_engine=tts_raw.get("fallback_engine", defaults.fallback_engine),
        gpt_sovits=_build(GPTSoVITSConfig, {**dataclasses.asdict(defaults.gpt_sovits), **sovits}),
    )


def _derive_stt(raw: Mapping[str, Any], voice: VoiceConfig) -> STTConfig:
    # Legacy configs have a top-level `stt:`; v2 nests it under `voice.stt`.
    stt_raw = _section(raw, "stt") or dict(voice.stt)
    return _build(STTConfig, stt_raw)


def _derive_memory(
    raw: Mapping[str, Any],
    providers: Mapping[str, ProviderConfig],
    models: ModelsConfig,
) -> MemoryConfig:
    memory_raw = dict(_section(raw, "memory"))
    embedding = dict(memory_raw.get("embedding") or {})
    default_embed = EmbeddingConfig(
        base_url=providers["local_ollama"].base_url,
        model=models.local_model("embed", "nomic-embed-text"),
    )
    memory_raw["embedding"] = _build(
        EmbeddingConfig, {**dataclasses.asdict(default_embed), **embedding}
    )
    return _build(MemoryConfig, memory_raw)


def _derive_llamacpp(raw: Mapping[str, Any]) -> LlamaCppConfig:
    section = _section(raw, "llamacpp")
    presets = []
    for item in section.get("presets") or ():
        if not isinstance(item, Mapping) or not item.get("id") or not item.get("model_path"):
            continue
        data = dict(item)
        data["id"] = str(data["id"])
        data["model_path"] = str(paths.resolve(str(data["model_path"])))
        data["extra_args"] = tuple(str(a) for a in data.get("extra_args") or ())
        presets.append(_build(LlamaCppPreset, data))
    data = {k: v for k, v in section.items() if k != "presets"}
    return _build(LlamaCppConfig, {**data, "presets": tuple(presets)})


def load_config(path: pathlib.Path | str | None = None, *, quiet: bool = False) -> Config:
    """Load and normalize a config file. `path=None` uses the search order."""
    explicit = path is not None
    config_path = pathlib.Path(path) if explicit else _find_config_path()
    warnings: list[str] = []

    raw: dict[str, Any] = {}
    if config_path is not None:
        text = config_path.read_text(encoding="utf-8")
        try:
            loaded = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            # The single most likely cause: a Windows path inside a
            # double-quoted YAML string (\\U is an escape). Say so, because the
            # raw ScannerError is unhelpful.
            raise RuntimeError(
                f"{config_path} failed to parse as YAML: {exc}\n\n"
                "If this mentions an 'escape sequence' and you have a Windows "
                "path (like C:\\Users\\...), switch that value to single quotes "
                "('C:\\Users\\...') -- double-quoted YAML treats backslashes as "
                "escape codes."
            ) from exc
        if loaded is None:
            raw = {}
        elif not isinstance(loaded, Mapping):
            raise RuntimeError(f"{config_path} must contain a YAML mapping at the top level.")
        else:
            raw = dict(loaded)

    llm_raw = _section(raw, "llm")
    providers = _normalize_providers(raw, llm_raw, warnings)
    models = _normalize_models(raw, llm_raw)

    routing_raw = _section(raw, "routing")
    routing = _build(RoutingConfig, {
        "mode": routing_raw.get("mode", "shadow"),
        "enforce_roles": _list(routing_raw.get("enforce_roles"), ("mind",)),
        "escalate_when": {**RoutingConfig().escalate_when, **_section(routing_raw, "escalate_when")},
        "never_escalate": _list(routing_raw.get("never_escalate"), RoutingConfig().never_escalate),
        "untrusted_context_blocks_cloud": routing_raw.get(
            "untrusted_context_blocks_cloud", True
        ),
    })

    privacy_raw = _section(raw, "privacy")
    privacy = _build(PrivacyConfig, {
        "cloud_allowed_classes": _list(
            privacy_raw.get("cloud_allowed_classes"), PrivacyConfig().cloud_allowed_classes
        ),
        "local_only_classes": _list(
            privacy_raw.get("local_only_classes"), PrivacyConfig().local_only_classes
        ),
        "redaction": {**PrivacyConfig().redaction, **_section(privacy_raw, "redaction")},
    })

    roles = _normalize_roles(raw, routing.never_escalate)
    _validate_roles(roles)

    voice = _build(VoiceConfig, {
        "enabled": _section(raw, "voice").get("enabled", True),
        "stt": {**VoiceConfig().stt, **_section(_section(raw, "voice"), "stt")},
        "vad": {**VoiceConfig().vad, **_section(_section(raw, "voice"), "vad")},
        "barge_in": {**VoiceConfig().barge_in, **_section(_section(raw, "voice"), "barge_in")},
        "push_to_talk_key": _section(raw, "voice").get("push_to_talk_key", "F9"),
        "mic": {**VoiceConfig().mic, **_section(_section(raw, "voice"), "mic")},
    })

    speech_raw = _section(raw, "speech")
    speech = _build(SpeechConfig, {
        "enabled": speech_raw.get("enabled", True),
        "max_segment_chars": speech_raw.get("max_segment_chars", 160),
        "min_segment_chars": speech_raw.get("min_segment_chars", 12),
        "code_blocks": speech_raw.get("code_blocks", "say_marker"),
        "acronym_allowlist": _list(
            speech_raw.get("acronym_allowlist"), SpeechConfig().acronym_allowlist
        ),
    })

    latency_raw = _section(raw, "latency")
    latency = _build(LatencyConfig, {
        "log": latency_raw.get("log", "logs/latency.jsonl"),
        "report_after_turns": latency_raw.get("report_after_turns", 20),
        "targets_ms": {**LatencyConfig().targets_ms, **_section(latency_raw, "targets_ms")},
    })

    persona = _build(PersonaConfig, _section(raw, "persona"))
    logs = _build(LogsConfig, _section(raw, "logs"))
    budget = _build(BudgetConfig, _section(raw, "budget"))
    audit = _build(AuditConfig, _section(raw, "audit"))

    # A cloud provider that is switched on but has no key is a warning, not a
    # crash: Mind simply stays local. Never send an unauthenticated request.
    airouter = providers["airouter"]
    if airouter.enabled and not resolve_api_key(airouter.api_key_env, provider=active_api_id(airouter)):
        warnings.append(
            "providers.airouter.enabled is true but "
            f"{airouter.api_key_env or '<no api_key_env>'} did not resolve. "
            "Cloud is disabled for this run; Mind stays local."
        )

    llm = _derive_llm(raw, providers, models)
    cfg = Config(
        providers=providers,
        models=models,
        roles=roles,
        routing=routing,
        privacy=privacy,
        budget=budget,
        audit=audit,
        voice=voice,
        speech=speech,
        latency=latency,
        persona=persona,
        logs=logs,
        llamacpp=_derive_llamacpp(raw),
        chat=_build(ChatConfig, _section(raw, "chat")),
        llm=llm,
        tts=_derive_tts(raw),
        stt=_derive_stt(raw, voice),
        session=_build(SessionConfig, _section(raw, "session")),
        memory=_derive_memory(raw, providers, models),
        task_guide=_build(TaskGuideConfig, _section(raw, "task_guide")),
        ocr_watch=_build(OCRWatchConfig, _section(raw, "ocr_watch")),
        vision=_build(VisionConfig, _section(raw, "vision")),
        source_path=str(config_path) if config_path else "<defaults>",
        warnings=tuple(warnings),
    )

    if warnings and not (quiet or explicit):
        for warning in warnings:
            print(f"[yuri] config: {warning}", file=sys.stderr)

    return cfg


# Loaded once at import time. Restart to pick up edits (no hot reload -- not
# worth the complexity for a single-user local app).
CONFIG = load_config()


def print_summary(cfg: Config = CONFIG) -> str:
    """One-line-per-role view of what actually resolved. Used by
    `python -m orchestrator --check` and at startup."""
    lines = [f"config: {cfg.source_path}"]
    reflex_model = cfg.models.local_model("reflex")
    for name, role in cfg.roles.items():
        def model_for(provider: str) -> str | None:
            if provider == "airouter":
                return cfg.models.cloud.get(name)
            resolved = cfg.models.local.get(name)
            # vision: null means "the reflex model", not "no model"
            return resolved if resolved is not None else reflex_model

        chain = " -> ".join(f"{p}:{model_for(p)}" for p in role.chain)
        lines.append(f"  role {name:<14} {'local-only' if role.local_only else 'escalatable':<11} {chain}")
    lines.append(f"  routing mode: {cfg.routing.mode}; enforce: {', '.join(cfg.routing.enforce_roles) or '-'}")
    for warning in cfg.warnings:
        lines.append(f"  WARNING: {warning}")
    return "\n".join(lines)
