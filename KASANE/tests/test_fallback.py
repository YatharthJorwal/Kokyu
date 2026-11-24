"""D-125: the fallback model when the chosen one can't answer; D-126: the picker's API list."""
from __future__ import annotations

import dataclasses

import pytest

import settings_file
from config import CONFIG
from kernel_fixtures import set_config
from provider_presets import popular_in
from router import listing
from router.discovery import ModelInfo

import router
from router.errors import RouteBlockedError
from router import decision as d
from test_chat_model import API, _temp_on, _until, kernel  # noqa: F401 -- kernel is a fixture
from test_listing import catalog


def _with_chat(monkeypatch, **chat):
    cfg = dataclasses.replace(CONFIG, chat=dataclasses.replace(CONFIG.chat, **chat))
    set_config(monkeypatch, cfg)
    monkeypatch.setattr(listing, "CONFIG", cfg)
    return cfg


def _send(ws, text="hi"):
    ws.send_json({"v": 1, "type": "send", "data": {"text": text}})
    return _until(ws, "turn_done")


# -- the fallback (D-125) -----------------------------------------------------


def test_the_fallback_is_the_local_model_unless_settings_name_one(monkeypatch):
    local = listing.local_ref()
    assert listing.fallback_ref(API) == local
    assert listing.fallback_ref(local) is None                      # the same model would only fail again
    _with_chat(monkeypatch, fallback_model_ref="api:airouter/vendor/cheap")
    assert listing.fallback_ref(API) == "api:airouter/vendor/cheap"


def test_on_auto_the_fallback_answers_at_once_and_says_why(kernel, monkeypatch):
    client, calls = kernel
    _with_chat(monkeypatch, on_model_failure="auto")
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)   # keeps memory, and so Ollama, out of the test
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": API}})
        _until(ws, "thread_updated")
        done, seen = _send(ws)
        ws.send_json({"v": 1, "type": "thread_open", "data": {"id": done["thread"]}})
        reopened, _ = _until(ws, "thread_opened")
    notes = [m["data"] for m in seen if m["type"] == "error"]
    assert [n["code"] for n in notes] == ["model_fallback"]          # no failure card: it answered
    assert "is answering instead" in notes[0]["message"]
    assert [c["model_ref"] for c in calls] == [API, listing.local_ref()]
    assert done["data"]["text"].startswith("fine")
    reply = reopened["data"]["messages"][-1]
    assert reply["model_ref"] == listing.local_ref() and reply["meta"]["instead_of"] == API
    assert reopened["data"]["thread"]["model_ref"] == API             # the thread keeps its model


def test_on_ask_the_card_offers_the_fallback_and_the_button_answers_once(kernel):
    client, calls = kernel
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)   # keeps memory, and so Ollama, out of the test
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": API}})
        _until(ws, "thread_updated")
        ws.send_json({"v": 1, "type": "send", "data": {"text": "hi"}})
        err, _ = _until(ws, "error")
        _until(ws, "turn_done")
        ws.send_json({"v": 1, "type": "regenerate", "data": {"model_ref": err["data"]["fallback"]}})
        done, seen = _until(ws, "turn_done")
        _send(ws, "again")                                          # the next line asks the thread's model
    assert err["data"]["actions"] == ["retry", "switch_model", "fallback"]
    assert err["data"]["fallback"] == listing.local_ref()
    assert not [m for m in seen if m["type"] == "error"] and done["data"]["text"].startswith("fine")
    assert [c["model_ref"] for c in calls] == [API, listing.local_ref(), API]


def test_a_failed_fallback_is_not_offered_again(kernel, monkeypatch):
    client, _ = kernel
    _with_chat(monkeypatch, on_model_failure="auto", fallback_model_ref="api:airouter/other/model")

    async def no_api(role, messages, tools, **kwargs):
        raise RouteBlockedError(d.CLOUD_DISABLED, "The API model isn't available.", kwargs.get("model_ref"))
        yield  # an async generator, like the real one

    monkeypatch.setattr(router, "stream_with_tools", no_api)
    with client.websocket_connect("/ws") as ws:
        _until(ws, "thread_opened")
        _temp_on(ws)
        ws.send_json({"v": 1, "type": "set_model", "data": {"model_ref": API}})
        _until(ws, "thread_updated")
        _, seen = _send(ws)
    errors = [m["data"] for m in seen if m["type"] == "error"]
    # the fallback is tried once, then the card, with no second offer
    assert [e["code"] for e in errors] == ["model_fallback", "model_blocked"]
    assert "fallback" not in errors[-1]["actions"]


# -- the picker's API list (D-126) ----------------------------------------------


def test_popular_sets_match_ids_with_or_without_the_vendor():
    ids = ["anthropic/claude-sonnet-5.5", "deepseek-chat", "vendor/unknown"]
    found = popular_in(ids)
    assert found["Popular"] == ["anthropic/claude-sonnet-5.5", "deepseek-chat"]
    assert "Strongest" not in found                                  # a set the endpoint has nothing of is left out


def test_the_picker_lists_the_popular_models_then_the_users_own(tmp_path, monkeypatch):
    cat = catalog(tmp_path, [ModelInfo("anthropic/claude-sonnet-5.5"), ModelInfo("vendor/odd-1"), ModelInfo("vendor/odd-2")])
    rows = listing.api_rows(cat, key_present=True)
    assert {r["full"]: r["listed"] for r in rows} == {"anthropic/claude-sonnet-5.5": True, "vendor/odd-1": False, "vendor/odd-2": False}
    cfg = _with_chat(monkeypatch, api_models={"airouter": ["vendor/odd-2", "gone/model"]})
    rows = listing.api_rows(cat, key_present=True, cfg=cfg)
    assert [r["full"] for r in rows if r["listed"]] == ["vendor/odd-2"]
    # an endpoint the sets know nothing of lists everything, so a custom one is never empty
    assert listing.listed_ids(["a/b", "c"], "custom_x", CONFIG) == {"a/b", "c"}


def test_settings_save_the_fallback_and_the_list_and_refuse_nonsense():
    out = settings_file.change({}, {"fallback": {"model_ref": API, "mode": "auto"}})
    assert out["chat"] == {"fallback_model_ref": API, "on_model_failure": "auto"}
    out = settings_file.change(out, {"fallback": {"model_ref": None, "mode": "ask"}})
    assert out["chat"] == {"on_model_failure": "ask"}
    out = settings_file.change(out, {"api_models": {"endpoint": "airouter", "models": ["a/b", "a/b", " c "]}})
    assert out["chat"]["api_models"] == {"airouter": ["a/b", "c"]}
    out = settings_file.change(out, {"api_models": {"endpoint": "airouter", "models": None}})
    assert "api_models" not in out["chat"]
    with pytest.raises(settings_file.SettingsError):
        settings_file.change({}, {"api_models": {"endpoint": "../x", "models": []}})
    with pytest.raises(settings_file.SettingsError):
        settings_file.change({}, {"api_models": {"endpoint": "airouter", "models": ["x" * 201]}})
