"""FR-W-3 / FR-S-5: a waifu is a prompt and a voice. Nothing else about a turn may depend on her,
in a chat thread or a roleplay thread alike (FR-MODE-2, D-074: the mode belongs to the thread)."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

import companions
import prompting
import router
import turns
from audio import tts
from waifu_fixtures import make_pack
from waifus import WaifuRegistry


class FakeWebSocket:
    def __init__(self, waifu):
        self.payloads: list[dict] = []
        self.state = SimpleNamespace(waifu=waifu)

    async def send_json(self, payload):
        self.payloads.append(payload)


@pytest.fixture
def registry(tmp_path):
    premade = tmp_path / "premade"
    make_pack(premade, "alpha", name="Alpha", ref_text="alpha transcript")
    make_pack(premade, "beta", name="Beta", ref_text="beta transcript")
    return WaifuRegistry(premade, tmp_path / "user")


CARD = {"title": "Rain", "setting": "A station at night.", "opening": "*She waves.* Over here!"}


async def _run_turn_as(waifu, monkeypatch, user_text="Tell me about your day.", *, mode="chat", scenario=None):
    calls, voices = [], []

    async def fake_stream(role, messages, tools, **kwargs):
        calls.append({"role": role, "messages": [dict(m) for m in messages], "tools": list(tools), "kwargs": dict(kwargs)})
        yield {"type": "content", "text": "It was fine. How about yours? [happy]"}

    async def fake_synth(text, voice=None):
        voices.append(voice)
        return b"RIFF"

    async def no_log(*_a, **_k):
        return None

    monkeypatch.setattr(router, "stream_with_tools", fake_stream)
    monkeypatch.setattr(tts, "synthesize", fake_synth)
    monkeypatch.setattr(turns, "log_transcript_turn", no_log)
    ws = FakeWebSocket(waifu)
    history = [{"role": "system", "content": companions.system_message(waifu, mode=mode, scenario=scenario)}]
    # Temp Chat: no memory reads or writes. The mode is the thread's, the same for both companions.
    reply = await turns.run_turn(ws, history, user_text, True, [], mode=mode)
    # Read aloud (D-097), as the session does it: in the voice of who wrote the reply.
    await turns.speak_reply(ws, reply, mode, companions.voice_of(ws))
    return calls, voices, history


@pytest.mark.parametrize(("mode", "scenario"), [("chat", None), ("roleplay", CARD), ("roleplay", None)])
@pytest.mark.asyncio
async def test_a_turn_differs_between_waifus_only_in_persona_text_and_voice(registry, monkeypatch, mode, scenario, read_aloud_on):
    a_calls, a_voices, a_hist = await _run_turn_as(registry.get("alpha"), monkeypatch, mode=mode, scenario=scenario)
    b_calls, b_voices, b_hist = await _run_turn_as(registry.get("beta"), monkeypatch, mode=mode, scenario=scenario)

    assert len(a_calls) == len(b_calls) == 1
    a, b = a_calls[0], b_calls[0]
    assert a["role"] == b["role"]                      # same router role -> same model decision
    assert a["tools"] == b["tools"]                    # same tools offered
    assert a["kwargs"] == b["kwargs"]                  # same privacy class, trust, options
    assert a["messages"][1:] == b["messages"][1:]      # history, hints and the user message identical
    assert a["messages"][0] != b["messages"][0]        # ...only the system message differs
    # FR-MODE-2: the layers after the persona are the thread's, identical for both companions
    a_system, b_system = a["messages"][0]["content"], b["messages"][0]["content"]
    alpha, beta = registry.get("alpha").prompt.rstrip(), registry.get("beta").prompt.rstrip()
    assert a_system.startswith(alpha) and b_system.startswith(beta)
    assert a_system.removeprefix(alpha) == b_system.removeprefix(beta)
    layer = prompting.CHAT_LAYER if mode == "chat" else prompting.ROLEPLAY_LAYER
    assert layer in a_system and layer in b_system
    if mode == "chat":
        assert a_system.endswith(prompting.APP_ADDENDUM + " " + prompting.TOOL_GUIDANCE)
    else:
        assert a_system.endswith(prompting.APP_ADDENDUM) and prompting.TOOL_GUIDANCE not in a_system
        assert (prompting.SCENARIO_HEADING in a_system) == bool(scenario)
        assert a["tools"] == [] and a["role"] == "chat"   # FR-MODE-4: no tools, same router role
    # Read aloud is on here and still adds no note: it never changes what she writes (D-097)
    a_notes = [m["content"] for m in a["messages"][1:] if m["role"] == "system"]
    assert a_notes == []
    assert a["messages"][0]["content"].startswith("You are Alpha") and b["messages"][0]["content"].startswith("You are Beta")

    assert a_voices and b_voices
    assert {v.prompt_text for v in a_voices} == {"alpha transcript"}
    assert {v.prompt_text for v in b_voices} == {"beta transcript"}
    assert a_hist[1:] and b_hist[1:] and a_hist[1:] == b_hist[1:]   # what was stored in history is identical too


@pytest.mark.asyncio
async def test_switching_mid_conversation_keeps_history_model_and_tools(registry, monkeypatch):
    waifu_a, waifu_b = registry.get("alpha"), registry.get("beta")
    calls, _voices, history = await _run_turn_as(waifu_a, monkeypatch, "First question.")
    first_system = history[0]["content"]

    ws = FakeWebSocket(waifu_a)
    monkeypatch.setenv("KOKYU_DATA_DIR", str(registry._user_dir.parent / "data"))
    await companions.apply_switch(ws, history, registry, "beta")
    assert history[0]["content"] != first_system
    assert [m["content"] for m in history[1:]][0] == "First question."   # the conversation survived

    calls2 = []

    async def fake_stream(role, messages, tools, **kwargs):
        calls2.append({"role": role, "tools": list(tools), "kwargs": dict(kwargs)})
        yield {"type": "content", "text": "Sure. [neutral]"}

    monkeypatch.setattr(router, "stream_with_tools", fake_stream)
    ws2 = FakeWebSocket(waifu_b)
    await turns.run_turn(ws2, history, "Second question.", True, [])
    assert calls2[0]["role"] == calls[0]["role"] and calls2[0]["tools"] == calls[0]["tools"] and calls2[0]["kwargs"] == calls[0]["kwargs"]


def test_the_turn_runner_never_branches_on_a_waifu():
    """Structural guard: persona and voice enter through _system_message/_synthesize_for only;
    Read aloud gets the voice handed in (D-097)."""
    for fn in (turns.run_turn, turns.speak_reply):
        assert "waifu" not in inspect.getsource(fn).lower(), fn


def test_the_router_has_no_waifu_input():
    for fn in (router.decide, router.Router.complete, router.Router.stream_with_tools, router.stream_with_tools):
        assert not any("waifu" in name or "persona" in name for name in inspect.signature(fn).parameters), fn


def test_model_request_has_no_waifu_field():
    from router.types import ModelRequest

    assert not any("waifu" in f or "persona" in f for f in ModelRequest.__dataclass_fields__)
