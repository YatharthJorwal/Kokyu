"""llama.cpp provider and server manager (K1-01, D-051).

A `local:llamacpp/<preset>` model runs in a `llama-server` child process that
the kernel starts on first use and keeps running until a different preset is
needed or the kernel shuts down. Large MoE models keep their expert weights in
system RAM (`--n-cpu-moe`), so the GPU holds only the shared layers.

The wire format is OpenAI-compatible, so streaming and tool-call parsing reuse
`AirouterProvider`. What differs: messages are converted from the kernel's
Ollama shape (system turns folded to the front, tool calls with ids and JSON
string arguments), and thinking is switched with `chat_template_kwargs`.

Never blocks the event loop: the process is spawned with asyncio and the
health check is an async HTTP poll.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any, AsyncIterator, Callable

import httpx

import llm
import paths
from config import CONFIG, LlamaCppConfig, LlamaCppPreset, ProviderConfig
from router import capabilities
from router.errors import ProviderError
from router.providers import airouter
from router.providers.airouter import AirouterProvider
from router.types import ModelChunk, ModelRequest

LOG_NAME = "llama-server.log"


def ollama_bundled_server() -> Path | None:
    """The llama-server that ships inside Ollama (development convenience, D-051)."""
    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Ollama" / "lib" / "ollama" / "llama-server.exe")
    ollama = shutil.which("ollama")
    if ollama:
        candidates.append(Path(ollama).resolve().parent / "lib" / "ollama" / "llama-server.exe")
    return next((c for c in candidates if c.is_file()), None)


def resolve_server(cfg: LlamaCppConfig) -> Path | None:
    if cfg.server_path:
        path = Path(cfg.server_path)
        return path if path.is_file() else None
    found = shutil.which("llama-server")
    return Path(found) if found else ollama_bundled_server()


def server_env(server: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    """Ollama's copy keeps its CUDA backend in a subfolder that ggml does not
    search on its own; point it there. A plain llama.cpp release needs nothing."""
    env = dict(os.environ if base is None else base)
    cuda = server.parent / "cuda_v12"
    if (cuda / "ggml-cuda.dll").is_file():
        env["PATH"] = os.pathsep.join([str(cuda), str(server.parent), env.get("PATH", "")])
        env.setdefault("GGML_BACKEND_PATH", str(cuda / "ggml-cuda.dll"))
    return env


def server_command(server: Path, preset: LlamaCppPreset, cfg: LlamaCppConfig) -> list[str]:
    cmd = [
        str(server),
        "-m", preset.model_path,
        "--host", cfg.host,
        "--port", str(cfg.port),
        "-ngl", str(preset.gpu_layers),
        "-c", str(preset.ctx),
        "-fa", preset.flash_attn,
        "--jinja",
        "--no-webui",
        "--alias", preset.id,
    ]
    if preset.n_cpu_moe is not None:
        cmd += ["--n-cpu-moe", str(preset.n_cpu_moe)]
    if preset.threads:
        cmd += ["--threads", str(preset.threads)]
    cmd += list(preset.extra_args)
    return cmd


def cache_friendly(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Moves per-turn system notes (recall, hints, scene) out of the system prompt.

    Qwen templates reject a system turn anywhere but first, and folding the
    per-turn notes into the first one (as the Ollama path does) changes the very
    start of the prompt every turn, so llama-server can never reuse its cached
    prefix and re-reads the whole conversation (about 30 s for 2,000 tokens with
    experts on the CPU, K1-01). Instead the leading system prompt stays as it is
    and each later system note is prepended to the next user message."""
    out: list[dict[str, Any]] = []
    pending: list[str] = []
    for index, message in enumerate(messages):
        if message.get("role") == "system" and index > 0 and out:
            if message.get("content"):
                pending.append(str(message["content"]))
            continue
        if message.get("role") == "user" and pending:
            notes = "\n".join(pending)
            message = {**message, "content": f"[Context for this message]\n{notes}\n\n{message.get('content') or ''}"}
            pending = []
        out.append(dict(message))
    if pending:                                  # notes after the last user turn
        out.append({"role": "user", "content": "[Context]\n" + "\n".join(pending)})
    return llm.fold_system_messages(out)        # only a leading system turn remains


def openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kernel (Ollama-shaped) messages -> OpenAI chat messages for llama-server:
    one system turn, first (see `cache_friendly`), tool calls in OpenAI shape."""
    return airouter.openai_messages(cache_friendly([dict(m) for m in messages]))


def _bare(name: str) -> str:
    return name[: -len(":latest")] if name.endswith(":latest") else name


def helper_models() -> frozenset[str]:
    """Ollama models the kernel itself uses beside the chat model (classifier,
    memory writer, embeddings). They are small and stay loaded next to a MoE
    whose experts live in system RAM (D-052)."""
    from router.decision import LOCAL_PROVIDER, model_for

    names = {model_for(LOCAL_PROVIDER, role, CONFIG.models) for role in ("classifier", "memory_writer", "embed")}
    names.add(CONFIG.memory.embedding.model)
    return frozenset(_bare(n) for n in names if n)


async def unload_ollama(
    base_url: str, *, keep: frozenset[str] = frozenset(), transport: httpx.AsyncBaseTransport | None = None
) -> list[str]:
    """Ask Ollama to drop its loaded models (keep_alive 0) so the GPU is free
    for llama-server, except the helpers in `keep`. Best effort: an Ollama that
    is not running is fine."""
    unloaded: list[str] = []
    try:
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
            ps = await client.get(f"{base_url.rstrip('/')}/api/ps")
            for model in (ps.json() or {}).get("models") or []:
                name = model.get("name") or model.get("model")
                if not name or _bare(name) in keep:
                    continue
                await client.post(f"{base_url.rstrip('/')}/api/generate", json={"model": name, "keep_alive": 0})
                unloaded.append(name)
    except (httpx.HTTPError, ValueError):
        pass
    return unloaded


class LlamaCppServer:
    """Owns one llama-server child. `ensure(preset)` returns once it is healthy."""

    def __init__(
        self,
        cfg: LlamaCppConfig,
        *,
        spawn: Callable[..., Any] = asyncio.create_subprocess_exec,
        transport: httpx.AsyncBaseTransport | None = None,
        ollama_url: str | None = None,
        poll_s: float = 1.0,
        keep_loaded: frozenset[str] | None = None,
    ) -> None:
        self.cfg = cfg
        self._keep = helper_models() if keep_loaded is None else keep_loaded
        self._spawn = spawn
        self._transport = transport
        self._ollama_url = ollama_url or CONFIG.llm.base_url
        self._poll_s = poll_s
        self._lock = asyncio.Lock()
        self.process: Any = None
        self.preset_id: str | None = None
        # Set while a started server is still loading its model; None once ready.
        self._deadline: float | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.cfg.host}:{self.cfg.port}"

    def running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def _healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def ensure(self, preset: LlamaCppPreset) -> None:
        async with self._lock:
            if self.running() and self.preset_id == preset.id:
                if await self._healthy():
                    return
                if self._deadline is not None:
                    # Started earlier and still loading: a cancelled warm-up (the
                    # user switched away and back, K1-10) left it running. Keep
                    # waiting for it instead of paying for the load twice.
                    await self._wait_ready_locked(preset)
                    return
            await self._stop_locked()
            server = resolve_server(self.cfg)
            if server is None:
                raise ProviderError(
                    "llama.cpp is not installed: set llamacpp.server_path in config.yaml "
                    "(or install Ollama, which bundles llama-server)."
                )
            if not Path(preset.model_path).is_file():
                raise ProviderError(f"model file for {preset.id!r} not found: {preset.model_path}")
            if await self._healthy():
                # Not ours (we just stopped ours): most likely a llama-server left
                # behind by a kernel that was killed instead of quit. Talking to it
                # would answer with whatever model it has loaded.
                raise ProviderError(
                    f"another program is already serving on {self.base_url} (often a leftover "
                    "llama-server.exe from a crash: end it in Task Manager), or change llamacpp.port."
                )
            await unload_ollama(self._ollama_url, keep=self._keep, transport=self._transport)
            log_path = paths.logs_dir() / LOG_NAME
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log = open(log_path, "ab")  # noqa: SIM115 -- handed to the child, closed in _stop_locked
            try:
                self.process = await self._spawn(
                    *server_command(server, preset, self.cfg),
                    env=server_env(server),
                    stdin=asyncio.subprocess.DEVNULL,   # the kernel's stdin carries API keys (D-059)
                    stdout=log,
                    stderr=asyncio.subprocess.STDOUT,
                )
            except OSError as exc:
                log.close()
                raise ProviderError(f"could not start llama-server: {exc}") from exc
            self._log = log
            self.preset_id = preset.id
            self._deadline = asyncio.get_running_loop().time() + self.cfg.startup_timeout_s
            await self._wait_ready_locked(preset)

    async def _wait_ready_locked(self, preset: LlamaCppPreset) -> None:
        loop = asyncio.get_running_loop()
        while not await self._healthy():
            if self.process is None or self.process.returncode is not None:
                code = self.process.returncode if self.process is not None else None
                await self._stop_locked()
                raise ProviderError(f"llama-server exited with code {code} while loading {preset.id}; see logs/{LOG_NAME}")
            if self._deadline is not None and loop.time() > self._deadline:
                await self._stop_locked()
                raise ProviderError(f"llama-server did not become ready within {self.cfg.startup_timeout_s:.0f} s")
            await asyncio.sleep(self._poll_s)
        self._deadline = None

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_locked()

    async def _stop_locked(self) -> None:
        proc, self.process, self.preset_id = self.process, None, None
        self._deadline = None
        if proc is not None and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=20)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        log = getattr(self, "_log", None)
        if log is not None:
            log.close()
            self._log = None


class LlamaCppProvider(AirouterProvider):
    name = "llamacpp"
    paid = False   # local: no bill to estimate, and warm() asks for one token and says nothing

    def __init__(
        self,
        cfg: LlamaCppConfig,
        server: LlamaCppServer | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.server = server or LlamaCppServer(cfg, transport=transport)
        provider_cfg = ProviderConfig(
            name="llamacpp",
            base_url=f"{self.server.base_url}/v1",
            api_style="openai",
            request_timeout_s=cfg.request_timeout_s,
        )
        super().__init__(provider_cfg, None, transport=transport)
        self.llama_cfg = cfg

    def _payload(self, request: ModelRequest, model: str) -> dict[str, Any]:
        payload = super()._payload(request, model)
        payload["messages"] = openai_messages(list(request.messages))
        payload.pop("reasoning_effort", None)
        payload.pop("stream_options", None)
        think = capabilities.think_for(f"local:llamacpp/{model}", request.effort)   # FR-M-10
        if think is None:
            think = CONFIG.llm.think
        payload["chat_template_kwargs"] = {"enable_thinking": bool(think)}
        return payload

    async def complete(self, request: ModelRequest, *, model: str) -> AsyncIterator[ModelChunk]:
        preset = self.llama_cfg.preset(model)
        if preset is None:
            raise ProviderError(f"no llama.cpp preset called {model!r} in config.yaml")
        await self.server.ensure(preset)
        async for chunk in super().complete(request, model=model):
            yield chunk

    async def health(self) -> bool:
        return self.server.running()
