"""K1-07 / K1-10 (FR-M-3, 4, 7): what the model picker lists."""
from __future__ import annotations

import dataclasses

import httpx
import pytest

import llm
import vram
from config import CONFIG, ChatConfig, LlamaCppConfig, LlamaCppPreset, VramConfig
from router import listing
from router.discovery import ModelCatalog, ModelInfo

TAGS = {
    "models": [
        {"name": "qwen3.5:4b", "size": 3_400_000_000, "details": {"family": "qwen35", "parameter_size": "4.7B", "quantization_level": "Q4_K_M"}},
        {"name": "nomic-embed-text:latest", "size": 274_000_000, "details": {"family": "nomic-bert"}},
        {"name": "bge-m3:latest", "size": 1_200_000_000, "details": {"family": "bert", "families": ["bert"]}},
        {"name": "qwen3.5:9b", "size": 6_600_000_000, "details": {"family": "qwen35", "parameter_size": "9.7B"}},
        {"name": "broken"},
        "junk",
    ]
}


def tags_transport(payload=TAGS, status=200):
    return httpx.MockTransport(lambda request: httpx.Response(status, json=payload))


@pytest.mark.asyncio
async def test_ollama_lists_chat_models_largest_first_without_embedding_models():
    rows, error = await listing.ollama_rows("http://ollama", transport=tags_transport())
    assert error is None
    assert [r["ref"] for r in rows] == ["local:ollama/qwen3.5:9b", "local:ollama/qwen3.5:4b", "local:ollama/broken"]
    nine = rows[0]
    assert nine["label"] == "qwen3.5:9b" and nine["kind"] == "local" and nine["size_bytes"] == 6_600_000_000
    assert nine["detail"] == "Ollama · 9.7B" and nine["available"] and nine["fits"] is None
    assert rows[1]["detail"] == "Ollama · 4.7B · Q4_K_M"
    # the slider's detents come from config/models.example.yaml (FR-M-10)
    assert nine["efforts"] == ["off", "high"] and rows[2]["efforts"] == []


@pytest.mark.asyncio
async def test_ollama_down_or_erroring_leaves_the_section_empty_with_a_reason():
    def refused(request):
        raise httpx.ConnectError("refused")

    assert await listing.ollama_rows("http://ollama", transport=httpx.MockTransport(refused)) == ([], "Ollama is not running")
    assert await listing.ollama_rows("http://ollama", transport=tags_transport(status=500)) == ([], "Ollama answered 500")
    rows, _ = await listing.ollama_rows("http://ollama", exclude=frozenset({"qwen3.5:4b"}), transport=tags_transport())
    assert "local:ollama/qwen3.5:4b" not in [r["ref"] for r in rows]


def test_llamacpp_presets_show_file_size_or_say_the_file_is_missing(tmp_path):
    gguf = tmp_path / "big.gguf"
    gguf.write_bytes(b"\0" * 2048)
    cfg = LlamaCppConfig(presets=(
        LlamaCppPreset(id="big", label="Qwen 35B", model_path=str(gguf), ctx=8192),
        LlamaCppPreset(id="gone", model_path=str(tmp_path / "missing.gguf")),
    ))
    big, gone = listing.llamacpp_rows(cfg)
    assert (big["ref"], big["label"], big["size_bytes"], big["available"]) == ("local:llamacpp/big", "Qwen 35B", 2048, True)
    assert big["detail"] == "llama.cpp · 8k context"
    assert (gone["label"], gone["available"], gone["note"]) == ("gone", False, "model file not found")


def catalog(tmp_path, models):
    # fetched at 0, read much later: a cache from a past session, so stale
    cat = ModelCatalog("https://api.example/v1", tmp_path / "cat.json", clock=lambda: 1e9)
    cat._models = {m.id: m for m in models}
    return cat


def test_api_rows_come_from_the_catalog_and_need_a_key(tmp_path):
    cat = catalog(tmp_path, [
        ModelInfo("vendor/chat-1", context_length=128_000, price_in=0.5, price_out=1.5, tags=("reasoning",)),
        ModelInfo("vendor/embed-1", kind="embedding"),
    ])
    [row] = listing.api_rows(cat, key_present=False)
    assert row["ref"] == "api:airouter/vendor/chat-1" and row["detail"] == "128k context"
    assert (row["available"], row["note"]) == (False, "needs an API key")      # listed, but picking it would be refused
    assert (row["price_in"], row["price_out"], row["tags"]) == (0.5, 1.5, ["reasoning"])
    assert listing.api_rows(cat, key_present=True)[0]["available"] is True
    assert listing.api_rows(None, key_present=True) == []


@pytest.mark.asyncio
async def test_model_list_puts_it_together_with_the_spend_footer(tmp_path):
    gguf = tmp_path / "big.gguf"
    gguf.write_bytes(b"\0")
    cfg = dataclasses.replace(
        CONFIG,
        chat=ChatConfig(default_model_ref="local:llamacpp/big"),
        llamacpp=LlamaCppConfig(presets=(LlamaCppPreset(id="big", label="Qwen 35B", model_path=str(gguf)),)),
        budget=dataclasses.replace(CONFIG.budget, daily_usd=1.5, monthly_usd=-1),
    )

    class Ledger:
        def totals(self):
            return (0.01, 0.25, 3.0)

    class Rt:
        api_key_present = True
        ledger = Ledger()

        def __init__(self):
            self.catalog = catalog(tmp_path, [ModelInfo("vendor/chat-1")])
            self.refreshed = False

            async def refresh(force=False):
                self.refreshed = force

            self.catalog.refresh = refresh
            self.ensured = False

        async def ensure_cloud(self, *, fetch=True):
            self.ensured = not fetch           # recheck only: the list was just fetched

    rt = Rt()
    data = await listing.model_list(rt, refresh=True, cfg=cfg, transport=tags_transport())
    assert rt.refreshed is True
    assert rt.ensured is True                                   # a refreshed list is usable at once (K1-08 review)
    assert (data["api"][0]["group"], data["api"][0]["label"]) == ("vendor", "chat-1")   # FR-M-4 groups
    assert data["default_ref"] == "local:llamacpp/big"
    assert [r["ref"] for r in data["local"]][:2] == ["local:llamacpp/big", "local:ollama/qwen3.5:9b"]   # presets first
    assert [r["ref"] for r in data["api"]] == ["api:airouter/vendor/chat-1"]
    assert data["api_key"] is True and data["api_stale"] is True and data["local_error"] is None
    assert data["spend"] == {
        "enabled": cfg.budget.enabled,
        "hour_usd": 0.01,
        "hourly_cap_usd": cfg.budget.hourly_usd,   # the cap that usually blocks first
        "day_usd": 0.25,
        "month_usd": 3.0,
        "daily_cap_usd": 1.5,
        "monthly_cap_usd": None,
    }


@pytest.mark.asyncio
async def test_a_failed_refresh_keeps_the_cache_but_says_so(tmp_path):
    # FR-M-4: offline, the cached list is shown marked stale, with the reason.
    def refused(request):
        raise httpx.ConnectError("offline")

    cat = ModelCatalog("https://api.example/v1", tmp_path / "cat.json", transport=httpx.MockTransport(refused))
    cat._models = {"vendor/chat-1": ModelInfo("vendor/chat-1", zdr=True)}
    cat._fetched_at = cat._clock()                                         # fresh: only the failure can mark it

    class Rt:
        api_key_present = True
        ledger = None
        catalog = cat

    cfg = dataclasses.replace(CONFIG, llamacpp=LlamaCppConfig(presets=()))
    data = await listing.model_list(Rt(), refresh=True, cfg=cfg, transport=tags_transport())
    assert [r["ref"] for r in data["api"]] == ["api:airouter/vendor/chat-1"]
    assert data["api"][0]["tags"] == ["zdr"]                                  # "no retention" badge
    assert data["api_stale"] is True and "ConnectError" in data["api_error"]


def test_default_ref_and_labels():
    cfg = dataclasses.replace(CONFIG, chat=ChatConfig(default_model_ref=None))
    assert listing.default_ref(cfg).startswith("local:ollama/")
    assert listing.effective_ref("api:airouter/x", cfg) == "api:airouter/x"
    cfg = dataclasses.replace(
        cfg, llamacpp=LlamaCppConfig(presets=(LlamaCppPreset(id="big", label="Qwen 35B", model_path="x"),))
    )
    assert listing.label_for("local:llamacpp/big", cfg) == "Qwen 35B"
    assert listing.label_for("local:llamacpp/other", cfg) == "other"
    assert listing.label_for("local:ollama/qwen3.5:9b", cfg) == "qwen3.5:9b"
    assert listing.label_for("nonsense", cfg) == "nonsense"


# -- K1-09: the fits hint and the check before a load (FR-M-3, FR-M-6) ---------------
# GPU and residents as measured on the dev PC (2026-11-15): 394 MB free of 12 GB.

RTX = vram.GpuMemory("NVIDIA GeForce RTX 3060", 12288, 11893, 394, "nvml")
PS = {"models": [
    {"name": "qwen3.5:9b", "size": 5590 * vram.MB, "size_vram": 5590 * vram.MB},
    {"name": "qwen3.5:4b", "size": 3207 * vram.MB, "size_vram": 3207 * vram.MB},
    {"name": "nomic-embed-text:latest", "size": 320 * vram.MB, "size_vram": 320 * vram.MB},
]}
MORE_TAGS = {"models": [
    *TAGS["models"],
    {"name": "gemma3:27b", "size": 17_000_000_000, "details": {"family": "gemma3"}},
    {"name": "qwen3:1.7b", "size": 1_400_000_000, "details": {"family": "qwen3"}},
]}


class NoLlamaServer:
    def llamacpp_preset(self):
        return None


@pytest.fixture
def gpu_cfg(tmp_path, monkeypatch):
    async def gpu():
        return RTX

    async def ps():
        return PS

    monkeypatch.setattr(vram, "gpu_memory", gpu)
    monkeypatch.setattr(llm, "loaded_models", ps)
    gguf = tmp_path / "big.gguf"
    gguf.write_bytes(b"\0")
    helpers = {"classifier": "qwen3.5:4b", "memory_writer": "qwen3.5:4b", "embed": "nomic-embed-text"}
    return dataclasses.replace(
        CONFIG,
        models=dataclasses.replace(CONFIG.models, local={**CONFIG.models.local, **helpers}),
        memory=dataclasses.replace(CONFIG.memory, embedding=dataclasses.replace(CONFIG.memory.embedding, model="nomic-embed-text")),
        llamacpp=LlamaCppConfig(presets=(LlamaCppPreset(id="big", label="Qwen 35B", model_path=str(gguf), n_cpu_moe=40),)),
        vram=VramConfig(),
    )


@pytest.mark.asyncio
async def test_local_rows_say_whether_they_fit(gpu_cfg):
    data = await listing.model_list(NoLlamaServer(), cfg=gpu_cfg, transport=tags_transport(MORE_TAGS))
    fits = {r["ref"]: r["fits"] for r in data["local"]}
    assert fits == {
        "local:llamacpp/big": None,            # experts in RAM: unknown until measured
        "local:ollama/gemma3:27b": False,      # 16 GB + KV: more than the card
        "local:ollama/qwen3.5:9b": True,       # already loaded
        "local:ollama/qwen3.5:4b": True,       # a helper, already loaded
        "local:ollama/qwen3:1.7b": True,       # fits once the 9B makes room
        "local:ollama/broken": None,           # no size: nothing to estimate from
    }


@pytest.mark.asyncio
async def test_no_gpu_reading_leaves_every_hint_unknown(tmp_path):
    data = await listing.model_list(NoLlamaServer(), cfg=CONFIG, transport=tags_transport())
    assert {r["fits"] for r in data["local"]} == {None}


@pytest.mark.asyncio
async def test_the_check_before_a_load_names_the_blocker(gpu_cfg):
    check = await listing.load_check("local:ollama/gemma3:27b", NoLlamaServer(), gpu_cfg, transport=tags_transport(MORE_TAGS))
    assert check.fits is False and "more than this GPU has (12.0 GB)" in check.message
    vram.MEASURED.record("local:ollama/gemma3:27b", 7000)   # measured once: smaller than the estimate
    check = await listing.load_check("local:ollama/gemma3:27b", NoLlamaServer(), gpu_cfg, transport=tags_transport(MORE_TAGS))
    assert check.fits is False and check.message.startswith("It needs about 6.9 GB of graphics memory, but only 5.3 GB")
    assert "In use: qwen3.5:4b (3.1 GB), other programs (2.7 GB), nomic-embed-text (0.3 GB)." in check.message
    ok = await listing.load_check("local:ollama/qwen3:1.7b", NoLlamaServer(), gpu_cfg, transport=tags_transport(MORE_TAGS))
    assert ok.fits is True
    for unknown in ("api:airouter/vendor/chat-1", "local:ollama/not-pulled:1b", "local:llamacpp/big"):
        assert (await listing.load_check(unknown, NoLlamaServer(), gpu_cfg, transport=tags_transport(MORE_TAGS))).fits is None
