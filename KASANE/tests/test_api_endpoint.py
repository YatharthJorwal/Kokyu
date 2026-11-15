"""K1-08b (FR-R-6, D-037, D-059): one OpenAI-compatible endpoint at a time, keys
from the shell, presets and their catalogs. No key, no network, no shell."""

import asyncio
import dataclasses
import io
import json
import os
import sqlite3
import subprocess
import sys

import httpx
import pytest

import config
import provider_presets
import shell_keys
from router import Router
from router import decision as d
from router.audit import AuditWriter
from router.budget import SpendLedger
from router.discovery import ModelCatalog, _to_info
from router.errors import RouteBlockedError
from router.types import ModelChunk, ModelRequest, Usage

from test_router import FakeCatalog, FakeProvider, drain, make_config


# -- presets and config ----------------------------------------------------------


def test_the_api_slot_fills_what_the_yaml_leaves_out_from_its_preset():
    slot = config._normalize_providers({"providers": {"airouter": {"preset": "openrouter"}}}, {})["airouter"]
    assert (slot.preset, slot.label, slot.price_unit) == ("openrouter", "OpenRouter", "per_token")
    assert slot.base_url == "https://openrouter.ai/api/v1" and slot.api_key_env == "OPENROUTER_API_KEY"
    old = config._normalize_providers({"providers": {"airouter": {"base_url": "https://api.airouter.in/v1"}}}, {})
    assert old["airouter"].preset == "airouter" and old["airouter"].models_cache == "data/airouter_models.json"


def test_a_custom_endpoint_needs_its_own_url_and_has_no_prices():
    slot = config._normalize_providers(
        {"providers": {"airouter": {"preset": "mine", "base_url": "https://llm.example.com/v1"}}}, {}
    )["airouter"]
    assert slot.models_url == "https://llm.example.com/v1/models" and slot.price_unit == "none"
    assert config.api_endpoint(slot, "mine") is slot
    switched = config.api_endpoint(slot, "deepseek")
    assert switched.base_url == "https://api.deepseek.com" and switched.request_timeout_s == slot.request_timeout_s
    assert config.api_endpoint(slot, "nowhere") is None


def test_changing_only_the_preset_never_keeps_another_endpoints_url():
    # A config copied from the example with only `preset:` changed (review of D-059):
    # the OpenRouter key must not go to the AI Router URL still written in the file.
    notes = []
    slot = config._normalize_providers(
        {"providers": {"airouter": {
            "preset": "openrouter",
            "base_url": "https://api.airouter.in/v1",
            "models_url": "https://api.airouter.in/v1/models",
            "api_key_env": "AIROUTER_API_KEY",
            "price_unit": "per_million",
        }}},
        {},
        notes,
    )["airouter"]
    assert slot.base_url == "https://openrouter.ai/api/v1" and slot.models_url == "https://openrouter.ai/api/v1/models"
    assert slot.api_key_env == "OPENROUTER_API_KEY" and slot.price_unit == "per_token"
    assert any("base_url is ignored" in n for n in notes)
    same = []
    config._normalize_providers({"providers": {"airouter": {"base_url": "https://api.airouter.in/v1"}}}, {}, same)
    assert same == []                                                  # the old file's own URL: no noise


def test_a_custom_id_the_shell_cannot_store_turns_the_api_off_with_a_warning():
    notes = []
    slot = config._normalize_providers(
        {"providers": {"airouter": {"preset": "my-lab", "base_url": "https://llm.example.com/v1"}}}, {}, notes
    )["airouter"]
    assert slot.enabled is False and "not a valid id" in notes[0]


def test_a_key_left_for_an_endpoint_that_is_gone_is_ignored():
    slot = config._normalize_providers({"providers": {"airouter": {"preset": "airouter"}}}, {})["airouter"]
    shell_keys.set("mylab", "sk-lab-1234567890")
    assert config.active_api_id(slot) == "airouter"
    shell_keys.set("openrouter", "sk-or-1234567890")
    assert config.active_api_id(slot) == "openrouter"


def test_a_developer_key_with_spaces_is_ignored_so_no_error_can_quote_it(tmp_path, monkeypatch, capsys, caplog):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-live SECRET123")
    assert config.resolve_api_key("DEEPSEEK_API_KEY", provider="deepseek", secrets_path=tmp_path / "none.yaml") is None
    assert "SECRET123" not in capsys.readouterr().err + caplog.text


@pytest.mark.parametrize(
    "url, ok",
    [
        ("https://openrouter.ai/api/v1", True),
        ("http://127.0.0.1:8080/v1", True),
        ("http://example.com/v1", False),                 # the key would cross the network in clear
        ("https://user:pw@example.com/v1", False),
        ("https://example.com/v1?key=x", False),
        ("ftp://example.com", False),
        ("https://llm.example.com:99999/v1", False),       # a typo in the port must not crash the router
    ],
)
def test_only_https_or_this_pc_may_carry_a_key(url, ok):
    assert (provider_presets.url_problem(url) is None) is ok


# -- where a key comes from ---------------------------------------------------------


def test_a_key_saved_in_the_app_wins_and_packaged_builds_use_only_that(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-the-environment")
    assert config.resolve_api_key("OPENROUTER_API_KEY", provider="openrouter") == "from-the-environment"
    shell_keys.set("openrouter", "sk-or-from-the-app")
    assert config.resolve_api_key("OPENROUTER_API_KEY", provider="openrouter") == "sk-or-from-the-app"
    shell_keys.clear()
    monkeypatch.setenv("KOKYU_PACKAGED", "1")
    monkeypatch.setattr(config.paths, "is_packaged", lambda: True)
    assert config.resolve_api_key("OPENROUTER_API_KEY", provider="openrouter") is None   # FR-R-6


def test_a_providers_secrets_section_is_never_handed_to_another(tmp_path, monkeypatch):
    for name in ("AIROUTER_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text("airouter:\n  api_key: sk-air-key\n", encoding="utf-8")
    missing = tmp_path / "none.env"
    assert config.resolve_api_key("AIROUTER_API_KEY", provider="airouter", secrets_path=secrets, dotenv_path=missing) == "sk-air-key"
    assert config.resolve_api_key("OPENROUTER_API_KEY", provider="openrouter", secrets_path=secrets, dotenv_path=missing) is None


def test_the_shell_handoff_leaves_the_environment_before_any_child_starts(monkeypatch):
    monkeypatch.setenv("KOKYU_API_KEYS", json.dumps({"openrouter": "sk-or-1234567890", "Bad Id": "sk-x-1234567890", "deepseek": "short"}))
    monkeypatch.setenv("KOKYU_KEY_PIPE", "1")
    shell_keys.take_from_environ()
    assert "KOKYU_API_KEYS" not in os.environ and "KOKYU_KEY_PIPE" not in os.environ
    assert shell_keys.PIPE_ENABLED and shell_keys.app_provider() == "openrouter"
    assert shell_keys.get("deepseek") is None                        # too short to be a key: dropped
    seen = subprocess.run(
        [sys.executable, "-c", "import os; print(os.environ.get('KOKYU_API_KEYS'))"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert seen == "None"


def test_unreadable_keys_from_the_shell_are_dropped_without_echoing_them(monkeypatch, capsys, caplog):
    monkeypatch.setenv("KOKYU_API_KEYS", "{not json sk-SENTINEL-0123456789")
    shell_keys.take_from_environ()
    assert shell_keys.app_provider() is None and "SENTINEL" not in capsys.readouterr().out + caplog.text


@pytest.mark.parametrize(
    "line, parsed",
    [
        (b'{"provider": "openrouter", "key": "sk-or-1234567890"}', ("openrouter", "sk-or-1234567890")),
        (b'\xef\xbb\xbf{"provider": "deepseek", "key": null}', ("deepseek", None)),      # removal; a BOM is tolerated
        (b'{"provider": "Open-Router", "key": "sk-or-1234567890"}', None),
        (b'{"provider": "openrouter", "key": "has a space 123"}', None),
        (b'{"provider": "openrouter", "key": "short"}', None),
        (b'["openrouter", "sk-or-1234567890"]', None),
        (b"not json", None),
        (b'{"provider": "openrouter", "key": "' + b"k" * 5000 + b'"}', None),
    ],
)
def test_a_pipe_line_is_a_key_message_or_nothing(line, parsed):
    assert shell_keys.parse_line(line) == parsed


@pytest.mark.asyncio
async def test_the_pipe_reader_applies_each_change_in_order_and_never_prints_a_key(capsys, caplog):
    seen = []

    async def apply(provider, key):
        seen.append((provider, key))

    stream = io.BytesIO(
        b'{"provider": "openrouter", "key": "sk-or-1234567890"}\n'
        b'garbage sk-SENTINEL-0123456789\n'
        b'{"provider": "openrouter", "key": null}\n'
    )
    thread = shell_keys.start_reader(asyncio.get_running_loop(), apply, stream)
    while thread.is_alive():
        await asyncio.sleep(0.01)
    assert seen == [("openrouter", "sk-or-1234567890"), ("openrouter", None)]
    assert "SENTINEL" not in capsys.readouterr().out + caplog.text


def test_a_normal_exit_with_the_pipe_reader_running_is_clean():
    # A daemon thread blocked on sys.stdin.buffer made any non-os._exit exit die with
    # "Fatal Python error: _enter_buffered_busy" (say, when port 8780 is taken).
    code = "\n".join([
        "import asyncio, sys",
        f"sys.path.insert(0, {os.path.dirname(shell_keys.__file__)!r})",
        "import shell_keys",
        "async def apply(p, k): pass",
        "async def main():",
        "    shell_keys.start_reader(asyncio.get_running_loop(), apply)",
        "    await asyncio.sleep(0.3)",
        "asyncio.run(main())",
        "sys.exit(3)",
    ])
    proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        code_out = proc.wait(timeout=30)   # stdin stays open, as the shell keeps it
    finally:
        proc.stdin.close()
    assert code_out == 3, proc.stderr.read().decode(errors="replace")


def test_one_key_at_a_time():
    shell_keys.set("openrouter", "sk-or-1234567890")
    shell_keys.set("deepseek", "sk-ds-1234567890")
    assert shell_keys.app_provider() == "deepseek" and shell_keys.get("openrouter") is None


# -- catalogs ---------------------------------------------------------------------


def test_openrouter_prices_per_token_are_kept_per_million_and_badges_derived():
    entry = {
        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
        "supported_parameters": ["tools", "reasoning", "temperature"],
        "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
        "top_provider": {"max_completion_tokens": 8192},
    }
    info = _to_info("anthropic/x", entry, "per_token")
    assert (info.price_in, info.price_out, info.priced) == (pytest.approx(3.0), pytest.approx(15.0), True)
    assert set(info.tags) == {"tool-use", "reasoning", "vision"} and info.max_tokens == 8192
    assert not _to_info("openrouter/auto", {"pricing": {"prompt": "-1", "completion": "-1"}}, "per_token").priced
    assert not _to_info("deepseek-chat", {"id": "deepseek-chat", "object": "model"}, "none").priced
    assert _to_info("free", {"pricing": {"prompt": "0", "completion": "0"}}, "per_token").priced   # 0 is a price
    assert _to_info("img", {"architecture": {"output_modalities": ["image"]}}, "per_token").kind == "image"


@pytest.mark.asyncio
async def test_the_models_list_gets_the_key_only_when_set_and_the_cache_is_per_endpoint(tmp_path):
    seen = []

    def handler(request):
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"data": [{"id": "deepseek-chat", "object": "model"}]})

    catalog = ModelCatalog("https://api.deepseek.com", tmp_path / "ds.json", price_unit="none",
                           transport=httpx.MockTransport(handler))
    assert await catalog.refresh(force=True)
    catalog.api_key = "sk-ds-1234567890"
    assert await catalog.refresh(force=True)
    assert seen == [None, "Bearer sk-ds-1234567890"]
    assert "sk-ds" not in (tmp_path / "ds.json").read_text(encoding="utf-8")
    other = ModelCatalog("https://openrouter.ai/api/v1", tmp_path / "ds.json")
    assert other.load_cache() is False                       # another endpoint's list is not ours


# -- the router -------------------------------------------------------------------


class Cloud:
    name = "airouter"

    def __init__(self):
        self.requests = []

    async def complete(self, request, *, model):
        self.requests.append(model)
        yield ModelChunk.content("hi")
        yield ModelChunk.done(Usage(10, 2))


def keyless_router(tmp_path, monkeypatch, **kw):
    monkeypatch.setattr(config, "resolve_api_key", lambda env, *, provider=None, **_: shell_keys.get(provider))
    cfg = make_config(tmp_path, mode="enforce")
    cfg = dataclasses.replace(cfg, budget=dataclasses.replace(cfg.budget, enabled=False))
    return Router(
        cfg,
        catalog=FakeCatalog(),
        local_provider=FakeProvider("local_ollama"),
        audit=AuditWriter(tmp_path / "audit.jsonl"),
        ledger=SpendLedger(tmp_path / "spend.db"),
        **kw,
    )


def ask(ref):
    return ModelRequest(role="chat", messages=({"role": "user", "content": "hi"},), model_ref=ref)


@pytest.mark.asyncio
async def test_a_key_saved_in_the_app_switches_the_endpoint_live(tmp_path, monkeypatch):
    router = keyless_router(tmp_path, monkeypatch)
    assert router.api_status()["key"] is None
    with pytest.raises(RouteBlockedError) as blocked:
        await drain(router, ask("api:openrouter/meta/llama"))
    assert blocked.value.reason == d.OTHER_PROVIDER                  # not the active endpoint: never rerouted

    router.catalog = FakeCatalog()
    monkeypatch.setattr(router, "_catalog_for", lambda cfg: FakeCatalog())
    assert await router.use_app_key("openrouter", "sk-or-1234567890") is True
    assert router.api_status() == {"id": "openrouter", "label": "OpenRouter", "key": "app"}
    assert router.cloud_provider is not None and router.cloud_provider.api_key == "sk-or-1234567890"

    cloud = Cloud()
    router.cloud_provider = cloud
    await drain(router, ask("api:openrouter/meta/llama"))
    assert cloud.requests == ["meta/llama"]
    with pytest.raises(RouteBlockedError) as blocked:
        await drain(router, ask("api:airouter/deepseek/deepseek-v4-flash"))   # an old thread, other endpoint
    assert blocked.value.reason == d.OTHER_PROVIDER
    with sqlite3.connect(tmp_path / "spend.db") as conn:
        assert conn.execute("SELECT provider FROM spend").fetchall() == [("openrouter",)]

    assert await router.use_app_key("openrouter", None) is False      # removed: back to the config's endpoint
    assert router.api_id == make_config(tmp_path).providers["airouter"].preset and router.cloud_provider is None


@pytest.mark.asyncio
async def test_a_key_change_mid_reply_bills_that_reply_at_its_own_price_and_endpoint(tmp_path, monkeypatch):
    router = keyless_router(tmp_path, monkeypatch)
    monkeypatch.setattr(router, "_catalog_for", lambda cfg: FakeCatalog())
    assert await router.use_app_key("airouter", "sk-ar-1234567890") is True

    class Unpriced(FakeCatalog):
        def price(self, model):
            return (0.0, 0.0)

    class SwitchMidReply:
        name = "airouter"

        async def complete(self, request, *, model):
            yield ModelChunk.content("hi")
            await router.use_app_key("openrouter", "sk-or-1234567890")   # saved in the model menu meanwhile
            yield ModelChunk.done(Usage(100_000, 100_000))

    router.cloud_provider = SwitchMidReply()
    monkeypatch.setattr(router, "_catalog_for", lambda cfg: Unpriced())
    await drain(router, ask("api:airouter/deepseek/deepseek-v4-flash"))
    with sqlite3.connect(tmp_path / "spend.db") as conn:
        rows = conn.execute("SELECT provider, cost_usd FROM spend").fetchall()
    assert rows == [("airouter", pytest.approx(0.2))]                # $0.5 + $1.5 per M on 100k each


@pytest.mark.asyncio
async def test_an_endpoint_that_would_send_the_key_in_clear_gets_no_provider(tmp_path, monkeypatch):
    router = keyless_router(tmp_path, monkeypatch)
    plain = dataclasses.replace(router._cloud_cfg, base_url="http://example.com/v1")
    router._install_key(plain, "sk-or-1234567890")
    assert router.cloud_provider is None and not router.api_key_present


@pytest.mark.asyncio
async def test_the_model_list_names_the_active_endpoint_but_never_its_key(tmp_path, monkeypatch):
    from router import listing

    router = keyless_router(tmp_path, monkeypatch)
    monkeypatch.setattr(router, "_catalog_for", lambda cfg: FakeCatalog())
    await router.use_app_key("openrouter", "sk-or-1234567890")

    async def no_ollama(*a, **k):
        return [], None

    monkeypatch.setattr(listing, "ollama_rows", no_ollama)
    listed = await listing.model_list(router, cfg=router.config)
    assert listed["api_provider"] == {"id": "openrouter", "label": "OpenRouter", "key": "app"}
    assert [p["id"] for p in listed["api_presets"]] == ["airouter", "openrouter", "deepseek"]
    assert all(row["ref"].startswith("api:openrouter/") for row in listed["api"])
    assert "sk-or" not in json.dumps(listed)


@pytest.mark.asyncio
async def test_a_key_change_reaches_every_window(monkeypatch):
    import app

    class Rt:
        def __init__(self):
            self.changes = []
            self.state = type("S", (), {"cloud_available": True})()
            self.use_api_model_override = None

        async def use_app_key(self, provider, key):
            self.changes.append((provider, key))
            return True

        def api_status(self):
            return {"id": "openrouter", "label": "OpenRouter", "key": "app"}

    class Ws:
        def __init__(self):
            self.sent = []

        async def send_json(self, frame):
            self.sent.append(frame)

    rt, windows = Rt(), [Ws(), Ws()]

    async def listed(*a, **k):
        return {"api": [], "api_provider": rt.api_status()}

    monkeypatch.setattr(app.router, "get_router", lambda: rt)
    monkeypatch.setattr(app.model_listing, "model_list", listed)
    monkeypatch.setattr(app, "_active_connections", set(windows))
    await app._apply_shell_key("openrouter", "sk-or-1234567890")
    assert rt.changes == [("openrouter", "sk-or-1234567890")]
    for ws in windows:
        assert [f["type"] for f in ws.sent] == ["model_list", "settings"]
        assert "sk-or" not in json.dumps(ws.sent)
