"""D-125: the fallback model when the chosen one can't answer; D-126: the picker's API list."""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

import config
import settings_file
import turns
from audio import tts
from conversation import ConversationManager, Speaker, next_swipe
from senses import look_intent
from threads import ThreadStore
from waifu_fixtures import make_pack
from waifus import WaifuRegistry
from config import CONFIG
from kernel_fixtures import set_config
from provider_presets import popular_in
from router import listing
from router.discovery import ModelInfo

import router
from router.errors import RouteBlockedError
from router import decision as d
from test_chat_model import API, LOCAL, _temp_on, _until, kernel  # noqa: F401 -- kernel is a fixture
from test_listing import catalog


def _with_chat(monkeypatch, **chat):
    cfg = dataclasses.replace(CONFIG, chat=dataclasses.replace(CONFIG.chat, **chat))
    set_config(monkeypatch, cfg)
    monkeypatch.setattr(listing, "CONFIG", cfg)
    monkeypatch.setattr(router, "_router", None)   # no running router: no key or endpoint check
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
    # the card names both, the chosen model first: Retry asks it again (review #15)
    first, second = listing.label_for(API), listing.label_for("api:airouter/other/model")
    assert errors[-1]["message"].startswith(f"{first} couldn't answer, and neither could {second}.")


def test_a_fallback_that_could_only_be_refused_is_never_offered(monkeypatch):
    # review #3, #4: an API fallback needs a key and the active endpoint (D-059)
    _with_chat(monkeypatch, fallback_model_ref="api:airouter/other/model")
    assert turns.usable_fallback(API) == "api:airouter/other/model"        # no router yet: not checked
    rt = SimpleNamespace(api_key_present=True, api_id="airouter")
    monkeypatch.setattr(router, "_router", rt)
    assert turns.usable_fallback(API) == "api:airouter/other/model"
    rt.api_id = "openrouter"                                                # the user saved another endpoint's key
    assert turns.usable_fallback(API) is None
    rt.api_id, rt.api_key_present = "airouter", False
    assert turns.usable_fallback(API) is None
    _with_chat(monkeypatch, fallback_model_ref=None)
    monkeypatch.setattr(router, "_router", rt)
    assert turns.usable_fallback(API) == listing.local_ref()               # local: the window checks the list


@pytest.mark.asyncio
async def test_screen_remarks_never_reach_an_api_fallback(tmp_path, monkeypatch):
    # review #1: a local thread's Task Guide / OCR remark stays local when an API model takes over (FR-SC-3)
    _with_chat(monkeypatch, on_model_failure="auto", fallback_model_ref=API)
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha")
    waifu = WaifuRegistry(premade, tmp_path / "user").get("alpha")
    seen = {}

    async def local_down(role, messages, tools, **kwargs):
        if kwargs.get("model_ref") == LOCAL:
            raise RouteBlockedError(d.CLOUD_DISABLED, "Ollama is not running.", LOCAL)
        seen[kwargs.get("model_ref")] = " ".join(m["content"] for m in messages)
        yield {"type": "content", "text": "ok [neutral]"}

    async def nothing(*_a, **_k):
        return None

    async def silent(text, voice=None):
        return b""

    class Socket:
        state = SimpleNamespace(waifu=waifu)

        async def send_json(self, payload):
            pass

    monkeypatch.setattr(router, "stream_with_tools", local_down)
    monkeypatch.setattr(tts, "synthesize", silent)
    monkeypatch.setattr(look_intent, "maybe_look", nothing)
    monkeypatch.setattr(turns, "log_transcript_turn", nothing)
    history, unprompted = [{"role": "system", "content": "sys"}], []
    turns.record_unprompted(history, "Whoa, $4,210 in checking?", True, [], unprompted)
    await turns.run_turn(Socket(), history, "hm?", True, [], model_ref=LOCAL, unprompted=unprompted)
    assert API in seen and "$4,210" not in seen[API]


@pytest.mark.asyncio
async def test_the_fallback_note_belongs_to_the_reply_it_wrote(tmp_path):
    # review #2, #13: swiping shows each candidate's own "X answered: Y couldn't", or none
    manager = ConversationManager(ThreadStore(tmp_path / "threads.db"))
    t = await manager.new_thread(waifu_id="alpha")
    alpha = Speaker("alpha", "Alpha")
    _, own = await manager.record_exchange(t.id, "hi", "mine", speaker=alpha, model_ref="api:x/Y")
    _, stand_in = await manager.record_exchange(
        t.id, "hi", "theirs", speaker=alpha, model_ref="local:ollama/X", reply_meta={**next_swipe(own), "instead_of": "api:x/Y"}
    )
    back = await manager.swipe_to(stand_in, 0)
    assert back.model_ref == "api:x/Y" and "instead_of" not in back.meta
    forward = await manager.swipe_to(back, 1)
    assert forward.model_ref == "local:ollama/X" and forward.meta["instead_of"] == "api:x/Y"
    _, again = await manager.record_exchange(t.id, "hi", "mine again", speaker=alpha, model_ref="api:x/Y", reply_meta=next_swipe(forward))
    assert "instead_of" not in again.meta
    assert (await manager.swipe_to(again, 1)).meta["instead_of"] == "api:x/Y"


def test_a_hand_edited_chat_section_never_breaks_the_model_list():
    # review #5: the wrong shapes fall back to the defaults with a warning
    cfg = config.load_config(overlay={"chat": {"api_models": ["openai/gpt-6"], "on_model_failure": "sometimes", "fallback_model_ref": "qwen"}}, quiet=True)
    assert cfg.chat.api_models == {} and cfg.chat.on_model_failure == "ask" and cfg.chat.fallback_model_ref is None
    cfg = config.load_config(overlay={"chat": {"api_models": {"airouter": ["a/b", 3], "openrouter": "x"}}}, quiet=True)
    assert cfg.chat.api_models == {"airouter": ["a/b", "3"]}
    assert listing.listed_ids(["a/b", "c/d"], "airouter", cfg) == {"a/b"}


# -- the picker's API list (D-126) ----------------------------------------------


def test_popular_sets_match_ids_with_or_without_the_vendor():
    ids = ["anthropic/claude-sonnet-5.5", "deepseek-chat", "vendor/unknown"]
    found = popular_in(ids)
    assert found["Popular"] == ["anthropic/claude-sonnet-5.5", "deepseek-chat"]
    assert "Strongest" not in found                                  # a set the endpoint has nothing of is left out


def test_a_new_release_replaces_the_older_one_in_its_set_on_any_endpoint():
    # D-127: families, not fixed ids, so the sets follow what the providers ship
    old = ["anthropic/claude-sonnet-5.5", "openai/gpt-5.4-mini"]
    assert popular_in(old)["Popular"] == ["anthropic/claude-sonnet-5.5"]
    new = old + ["anthropic/claude-sonnet-6", "anthropic/claude-sonnet-6-fast", "anthropic/claude-sonnet-6-preview", "openai/gpt-5.6-mini"]
    assert popular_in(new)["Popular"] == ["anthropic/claude-sonnet-6"]            # not its speed tier or preview
    assert popular_in(new)["Budget"] == ["openai/gpt-5.6-mini"]
    # OpenRouter-style ids and a bare DeepSeek id both count; 4 is newer than 3.8
    assert popular_in(["qwen/qwen3.8-max", "qwen/qwen4-max"])["Strongest"] == ["qwen/qwen4-max"]
    # the user's test round: Gemini's Pro line ships as a preview; a stable one of the same version wins
    gem = ["google/gemini-2.5-pro", "google/gemini-3.1-pro-preview", "google/gemini-3-pro-image"]
    assert popular_in(gem)["Strongest"] == ["google/gemini-3.1-pro-preview"]
    assert popular_in(gem + ["google/gemini-3.1-pro"])["Strongest"] == ["google/gemini-3.1-pro"]
    assert popular_in(["meta/llama-3.3-70b", "meta/llama-4-scout", "meta/llama-4-maverick"])["Budget"] == ["meta/llama-4-scout"]
    # review #8-#11: named tiers (OpenAI, Gemini 4), never a date, a bare DeepSeek id only on DeepSeek
    gpt = ["openai/gpt-5.4-mini", "openai/gpt-5.5-pro", "openai/gpt-6-luna", "openai/gpt-6.2-sol", "openai/gpt-6.2-astra", "openai/gpt-6.2-sol-fast"]
    assert [popular_in(gpt)[k] for k in ("Popular", "Budget", "Strongest")] == [["openai/gpt-6.2-sol"], ["openai/gpt-6-luna"], ["openai/gpt-6.2-astra"]]
    gem = ["google/gemini-3.8-flash", "google/gemini-4-hydrogen", "google/gemini-4-neon", "google/gemini-4-neon-fast"]
    assert popular_in(gem)["Popular"] == ["google/gemini-4-hydrogen"] and popular_in(gem)["Strongest"] == ["google/gemini-4-neon"]
    assert popular_in(["mistralai/mistral-large-2411", "mistral/mistral-large-4"])["Popular"] == ["mistral/mistral-large-4"]
    assert "deepseek/deepseek-chat" not in popular_in(["deepseek/deepseek-chat", "deepseek/deepseek-v4-flash"])["Popular"]
    assert popular_in(["deepseek-chat", "deepseek-reasoner"])["Strongest"] == ["deepseek-reasoner"]


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
