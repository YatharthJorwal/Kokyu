"""Read aloud (D-097): she speaks each finished reply, in Chat and Roleplay. The
switch is kept in settings.json; GPT-SoVITS starts only while it is on; turned off,
replies go silent at once and the server stops after idle. Replaces D-061's voice mode."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
import base64
import dataclasses

import pytest
from fastapi.testclient import TestClient

import app
import boot
import companions
import config
import conversation
import hub
import settings_file
import turns
from audio import arbiter, read_aloud, stt, tts


@pytest.fixture
def voice(monkeypatch):
    seen: dict[str, list] = {"start": [], "preload": [], "stop": [], "status": []}
    result = {"up": True}

    async def ensure_server():
        seen["start"].append(1)
        return result["up"]

    async def preload():
        seen["preload"].append(1)

    monkeypatch.setattr(tts, "ensure_server", ensure_server)
    monkeypatch.setattr(tts, "stop_server", lambda: seen["stop"].append(1))
    monkeypatch.setattr(stt, "preload", preload)
    switch = read_aloud.READ_ALOUD

    async def listener(status):
        seen["status"].append((status["on"], status["state"]))

    switch.subscribe(listener)
    return switch, seen, result


async def idle_after(seconds):
    """In settings.json, like a user's override: Read aloud's own saves rebuild the config."""
    settings_file.write({"tts": {"idle_stop_s": seconds}})
    await settings_file.apply_saved()


async def settle(switch):
    if switch.loader.busy():
        await switch.loader._task


@pytest.mark.asyncio
async def test_off_at_first_then_on_starts_only_the_voice(voice):
    switch, seen, _ = voice
    assert switch.status() == {"on": False, "state": "idle", "message": None, "elapsed_s": None}
    await switch.set(True)
    await settle(switch)
    assert switch.on and seen["start"] == [1]
    assert seen["preload"] == []                         # speech-to-text is dictation's, on first use
    assert seen["status"][0] == (True, "idle") and seen["status"][-1] == (True, "ready")
    assert (True, "loading") in seen["status"]           # the window's "her voice is starting"
    await switch.set(True)                                # already up: nothing starts again
    await settle(switch)
    assert seen["start"] == [1]


@pytest.mark.asyncio
async def test_kept_in_settings_json_across_a_restart(voice):
    switch, _, _ = voice
    await switch.set(True)
    await settle(switch)
    assert settings_file.read()["tts"] == {"read_aloud": True}
    # a restart: config.yaml says off, settings.json wins (D-070)
    config.install(dataclasses.replace(config.CONFIG, tts=dataclasses.replace(config.CONFIG.tts, read_aloud=False)))
    assert not read_aloud.ReadAloud().on
    await settings_file.apply_saved()
    assert read_aloud.ReadAloud().on
    await switch.set(False)
    assert settings_file.read()["tts"] == {"read_aloud": False} and not switch.on


@pytest.mark.asyncio
async def test_a_failed_start_is_shown_and_turning_it_on_again_retries(voice):
    switch, seen, result = voice
    result["up"] = False
    await switch.set(True)
    await settle(switch)
    status = switch.status()
    assert status["state"] == "failed" and "logs/gpt_sovits.log" in status["message"]
    assert await switch.ready() is False and seen["start"] == [1]   # a reply does not relaunch it
    result["up"] = True
    await switch.set(True)                                # Try again
    await settle(switch)
    assert switch.status()["state"] == "ready" and seen["start"] == [1, 1]


@pytest.mark.asyncio
async def test_ready_waits_while_the_voice_wakes_up(voice, monkeypatch):
    switch, seen, _ = voice
    gate = asyncio.Event()

    async def slow_start():
        seen["start"].append(1)
        await gate.wait()
        return True

    monkeypatch.setattr(tts, "ensure_server", slow_start)
    await switch.set(True)
    waiting = asyncio.create_task(switch.ready())
    await asyncio.sleep(0.01)
    assert not waiting.done() and switch.status()["state"] == "loading"
    gate.set()
    assert await waiting is True and seen["start"] == [1]


@pytest.mark.asyncio
async def test_ready_is_false_while_off(voice):
    switch, seen, _ = voice
    assert await switch.ready() is False and seen["start"] == []


@pytest.mark.asyncio
async def test_off_is_silent_at_once_and_stops_the_server_only_after_idle(voice):
    switch, seen, _ = voice
    await idle_after(0.05)
    await switch.set(True)
    await settle(switch)
    await switch.set(False)
    assert not switch.on and seen["stop"] == []          # not yet: a quick on/off must not reload
    await switch.set(True)                                # back on before the idle time: kept
    await asyncio.sleep(0.1)
    assert seen["stop"] == [] and seen["start"] == [1]
    await switch.set(False)
    await asyncio.sleep(0.1)
    assert seen["stop"] == [1]
    assert switch.status() == {"on": False, "state": "idle", "message": None, "elapsed_s": None}
    await switch.set(True)                                # after the stop, on starts it again
    await settle(switch)
    assert seen["start"] == [1, 1]


@pytest.mark.asyncio
async def test_off_before_anything_started_has_nothing_to_stop(voice):
    switch, seen, _ = voice
    await idle_after(0)
    await switch.set(False)
    await asyncio.sleep(0.02)
    assert seen["stop"] == [] and seen["start"] == []


@pytest.mark.asyncio
async def test_boot_wakes_the_voice_only_if_read_aloud_was_left_on(voice):
    switch, seen, _ = voice
    await boot.start_read_aloud()
    await settle(switch)
    assert seen["start"] == []
    await switch.set(True)
    await settle(switch)
    switch.loader.reset()
    await boot.start_read_aloud()
    await settle(switch)
    assert seen["start"] == [1, 1]


@pytest.mark.asyncio
async def test_nothing_is_synthesized_while_off(voice, monkeypatch):
    switch, _, _ = voice

    async def synth(text, voice_params=None):
        return b"WAV"

    monkeypatch.setattr(tts, "synthesize", synth)
    monkeypatch.setattr(companions, "voice_of", lambda ws: None)
    assert await turns.synthesize_for(object(), "hello") == b""
    await switch.set(True)
    await settle(switch)
    assert await turns.synthesize_for(object(), "hello") == b"WAV"


class SpeakSocket:
    def __init__(self):
        self.frames = []

    async def send_json(self, frame):
        self.frames.append(frame)

    def spoken(self):
        return [f["data"]["text"] for f in self.frames if f["type"] == "speak"]


@pytest.fixture
def spoken_aloud(voice, monkeypatch):
    switch, _, _ = voice
    voices = []

    async def synth(text, voice_params=None):
        voices.append(voice_params)
        return b"WAV:" + text.encode()

    monkeypatch.setattr(tts, "synthesize", synth)
    return switch, voices


REPLY = (
    "Fine — here's your list. [teasing]\n\n"
    "| Fruit | Colour |\n|---|---|\n| Apple | Red |\n\n"
    "```py\nprint('no')\n```\n"
    "You're welcome."
)


@pytest.mark.asyncio
async def test_a_finished_reply_is_spoken_through_speakable_in_the_given_voice(spoken_aloud):
    switch, voices = spoken_aloud
    await switch.set(True)
    await settle(switch)
    ws = SpeakSocket()
    luna = tts.VoiceParams(ref_audio_path="luna.wav", prompt_text="hi", prompt_lang="en", text_lang="en")
    await turns.speak_reply(ws, REPLY, "chat", luna)
    assert ws.spoken() == ["Fine, here's your list.", "You are welcome."]
    assert voices == [luna, luna]
    first = next(f for f in ws.frames if f["type"] == "speak")
    assert base64.b64decode(first["data"]["audio_b64"]) == b"WAV:Fine, here's your list."
    assert arbiter.ARBITER.state == arbiter.IDLE          # the one mouth is free again


@pytest.mark.asyncio
async def test_a_roleplay_reply_speaks_only_her_dialogue(spoken_aloud):
    switch, _ = spoken_aloud
    await switch.set(True)
    await settle(switch)
    ws = SpeakSocket()
    await turns.speak_reply(ws, '*She smiles.* "Morning. Sleep well?" *stretches* [happy]', "roleplay", None)
    assert ws.spoken() == ["Morning.", "Sleep well?"]


@pytest.mark.asyncio
async def test_nothing_is_spoken_while_off_or_when_nothing_is_speakable(spoken_aloud, voice):
    switch, voices = spoken_aloud
    _, seen, _ = voice
    ws = SpeakSocket()
    await turns.speak_reply(ws, "Hello there.", "chat", None)
    assert ws.frames == [] and seen["start"] == []         # off: the voice is not even started
    await switch.set(True)
    await settle(switch)
    await turns.speak_reply(ws, "```\ncode only\n```", "chat", None)
    await turns.speak_reply(ws, "*She waves.*", "roleplay", None)
    assert ws.frames == [] and voices == []


@pytest.mark.asyncio
async def test_a_dead_voice_backend_leaves_the_reply_as_text(spoken_aloud, monkeypatch):
    switch, _ = spoken_aloud
    await switch.set(True)
    await settle(switch)

    async def down(text, voice_params=None):
        raise tts.TTSUnreachableError("down")

    monkeypatch.setattr(tts, "synthesize", down)
    ws = SpeakSocket()
    await turns.speak_reply(ws, "Hello there. How are you?", "chat", None)
    # clips with no audio: the window skips them (FR-V-7); nothing raised
    assert all(f["data"]["audio_b64"] == "" for f in ws.frames)
    assert arbiter.ARBITER.state == arbiter.IDLE


def _until(ws, type_):
    while True:
        msg = ws.receive_json()
        if msg.get("type") == type_:
            return msg


def test_a_window_sees_read_aloud_off_and_turns_it_on(voice, monkeypatch):
    switch, seen, _ = voice
    monkeypatch.setattr(hub, "shutdown_event", asyncio.Event())
    monkeypatch.setattr(hub, "driver", None)
    monkeypatch.setattr(conversation, "_manager", None)
    with TestClient(app.app) as client, client.websocket_connect("/ws") as ws:
        first = _until(ws, "read_aloud_status")
        assert first["data"] == {"on": False, "state": "idle", "message": None, "elapsed_s": None}
        assert seen["start"] == []                        # opening the window started nothing
        ws.send_json({"v": 1, "type": "read_aloud", "data": {"on": True}})
        while _until(ws, "read_aloud_status")["data"]["state"] != "ready":
            pass
    assert seen["start"] == [1]


# -- the session: spoken after the turn, silenced by Stop, a new line or another thread --


def _session(mode="chat"):
    from types import SimpleNamespace

    from session import Session

    session = Session.__new__(Session)
    session.ws = SimpleNamespace(state=SimpleNamespace(waifu=None))
    session.thread = SimpleNamespace(id="t1", mode=mode, scenario={}, model_ref=None, effort=None)
    session.turn = session.speech = None
    session.pending_waifu = None
    session.history, session.temp, session.temp_flags, session.unprompted = [], False, [], []
    session.story_summary = ""
    return session


@pytest.fixture
def scripted(monkeypatch):
    """run_turn answers at once; speak_reply holds until released, recording what it got."""
    said, release = [], asyncio.Event()

    async def run_turn(ws, history, user_text, *a, mode="chat", **k):
        return f"Reply to {user_text}."

    async def speak_reply(ws, text, mode, voice):
        said.append((text, mode))
        await release.wait()

    monkeypatch.setattr(turns, "run_turn", run_turn)
    monkeypatch.setattr(turns, "speak_reply", speak_reply)
    return said, release


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["chat", "roleplay"])
async def test_the_session_reads_the_finished_reply_in_the_threads_mode(scripted, read_aloud_on, mode):
    said, release = scripted
    session = _session(mode)
    await session.start_turn("hi", on_finished=None)
    await session.turn
    await asyncio.sleep(0)
    assert said == [("Reply to hi.", mode)] and not session.speech.done()
    assert not session.busy                     # she can be sent a new line while she speaks
    release.set()
    await session.speech


@pytest.mark.asyncio
async def test_nothing_is_read_while_read_aloud_is_off(scripted):
    said, _ = scripted
    session = _session()
    await session.start_turn("hi", on_finished=None)
    await session.turn
    assert said == [] and session.speech is None


@pytest.mark.asyncio
async def test_stop_and_a_new_line_silence_the_reply_being_read(scripted, read_aloud_on):
    said, _ = scripted
    session = _session()
    await session.start_turn("one", on_finished=None)
    await session.turn
    await asyncio.sleep(0)
    first = session.speech
    await session.start_turn("two", on_finished=None)    # a new line: the old reply stops
    assert first.cancelled()
    await session.turn
    await asyncio.sleep(0)
    second = session.speech
    await session.on_stop(None)                          # Stop silences her too (FR-C-2)
    assert second.cancelled() and session.speech is None
    assert said == [("Reply to one.", "chat"), ("Reply to two.", "chat")]


@pytest.mark.asyncio
async def test_turning_read_aloud_off_silences_her_at_once(scripted, read_aloud_on, voice, monkeypatch):
    said, _ = scripted
    session = _session()
    monkeypatch.setattr(hub, "drives", lambda ws: True)
    await session.start_turn("one", on_finished=None)
    await session.turn
    await asyncio.sleep(0)
    speaking = session.speech
    await session.on_read_aloud(SimpleNamespace(data=SimpleNamespace(on=False)))
    assert speaking.cancelled() and not read_aloud.READ_ALOUD.on


# -- one message read on request: her speaker button (D-099) -------------------------


@pytest.mark.asyncio
async def test_a_message_is_read_on_request_with_read_aloud_off_then_the_voice_idles(spoken_aloud, voice):
    switch, voices = spoken_aloud
    _, seen, _ = voice
    await idle_after(0.05)
    assert not switch.on
    ws = SpeakSocket()
    await turns.speak_reply(ws, "Fine — here it is. [teasing]", "chat", None, ref="m7")
    assert ws.spoken() == ["Fine, here it is."] and seen["start"] == [1]   # the voice started just for it
    assert (ws.frames[-1]["type"], ws.frames[-1]["data"]) == ("spoken", {"ref": "m7"})
    assert not switch.on                                                    # Read aloud stays off
    await asyncio.sleep(0.1)
    assert seen["stop"] == [1]                                              # and the voice goes idle again


@pytest.mark.asyncio
async def test_a_failed_start_is_retried_by_the_button_and_still_says_done(spoken_aloud, voice):
    _, _, result = voice
    result["up"] = False
    ws = SpeakSocket()
    await turns.speak_reply(ws, "Hello.", "chat", None, ref="m1")
    assert ws.spoken() == [] and [(f["type"], f["data"]) for f in ws.frames] == [("spoken", {"ref": "m1"})]
    result["up"] = True
    await turns.speak_reply(ws, "Hello.", "chat", None, ref="m1")
    assert ws.spoken() == ["Hello."]


@pytest.mark.asyncio
async def test_a_roleplay_message_read_on_request_speaks_only_dialogue(spoken_aloud):
    ws = SpeakSocket()
    await turns.speak_reply(ws, '*She smiles.* "Hi there." *waves*', "roleplay", None, ref="m2")
    assert ws.spoken() == ["Hi there."]


@pytest.mark.asyncio
async def test_the_session_reads_a_message_in_its_speaker_s_voice_and_stops_on_request(monkeypatch, read_aloud_on):
    said, release = [], asyncio.Event()

    async def speak_reply(ws, text, mode, voice, *, ref=None):
        said.append((text, mode, voice, ref))
        await release.wait()

    monkeypatch.setattr(turns, "speak_reply", speak_reply)
    luna = SimpleNamespace(ref_audio_path="luna.wav", voice=SimpleNamespace(ref_text="hi", ref_lang="en"))
    session = _session("roleplay")
    session.registry = SimpleNamespace(get=lambda wid: luna if wid == "luna" else None)
    msg = SimpleNamespace(data=SimpleNamespace(ref="k1", text="*nods* \"Yes.\"", speaker_id="luna"))
    await session.on_speak_message(msg)
    await asyncio.sleep(0)
    [(text, mode, voice_params, ref)] = said
    assert (text, mode, ref) == ("*nods* \"Yes.\"", "roleplay", "k1")
    assert voice_params.ref_audio_path == "luna.wav"
    reading = session.speech
    await session.on_speak_message(SimpleNamespace(data=SimpleNamespace(ref="k2", text="Two.", speaker_id="gone")))
    assert reading.cancelled()                      # one reading at a time
    await session.on_speak_stop(SimpleNamespace(data=None))
    assert session.speech is None
    assert session.turn is None                      # Stop's job (a reply being written) is untouched
