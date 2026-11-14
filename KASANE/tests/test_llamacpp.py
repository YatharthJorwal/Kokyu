"""llama.cpp backend (K1-01, D-051): presets, the server child, message conversion, streaming."""
from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path

import httpx
import pytest

import config
from config import LlamaCppConfig, LlamaCppPreset, load_config
from router import decision as d
from router import model_ref
from router.errors import ProviderError
from router.providers import llamacpp as lc
from router.types import ModelRequest

from test_decision import BUDGET, MODELS, PROVIDERS, state


def preset(tmp_path, **kw) -> LlamaCppPreset:
    model = tmp_path / "big.gguf"
    model.write_bytes(b"GGUF")
    return LlamaCppPreset(**{"id": "big", "model_path": str(model), "n_cpu_moe": 40, "threads": 6, **kw})


def test_presets_load_from_config_and_skip_incomplete_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path))
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "chat:\n  default_model_ref: 'local:llamacpp/big'\n  default_effort: 'off'\n"
        "llamacpp:\n  port: 8099\n  presets:\n"
        "    - {id: big, model_path: 'D:\\models\\big.gguf', n_cpu_moe: 40, extra_args: ['--mlock']}\n"
        "    - {id: no_path}\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_file, quiet=True)
    assert cfg.llamacpp.port == 8099 and [p.id for p in cfg.llamacpp.presets] == ["big"]
    big = cfg.llamacpp.preset("big")
    assert big.n_cpu_moe == 40 and big.extra_args == ("--mlock",) and big.model_path.endswith("big.gguf")
    assert cfg.chat.default_model_ref == "local:llamacpp/big" and cfg.chat.default_effort == "off"
    assert config.CONFIG.llamacpp.presets == () or isinstance(config.CONFIG.llamacpp.presets, tuple)


def test_a_llamacpp_ref_is_local_and_runs_even_with_ambient_content():
    ref = model_ref.parse("local:llamacpp/qwen3.6-35b-a3b")
    assert ref.provider == "llamacpp" and ref.is_local
    r = d.decide(
        role="chat", role_cfg=config.CONFIG.roles["chat"],
        request=ModelRequest(role="chat", model_ref=str(ref), ambient=True),
        routing=config.CONFIG.routing, budget=BUDGET, state=state(cloud_available=False),
        models=MODELS, providers=PROVIDERS, now=1000.0,
    )
    assert (r.reason, r.chosen, r.blocked) == (d.USER_SELECTED, "llamacpp:qwen3.6-35b-a3b", False)


def test_the_server_command_carries_the_preset(tmp_path):
    p = preset(tmp_path, extra_args=("--mlock",))
    cmd = lc.server_command(Path("llama-server.exe"), p, LlamaCppConfig(port=8090))
    joined = " ".join(cmd)
    assert "--n-cpu-moe 40" in joined and "--port 8090" in joined and "--jinja" in cmd
    assert "--alias big" in joined and "--threads 6" in joined and cmd[-1] == "--mlock"
    assert "--host 127.0.0.1" in joined                       # never listens beyond this PC


def test_ollamas_bundled_server_gets_its_cuda_folder(tmp_path):
    server = tmp_path / "llama-server.exe"
    server.write_bytes(b"")
    (tmp_path / "cuda_v12").mkdir()
    (tmp_path / "cuda_v12" / "ggml-cuda.dll").write_bytes(b"")
    env = lc.server_env(server, {"PATH": "C:\\Windows"})
    assert env["PATH"].startswith(str(tmp_path / "cuda_v12")) and env["GGML_BACKEND_PATH"].endswith("ggml-cuda.dll")
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "llama-server.exe").write_bytes(b"")
    assert lc.server_env(plain / "llama-server.exe", {"PATH": "x"}) == {"PATH": "x"}


def test_messages_are_converted_for_openai_style_templates():
    msgs = [
        {"role": "system", "content": "persona"},
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "recall: likes tea"},          # ephemeral, mid-history
        {"role": "user", "content": "what do I like?"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "remember", "arguments": {"q": "tea"}}}]},
        {"role": "tool", "content": "tea"},
    ]
    out = lc.openai_messages(msgs)
    assert [m["role"] for m in out].count("system") == 1 and out[0] == {"role": "system", "content": "persona"}
    # the per-turn note rides on the next user message, so the cached prefix stays the same
    assert out[1] == {"role": "user", "content": "hi"}
    assert out[2]["role"] == "user" and out[2]["content"].startswith("[Context for this message]\nrecall: likes tea")
    assert out[2]["content"].endswith("what do I like?")
    call = next(m for m in out if m.get("tool_calls"))["tool_calls"][0]
    assert call["type"] == "function" and json.loads(call["function"]["arguments"]) == {"q": "tea"}
    assert out[-1] == {"role": "tool", "content": "tea", "tool_call_id": call["id"]}


class FakeProcess:
    def __init__(self, exit_code=None, on_stop=None):
        self.returncode = exit_code
        self.terminated = False
        self._on_stop = on_stop

    def terminate(self):
        self.terminated = True
        self.returncode = 0
        if self._on_stop:
            self._on_stop()                     # the port closes with the process

    def kill(self):
        self.returncode = -9

    async def wait(self):
        return self.returncode


def transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_the_server_starts_once_unloads_ollama_and_restarts_for_another_preset(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    server_exe = tmp_path / "llama-server.exe"
    server_exe.write_bytes(b"")
    spawned, unloaded = [], []
    health = {"ok": False}

    async def spawn(*cmd, **kw):
        spawned.append(cmd)
        health["ok"] = True
        return FakeProcess(on_stop=lambda: health.update(ok=False))

    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200 if health["ok"] else 503)
        if request.url.path == "/api/ps":
            names = ["qwen3.5:9b", "qwen3.5:4b", "nomic-embed-text:latest"]
            return httpx.Response(200, json={"models": [{"name": n} for n in names]})
        if request.url.path == "/api/generate":
            unloaded.append(json.loads(request.content)["model"])
            return httpx.Response(200, json={})
        return httpx.Response(404)

    cfg = LlamaCppConfig(server_path=str(server_exe))
    keep = frozenset({"qwen3.5:4b", "nomic-embed-text"})       # the helpers stay loaded (D-052)
    server = lc.LlamaCppServer(
        cfg, spawn=spawn, transport=transport(handler), ollama_url="http://ollama", poll_s=0, keep_loaded=keep,
    )
    a = preset(tmp_path)
    await server.ensure(a)
    await server.ensure(a)                                   # already up: no second spawn
    assert len(spawned) == 1 and unloaded == ["qwen3.5:9b"] and server.preset_id == "big"
    first = server.process
    b = LlamaCppPreset(id="other", model_path=a.model_path)
    await server.ensure(b)
    assert first.terminated and len(spawned) == 2 and server.preset_id == "other"
    await server.stop()
    assert not server.running()


@pytest.mark.asyncio
async def test_missing_server_model_or_a_crash_are_clear_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    no_server = lc.LlamaCppServer(LlamaCppConfig(server_path=str(tmp_path / "nope.exe")))
    with pytest.raises(ProviderError, match="not installed"):
        await no_server.ensure(preset(tmp_path))

    exe = tmp_path / "llama-server.exe"
    exe.write_bytes(b"")
    cfg = LlamaCppConfig(server_path=str(exe))
    with pytest.raises(ProviderError, match="not found"):
        await lc.LlamaCppServer(cfg).ensure(LlamaCppPreset(id="x", model_path=str(tmp_path / "missing.gguf")))

    async def never(*cmd, **kw):
        raise AssertionError("must not spawn while the port is taken")

    taken = transport(lambda r: httpx.Response(200, json={}))       # someone else answers /health
    with pytest.raises(ProviderError, match="already serving"):
        await lc.LlamaCppServer(cfg, spawn=never, transport=taken, ollama_url="http://o", poll_s=0).ensure(preset(tmp_path))

    async def crashing(*cmd, **kw):
        return FakeProcess(exit_code=1)

    down = transport(lambda r: httpx.Response(503) if r.url.path == "/health" else httpx.Response(200, json={}))
    with pytest.raises(ProviderError, match="exited with code 1"):
        await lc.LlamaCppServer(cfg, spawn=crashing, transport=down, ollama_url="http://o", poll_s=0).ensure(preset(tmp_path))


@pytest.mark.asyncio
async def test_the_provider_streams_with_thinking_switched_by_effort(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    bodies = []

    up = {"ok": False}

    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200 if up["ok"] else 503)
        if request.url.path == "/v1/chat/completions":
            assert "authorization" not in request.headers     # no key, so no "Bearer " header (found live)
            bodies.append(json.loads(request.content))
            sse = (
                'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={})

    exe = tmp_path / "llama-server.exe"
    exe.write_bytes(b"")
    p = preset(tmp_path)
    cfg = LlamaCppConfig(server_path=str(exe), presets=(p,))

    async def spawn(*cmd, **kw):
        up["ok"] = True
        return FakeProcess(on_stop=lambda: up.update(ok=False))

    t = transport(handler)
    server = lc.LlamaCppServer(cfg, spawn=spawn, transport=t, ollama_url="http://o", poll_s=0)
    provider = lc.LlamaCppProvider(cfg, server, transport=t)
    base = dict(role="chat", messages=({"role": "system", "content": "s"}, {"role": "user", "content": "hi"}))
    text = "".join([c.text async for c in provider.complete(ModelRequest(**base, effort="high"), model="big") if c.kind == "content"])
    [c async for c in provider.complete(ModelRequest(**base), model="big")]
    assert text == "Hello"
    assert bodies[0]["chat_template_kwargs"] == {"enable_thinking": True}
    assert bodies[1]["chat_template_kwargs"] == {"enable_thinking": bool(config.CONFIG.llm.think)}
    assert "reasoning_effort" not in bodies[0]
    with pytest.raises(ProviderError, match="no llama.cpp preset"):
        [c async for c in provider.complete(ModelRequest(**base), model="unknown")]


def test_two_turns_share_the_same_prefix_so_the_server_cache_is_reused():
    turn1 = [
        {"role": "system", "content": "persona"},
        {"role": "user", "content": "a"},
        {"role": "system", "content": "recall one"},
        {"role": "user", "content": "b"},
    ]
    turn2 = [
        {"role": "system", "content": "persona"},
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
        {"role": "assistant", "content": "reply"},
        {"role": "system", "content": "recall two"},
        {"role": "user", "content": "c"},
    ]
    one, two = lc.openai_messages(turn1), lc.openai_messages(turn2)
    assert one[:2] == two[:2]                       # system prompt and first turn are byte-identical
    assert two[-1]["content"].startswith("[Context for this message]\nrecall two")


def test_the_helpers_kept_beside_llama_server_come_from_the_config(monkeypatch):
    models = dataclasses.replace(
        config.CONFIG.models, local={**config.CONFIG.models.local, "classifier": "small:2b", "memory_writer": None, "reflex": "big:9b"},
    )
    monkeypatch.setattr(lc, "CONFIG", dataclasses.replace(config.CONFIG, models=models))
    keep = lc.helper_models()
    assert {"small:2b", "big:9b"} <= keep                  # a null helper means "the reflex model", so that one stays
    assert config.CONFIG.memory.embedding.model in keep


def test_a_null_helper_model_means_the_reflex_model(tmp_path):
    from router.decision import LOCAL_PROVIDER, model_for

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "models:\n  local:\n    reflex: 'big:9b'\n    classifier: null\n    memory_writer: 'small:4b'\n", encoding="utf-8",
    )
    models = load_config(cfg_file, quiet=True).models
    assert model_for(LOCAL_PROVIDER, "classifier", models) == "big:9b"       # one model in VRAM on a 9B-only PC
    assert model_for(LOCAL_PROVIDER, "memory_writer", models) == "small:4b"


@pytest.mark.asyncio
async def test_a_cancelled_load_of_the_same_preset_is_waited_for_not_restarted(tmp_path, monkeypatch):
    # K1-10: the user picks the 35B, switches away before it is up, then back.
    # The half-loaded server keeps loading; starting a second one would cost the
    # whole load again.
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    server_exe = tmp_path / "llama-server.exe"
    server_exe.write_bytes(b"")
    spawned = []
    health = {"ok": False}

    async def spawn(*cmd, **kw):
        spawned.append(cmd)
        return FakeProcess(on_stop=lambda: health.update(ok=False))

    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200 if health["ok"] else 503)
        return httpx.Response(200, json={"models": []})

    server = lc.LlamaCppServer(
        LlamaCppConfig(server_path=str(server_exe)), spawn=spawn, transport=transport(handler),
        ollama_url="http://ollama", poll_s=0.01, keep_loaded=frozenset(),
    )
    a = preset(tmp_path)
    first = asyncio.create_task(server.ensure(a))
    await asyncio.sleep(0.05)
    first.cancel()                                           # the warm-up was cancelled mid-load
    with pytest.raises(asyncio.CancelledError):
        await first
    assert server.running() and server.preset_id == "big"    # still loading in the background
    second = asyncio.create_task(server.ensure(a))
    await asyncio.sleep(0.05)
    health["ok"] = True                                      # the model finished loading
    await asyncio.wait_for(second, timeout=2)
    assert len(spawned) == 1
    await server.stop()
