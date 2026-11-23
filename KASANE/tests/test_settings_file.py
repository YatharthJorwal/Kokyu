"""K1-13b (FR-SET-2, D-070): settings.json over config.yaml, applied with no restart."""
from __future__ import annotations

import asyncio
import json
import sys
import types

import pytest

import boot
import config
import hub
import router
import settings_file
from router import listing
from senses import ocr_watch, task_guide
from test_api_endpoint import FakeCatalog, keyless_router

YAML = """
llm:
  base_url: 'http://127.0.0.1:11434'
providers:
  airouter:
    preset: openrouter
    request_timeout_s: 33
budget:
  hourly_usd: 0.5
  daily_usd: 2
"""


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"


@pytest.fixture
def running_config():
    """Every test that installs a config puts the old one back."""
    old = config.CONFIG
    yield old
    config.install(old)


def load(tmp_path, saved):
    file = tmp_path / "config.yaml"
    file.write_text(YAML, encoding="utf-8")
    return config.load_config(file, quiet=True, overlay=saved)


# -- the file ---------------------------------------------------------------------


def test_the_file_round_trips_and_a_broken_one_is_ignored(data_dir):
    assert settings_file.read() == {}
    settings_file.write({"budget": {"enabled": False}})
    assert json.loads(settings_file.path().read_text(encoding="utf-8"))["version"] == settings_file.VERSION
    assert settings_file.read() == {"budget": {"enabled": False}}
    assert not settings_file.path().with_name("settings.json.tmp").exists()

    settings_file.path().write_text("{not json", encoding="utf-8")
    assert settings_file.read() == {}                      # the app still starts, on config.yaml alone
    broken = settings_file.path().with_name("settings.json.broken")
    assert broken.read_text(encoding="utf-8") == "{not json"   # kept before a change rewrites the file
    settings_file.path().write_text("[1, 2]", encoding="utf-8")
    assert settings_file.read() == {}
    settings_file.write({"budget": "off", "llm": {"base_url": "http://localhost:1"}})   # hand-edited
    assert settings_file.read() == {"llm": {"base_url": "http://localhost:1"}}         # a section is never wiped


# -- precedence: settings.json wins, key by key (D-070) ---------------------------


def test_settings_win_over_config_yaml_key_by_key(tmp_path):
    saved = settings_file.change({}, {"ollama_url": "http://localhost:11500/", "budget": {"enabled": True, "hourly_usd": 1.0}})
    cfg = load(tmp_path, saved)
    assert cfg.llm.base_url == "http://localhost:11500"                      # the legacy llm: key in the yaml loses too
    assert cfg.providers["local_ollama"].base_url == "http://localhost:11500"
    assert cfg.memory.embedding.base_url == "http://localhost:11500"          # derived values follow
    assert (cfg.budget.hourly_usd, cfg.budget.daily_usd, cfg.budget.monthly_usd) == (1.0, -1.0, -1.0)
    assert cfg.providers["airouter"].request_timeout_s == 33                  # untouched keys stay the yaml's

    back = settings_file.change(saved, {"ollama_url": ""})
    assert "llm" not in back and "providers" not in back                     # nothing left behind
    assert load(tmp_path, back).llm.base_url == "http://127.0.0.1:11434"


@pytest.mark.parametrize(
    "url",
    ["http://192.168.1.5:11434", "http://ollama.example.com", "ftp://127.0.0.1", "http://user:pw@localhost:11434", "localhost:11434"],
)
def test_ollama_must_run_on_this_pc(url):
    # Invariant 3: what the companions see and hear goes to the local model only
    with pytest.raises(settings_file.SettingsError):
        settings_file.change({}, {"ollama_url": url})


def test_a_budget_cap_must_be_a_sane_amount():
    for bad in (-1, 10_001, float("nan"), float("inf")):
        with pytest.raises(settings_file.SettingsError):
            settings_file.change({}, {"budget": {"enabled": True, "hourly_usd": bad}})
    saved = settings_file.change({}, {"budget": {"enabled": False, "hourly_usd": 0, "daily_usd": None}})
    assert saved["budget"] == {"enabled": False, "hourly_usd": 0.0, "daily_usd": -1.0, "monthly_usd": -1.0}


# -- a custom endpoint (K1-08b, D-059) --------------------------------------------


def test_a_custom_endpoint_never_gets_a_developer_key_and_its_id_follows_the_host(tmp_path):
    saved = settings_file.change({}, {"custom_api": {"label": "My lab", "base_url": "https://lab.example.com/v1/"}})
    slot = load(tmp_path, saved).providers["airouter"]
    assert slot.preset == settings_file.custom_id("https://lab.example.com/v1") and slot.preset.startswith("custom_")
    assert (slot.label, slot.base_url, slot.enabled) == ("My lab", "https://lab.example.com/v1", True)
    assert slot.api_key_env == ""                                             # only a key saved for it in the app
    assert slot.price_unit == "none" and slot.models_url == "https://lab.example.com/v1/models"
    assert slot.request_timeout_s == 33

    # the same host keeps its id (and its saved key); another host gets a new one
    assert settings_file.custom_id("https://lab.example.com/v2") == slot.preset
    assert settings_file.custom_id("https://evil.example.com/v1") != slot.preset

    removed = settings_file.change(saved, {"custom_api": None})
    assert load(tmp_path, removed).providers["airouter"].preset == "openrouter"


@pytest.mark.parametrize(
    "custom",
    [{"label": "", "base_url": "https://x.example.com"}, {"label": "x" * 41, "base_url": "https://x.example.com"},
     {"label": "Plain", "base_url": "http://x.example.com/v1"}, {"label": "Query", "base_url": "https://x.example.com/?k=1"}],
)
def test_a_custom_endpoint_that_could_leak_its_key_is_refused(custom):
    with pytest.raises(settings_file.SettingsError):
        settings_file.change({}, {"custom_api": custom})


def test_the_key_form_offers_the_custom_endpoint(tmp_path):
    saved = settings_file.change({}, {"custom_api": {"label": "My lab", "base_url": "https://lab.example.com/v1"}})
    targets = listing._key_targets(load(tmp_path, saved))
    assert targets[-1] == {"id": settings_file.custom_id("https://lab.example.com/v1"), "label": "My lab"}
    assert [t["id"] for t in listing._key_targets(load(tmp_path, {}))] == ["airouter", "openrouter", "deepseek"]


@pytest.mark.asyncio
async def test_the_router_follows_new_settings_live(tmp_path, monkeypatch):
    rt = keyless_router(tmp_path, monkeypatch)
    monkeypatch.setattr(rt, "_catalog_for", lambda cfg: FakeCatalog())
    saved = settings_file.change({}, {
        "custom_api": {"label": "My lab", "base_url": "https://lab.example.com/v1"},
        "budget": {"enabled": True, "hourly_usd": 0.1},
    })
    cfg = load(tmp_path, saved)
    assert await rt.reconfigure(cfg) is False                              # no key saved for it yet
    pid = settings_file.custom_id("https://lab.example.com/v1")
    assert rt.api_status() == {"id": pid, "label": "My lab", "key": None}
    assert rt.config.budget.hourly_usd == 0.1

    assert await rt.use_app_key(pid, "sk-lab-1234567890") is True         # the picker's Key form
    assert rt.cloud_provider is not None and rt.cloud_provider.api_key == "sk-lab-1234567890"

    # the address edited to another host: the saved key stays with the old one
    moved = load(tmp_path, settings_file.change(saved, {"custom_api": {"label": "My lab", "base_url": "https://other.example.com/v1"}}))
    assert await rt.reconfigure(moved) is False
    assert rt.api_status()["id"] == settings_file.custom_id("https://other.example.com/v1") and rt.cloud_provider is None


# -- live apply ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_points_every_module_at_the_new_config(data_dir, running_config, monkeypatch):
    reader = types.ModuleType("fake_reader")
    reader.CONFIG = running_config
    monkeypatch.setitem(sys.modules, "fake_reader", reader)

    cfg = await settings_file.save(settings_file.change({}, {"budget": {"enabled": False}}))
    assert cfg.budget.enabled is False
    assert config.CONFIG is cfg and reader.CONFIG is cfg and router.CONFIG is cfg
    assert settings_file.read() == {"budget": {"enabled": False, "hourly_usd": -1.0, "daily_usd": -1.0, "monthly_usd": -1.0}}


@pytest.mark.asyncio
async def test_a_saved_file_applies_at_start_and_a_bad_one_does_not(data_dir, running_config, monkeypatch):
    settings_file.write({"budget": {"enabled": False}})
    await settings_file.apply_saved()
    assert config.CONFIG.budget.enabled is False and config.CONFIG is not running_config

    config.install(running_config)

    def broken(*_a, **_k):
        raise ValueError("role 'vision' is local_only but ...")         # a hand-edit that does not build

    monkeypatch.setattr(config, "load_config", broken)
    await settings_file.apply_saved()                                     # the kernel still starts
    assert config.CONFIG is running_config


def test_the_view_says_what_is_in_effect_and_where_it_comes_from(tmp_path, data_dir):
    saved = settings_file.change({}, {
        "custom_api": {"label": "My lab", "base_url": "https://lab.example.com/v1"},
        "screen": {"ocr_watch": True},
    })
    shown = settings_file.view(load(tmp_path, saved), saved)
    assert shown["ollama_url"] == "http://127.0.0.1:11434"
    assert shown["budget"] == {"enabled": True, "hourly_usd": 0.5, "daily_usd": 2.0, "monthly_usd": 20.0}
    assert shown["custom_api"]["label"] == "My lab"
    assert shown["screen"] == {"task_guide": False, "ocr_watch": True}
    assert shown["saved"] == ["custom_api", "screen"] and shown["problem"] is None
    assert shown["file"] == str(data_dir / "settings.json")


# -- over the WebSocket -------------------------------------------------------------


def test_settings_set_saves_applies_and_tells_every_window(data_dir, running_config, monkeypatch):
    from fastapi.testclient import TestClient

    import app

    class FakeRouter:
        configs: list = []

        async def reconfigure(self, cfg):
            self.configs.append(cfg)
            return False

    rt = FakeRouter()
    monkeypatch.setattr(router, "get_router", lambda: rt)

    async def model_list(_rt, **_kw):
        return {"local": []}

    monkeypatch.setattr(listing, "model_list", model_list)
    monkeypatch.setattr(hub, "driver", None)
    monkeypatch.setattr(hub, "shutdown_event", asyncio.Event())

    def until(ws, kind):
        while True:
            msg = ws.receive_json()
            if msg["type"] == kind:
                return msg

    client = TestClient(app.app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"v": 1, "type": "settings_set", "data": {"ollama_url": "http://10.0.0.2:11434"}})
        refused = until(ws, "settings")["data"]
        assert "this PC" in refused["problem"] and not settings_file.path().exists() and rt.configs == []

        ws.send_json({"v": 1, "type": "settings_set", "data": {"budget": {"enabled": True, "hourly_usd": 0.75, "daily_usd": None, "monthly_usd": 5}}})
        shown = until(ws, "settings")["data"]
        assert shown["problem"] is None and shown["budget"]["hourly_usd"] == 0.75 and shown["saved"] == ["budget"]
        until(ws, "model_list")
        assert rt.configs[-1].budget.hourly_usd == 0.75 and config.CONFIG.budget.hourly_usd == 0.75
        assert settings_file.read()["budget"]["monthly_usd"] == 5.0

        ws.send_json({"v": 1, "type": "settings_get", "data": {}})
        assert until(ws, "settings")["data"]["budget"]["daily_usd"] is None


# -- screen companions at start (FR-SC-1) -------------------------------------------


@pytest.mark.asyncio
async def test_screen_companions_set_to_start_turn_on_after_the_vision_check(tmp_path, monkeypatch, running_config):
    sent = []

    async def broadcast(frame):
        sent.append(frame)

    monkeypatch.setattr(hub, "broadcast", broadcast)
    saved = settings_file.change({}, {"screen": {"task_guide": True, "ocr_watch": True}})
    config.install(load(tmp_path, saved))
    task_guide.set_enabled(False)
    ocr_watch.set_active(False)
    try:
        async def blind():
            return "no vision model"

        monkeypatch.setattr(boot.ambient, "vision_problem", blind)
        await boot.start_screen_companions()
        assert not task_guide.enabled() and not ocr_watch.get_state().active   # stays off and says why
        assert sent[-1]["data"]["code"] == "vision_unavailable"

        async def sees():
            return None

        monkeypatch.setattr(boot.ambient, "vision_problem", sees)
        await boot.start_screen_companions()
        assert task_guide.enabled() and ocr_watch.get_state().active
        assert sent[-1]["type"] == "screen_companions"
    finally:
        task_guide.set_enabled(False)
        ocr_watch.set_active(False)


@pytest.mark.asyncio
async def test_by_default_nothing_watches_the_screen_at_start(monkeypatch):
    async def never():
        raise AssertionError("no vision check when nothing is set to start")

    monkeypatch.setattr(boot.ambient, "vision_problem", never)
    await boot.start_screen_companions()
    assert not task_guide.enabled() and not ocr_watch.get_state().active
