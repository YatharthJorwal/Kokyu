"""Chat memory (D-098): a context length per model, set in the picker and kept in
settings.json. Every Ollama request for the model and the history budget use it; a
llama.cpp preset runs with it; each row says how far it goes and where it stops
fitting in graphics memory. Fakes only: no request reaches the user's Ollama."""
from __future__ import annotations

import dataclasses
import inspect
import json
import struct
from types import SimpleNamespace

import httpx
import pytest

import config
import context_fit
import hub
import llm
import model_loader
import protocol
import settings_file
import turns
import vram
from router import listing

GIB = 1024**3
QWEN = "local:ollama/qwen3.5:9b"
INFO = {
    "general.architecture": "qwen3",
    "qwen3.block_count": 36,
    "qwen3.attention.head_count": 32,
    "qwen3.attention.head_count_kv": 8,
    "qwen3.attention.key_length": 128,
    "qwen3.attention.value_length": 128,
    "qwen3.context_length": 262144,
}


def set_memory(**by_model):
    cfg = config.CONFIG
    config.install(dataclasses.replace(cfg, llm=dataclasses.replace(cfg.llm, context_by_model=dict(by_model))))


@pytest.fixture(autouse=True)
def _restore_config():
    original = config.CONFIG
    yield
    config.install(original)


def test_the_model_s_setting_wins_else_the_usual_context():
    set_memory(**{QWEN: 32768})
    assert context_fit.context_for(QWEN) == 32768
    assert context_fit.context_for("local:ollama/qwen3.5:4b") == config.CONFIG.llm.num_ctx
    assert context_fit.context_for(None) == config.CONFIG.llm.num_ctx


def test_every_ollama_request_for_a_model_sends_its_chat_memory():
    set_memory(**{QWEN: 32768})
    assert llm._ollama_options("qwen3.5:9b")["num_ctx"] == 32768
    assert llm._ollama_options("qwen3.5:4b")["num_ctx"] == config.CONFIG.llm.num_ctx
    # one value per model, or Ollama reloads it: no request may build options without its model
    source = inspect.getsource(llm)
    assert source.count("_ollama_options(") >= 6
    assert "_ollama_options()" not in source and "_ollama_options(**" not in source


@pytest.mark.asyncio
async def test_the_history_budget_follows_the_model_s_chat_memory(monkeypatch):
    seen = []
    original = turns.fit_for_llm

    def spy(messages, tools_list=None, extra=None, num_ctx=...):
        seen.append(num_ctx)
        return original(messages, tools_list, extra, num_ctx=num_ctx)

    async def fake_stream(role, messages, tools, **kwargs):
        yield {"type": "content", "text": "Fine. [neutral]"}

    async def nothing(*a, **k):
        return None

    monkeypatch.setattr(turns, "fit_for_llm", spy)
    monkeypatch.setattr(turns.router, "stream_with_tools", fake_stream)
    monkeypatch.setattr(turns, "log_transcript_turn", nothing)
    set_memory(**{QWEN: 65536})
    ws = SimpleNamespace(state=SimpleNamespace(waifu=None), send_json=nothing)
    await turns.run_turn(ws, [{"role": "system", "content": "sys"}], "hi", True, [], model_ref=QWEN)
    assert seen == [65536]


def test_the_budget_trims_to_the_given_context():
    long = [{"role": "system", "content": "sys"}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": "word " * 400} for i in range(40)
    ] + [{"role": "user", "content": "now"}]
    small = turns.fit_for_llm(long, num_ctx=8192)
    large = turns.fit_for_llm(long, num_ctx=65536)
    assert len(small) < len(large) == len(long)


def test_a_change_is_kept_in_settings_json_and_none_goes_back():
    saved = settings_file.change({}, {"context": {"ref": QWEN, "tokens": 32768}})
    assert saved == {"llm": {"context_by_model": {QWEN: 32768}}}
    saved = settings_file.change(saved, {"context": {"ref": "local:llamacpp/big", "tokens": 16384}})
    assert saved["llm"]["context_by_model"] == {QWEN: 32768, "local:llamacpp/big": 16384}
    saved = settings_file.change(saved, {"context": {"ref": QWEN, "tokens": None}})
    assert saved == {"llm": {"context_by_model": {"local:llamacpp/big": 16384}}}
    assert settings_file.change(saved, {"context": {"ref": "local:llamacpp/big", "tokens": None}}) == {}
    with pytest.raises(settings_file.SettingsError):
        settings_file.change({}, {"context": {"ref": "", "tokens": 8192}})


def test_the_protocol_bounds_a_context():
    ok = protocol.parse_client({"v": 1, "type": "set_context", "data": {"ref": QWEN, "tokens": 32768}})
    assert ok.data.tokens == 32768
    for tokens in (512, 64 * 1024 * 1024):
        with pytest.raises(protocol.ProtocolError):
            protocol.parse_client({"v": 1, "type": "set_context", "data": {"ref": QWEN, "tokens": tokens}})


def _gpu(total_gb=12.0, free_gb=11.0):
    total, free = int(total_gb * 1024), int(free_gb * 1024)
    return vram.GpuMemory(name="RTX", total_mb=total, used_mb=total - free, free_mb=free, source="smi")


def _show(info):
    def handler(request):
        assert request.url.path == "/api/show" and json.loads(request.content)["model"] == "qwen3.5:9b"
        return httpx.Response(200, json={"model_info": info, "capabilities": ["completion"]})

    return httpx.MockTransport(handler)


def _row(**kw):
    return {"_digest": "abc", "ref": QWEN, "full": "qwen3.5:9b", "backend": "ollama", "kind": "local",
            "size_bytes": int(5.6 * GIB), "label": "Qwen3.5 9B", **kw}


@pytest.mark.asyncio
async def test_a_local_row_carries_its_range_setting_and_fit_point(monkeypatch):
    monkeypatch.setattr(listing, "_OLLAMA_FACTS", {})
    set_memory(**{QWEN: 32768})
    snap = vram.Snapshot(_gpu(), {})
    [row] = await listing.with_context([_row()], snap, config.CONFIG, _show(INFO))
    ctx = row["context"]
    assert "_digest" not in row
    assert ctx["max"] == 262144 and ctx["value"] == 32768 and ctx["spills"] is True
    room = 11 * 1024 - config.CONFIG.vram.headroom_mb
    assert ctx["fit"] == context_fit.fit_limit(room * 1024 * 1024, int(5.6 * GIB), context_fit.kv_shape(INFO))
    assert 20000 < ctx["fit"] < 40000


@pytest.mark.asyncio
async def test_facts_are_asked_once_per_model_version(monkeypatch):
    monkeypatch.setattr(listing, "_OLLAMA_FACTS", {})
    asked = []

    def handler(request):
        asked.append(1)
        return httpx.Response(200, json={"model_info": INFO})

    t = httpx.MockTransport(handler)
    await listing.with_context([_row()], None, config.CONFIG, t)
    await listing.with_context([_row()], None, config.CONFIG, t)
    assert asked == [1]
    await listing.with_context([_row(_digest="new")], None, config.CONFIG, t)   # re-pulled
    assert asked == [1, 1]


@pytest.mark.asyncio
async def test_no_gpu_reading_means_no_fit_point_and_no_facts_no_slider(monkeypatch):
    monkeypatch.setattr(listing, "_OLLAMA_FACTS", {})
    [row] = await listing.with_context([_row()], None, config.CONFIG, _show(INFO))
    assert row["context"]["fit"] is None and row["context"]["max"] == 262144
    monkeypatch.setattr(listing, "_OLLAMA_FACTS", {})
    [bare] = await listing.with_context([_row()], vram.Snapshot(_gpu(), {}), config.CONFIG, _show({}))
    assert bare["context"] is None


@pytest.mark.asyncio
async def test_past_the_fit_point_ollama_still_loads_but_llamacpp_is_refused(monkeypatch):
    snap = vram.Snapshot(_gpu(12, 10), {})

    async def fake_snapshot(rt):
        return snap

    async def fake_rows(*a, **k):
        return [_row()], None

    monkeypatch.setattr(listing, "_snapshot", fake_snapshot)
    monkeypatch.setattr(listing, "ollama_rows", fake_rows)
    set_memory(**{QWEN: 131072})       # far past what 10 GB holds
    check = await listing.load_check(QWEN, rt=None)
    assert check.fits is None          # a warning in the picker, not a block (D-098)
    set_memory()                       # the usual 8K fits: unchanged behaviour
    assert (await listing.load_check(QWEN, rt=None)).fits is True


def _gguf(path, pairs):
    """A tiny GGUF v3 header: no tensors, the given key/values, one skipped array."""
    def s(text):
        raw = text.encode()
        return struct.pack("<Q", len(raw)) + raw

    body = b""
    for key, (kind, value) in pairs.items():
        body += s(key) + struct.pack("<I", kind)
        if kind == 4:
            body += struct.pack("<I", value)
        elif kind == 8:
            body += s(value)
        elif kind == 9:   # an array of strings, as the vocabulary is
            body += struct.pack("<IQ", 8, len(value)) + b"".join(s(v) for v in value)
    path.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 0, len(pairs)) + body)


def test_a_llamacpp_model_s_facts_come_from_its_gguf_header(tmp_path):
    f = tmp_path / "m.gguf"
    _gguf(f, {
        "general.architecture": (8, "qwen3"),
        "tokenizer.ggml.tokens": (9, ["a", "b", "c"]),
        "qwen3.block_count": (4, 36),
        "qwen3.attention.head_count": (4, 32),
        "qwen3.attention.head_count_kv": (4, 8),
        "qwen3.embedding_length": (4, 4096),
        "qwen3.context_length": (4, 40960),
    })
    meta = context_fit.gguf_metadata(str(f))
    assert "tokenizer.ggml.tokens" not in meta
    assert context_fit.context_max(meta) == 40960
    assert context_fit.kv_shape(meta).bytes_per_token() == 144 * 1024
    (tmp_path / "bad.gguf").write_bytes(b"nope")
    assert context_fit.gguf_metadata(str(tmp_path / "bad.gguf")) == {}
    assert context_fit.gguf_metadata(str(tmp_path / "missing.gguf")) == {}


@pytest.mark.asyncio
async def test_setting_it_saves_forgets_the_old_measurement_and_reloads_the_model_in_memory(monkeypatch):
    from session import Session

    vram.MEASURED.record(QWEN, 7000)
    reloads, frames = [], []
    monkeypatch.setattr(hub, "drives", lambda ws: True)
    monkeypatch.setattr(model_loader.LOADER, "_ref", QWEN)
    monkeypatch.setattr(model_loader.LOADER, "_state", model_loader.READY)
    monkeypatch.setattr(model_loader.LOADER, "request", lambda ref, **kw: reloads.append((ref, kw)))

    async def fake_list(rt, cfg=None):
        return {"local": [], "api": []}

    async def broadcast(frame):
        frames.append(frame)

    monkeypatch.setattr(listing, "model_list", fake_list)
    monkeypatch.setattr(hub, "broadcast", broadcast)
    session = Session.__new__(Session)
    session.ws, session.turn = object(), None
    await session.on_set_context(SimpleNamespace(data=SimpleNamespace(ref=QWEN, tokens=32768)))
    assert settings_file.read() == {"llm": {"context_by_model": {QWEN: 32768}}}
    assert context_fit.context_for(QWEN) == 32768
    assert vram.MEASURED.get(QWEN) is None              # measured at 8K: no longer true
    assert reloads == [(QWEN, {"force": True})]         # the loading strip shows while it reloads
    assert [f["type"] for f in frames] == ["model_list"]
    model_loader.LOADER.reset()
