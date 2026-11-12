"""Per-waifu voice parameters, opt-in fallback and pre-warm (FR-V-1, FR-V-7, FR-S-3, D-006)."""
from __future__ import annotations

import dataclasses

import pytest

import config
from audio import tts

LUNA = tts.VoiceParams(ref_audio_path="C:/a/luna.wav", prompt_text="luna transcript", prompt_lang="en", text_lang="en")
YURI = tts.VoiceParams(ref_audio_path="C:/a/yuri.wav", prompt_text="yuri transcript", prompt_lang="en", text_lang="en")


class _Response:
    status_code = 200
    headers = {"content-type": "audio/wav"}
    content = b"WAV"
    text = ""


def _fake_client(sent: list[dict]):
    class Client:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json):
            sent.append({"url": url, **json})
            return _Response()
    return Client


def _cfg(**tts_overrides):
    return dataclasses.replace(config.CONFIG, tts=dataclasses.replace(config.CONFIG.tts, **tts_overrides))


@pytest.mark.asyncio
async def test_request_carries_the_speaking_waifus_clip_and_transcript(monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(tts.httpx, "AsyncClient", _fake_client(sent))
    assert await tts.synthesize("hello", LUNA) == b"WAV"
    assert sent[0]["ref_audio_path"] == "C:/a/luna.wav"
    assert sent[0]["prompt_text"] == "luna transcript"
    assert sent[0]["text"] == "hello" and sent[0]["prompt_lang"] == "en" and sent[0]["text_lang"] == "en"


@pytest.mark.asyncio
async def test_switching_waifus_changes_parameters_only(monkeypatch):
    """Back to back, no restart, no other request fields differ (D-006)."""
    sent: list[dict] = []
    monkeypatch.setattr(tts.httpx, "AsyncClient", _fake_client(sent))
    await tts.synthesize("same sentence", LUNA)
    await tts.synthesize("same sentence", YURI)
    differing = {k for k in sent[0] if sent[0][k] != sent[1][k]}
    assert differing == {"ref_audio_path", "prompt_text"}


@pytest.mark.asyncio
async def test_without_a_voice_the_legacy_config_clip_is_used(monkeypatch):
    sent: list[dict] = []
    sovits = dataclasses.replace(config.CONFIG.tts.gpt_sovits, ref_audio_path="C:/legacy.wav", prompt_text="legacy")
    monkeypatch.setattr(tts, "CONFIG", _cfg(gpt_sovits=sovits))
    monkeypatch.setattr(tts.httpx, "AsyncClient", _fake_client(sent))
    await tts.synthesize("hi")
    assert sent[0]["ref_audio_path"] == "C:/legacy.wav" and sent[0]["prompt_text"] == "legacy"


@pytest.mark.asyncio
async def test_backend_down_keeps_the_reply_text_only_by_default(monkeypatch):
    async def down(text, voice=None):
        raise tts.TTSUnreachableError("down")

    monkeypatch.setattr(tts, "_synthesize_gpt_sovits", down)
    monkeypatch.setattr(tts, "_synthesize_pyttsx3_sync", lambda t: pytest.fail("placeholder voice must be opt-in"))
    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: False)
    assert config.CONFIG.tts.fallback_engine == "none"
    with pytest.raises(tts.TTSUnreachableError):
        await tts.synthesize("hello", LUNA)


@pytest.mark.asyncio
async def test_placeholder_voice_only_when_opted_in(monkeypatch):
    async def down(text, voice=None):
        raise tts.TTSUnreachableError("down")

    monkeypatch.setattr(tts, "CONFIG", _cfg(fallback_engine="pyttsx3"))
    monkeypatch.setattr(tts, "_synthesize_gpt_sovits", down)
    monkeypatch.setattr(tts, "_synthesize_pyttsx3_sync", lambda t: b"PLACEHOLDER")
    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: False)
    assert await tts.synthesize("hello", LUNA) == b"PLACEHOLDER"


@pytest.mark.asyncio
async def test_prewarm_reports_whether_the_backend_answered(monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(tts.httpx, "AsyncClient", _fake_client(sent))
    assert await tts.prewarm(YURI) is True
    assert sent[0]["ref_audio_path"] == "C:/a/yuri.wav"

    async def down(text, voice=None):
        raise tts.TTSUnreachableError("down")

    monkeypatch.setattr(tts, "_synthesize_gpt_sovits", down)
    assert await tts.prewarm(YURI) is False


def test_install_dir_shorthand_derives_python_script_and_cwd(monkeypatch):
    """A path with a space ('GPT SoVITS') must survive: one argv element each (D-042)."""
    root = r"D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228"
    launch = {**dict(config.CONFIG.tts.gpt_sovits.launch), "enabled": True, "dir": root}
    sovits = dataclasses.replace(config.CONFIG.tts.gpt_sovits, launch=launch)
    monkeypatch.setattr(tts, "CONFIG", _cfg(gpt_sovits=sovits))
    monkeypatch.setattr(tts.os.path, "isfile", lambda p: True)
    seen = {}

    def popen(argv, cwd=None, **kw):
        seen["argv"], seen["cwd"] = argv, cwd
        return object()

    monkeypatch.setattr(tts.subprocess, "Popen", popen)
    assert tts._launch_gpt_sovits() is not None
    assert seen["cwd"] == root
    assert seen["argv"][0].endswith("python.exe") and root in seen["argv"][0]
    assert seen["argv"][1].endswith("api_v2.py") and root in seen["argv"][1]
    assert all(" " not in a or a.startswith("D:") for a in seen["argv"])  # spaces live only inside path elements


def test_no_machine_paths_in_default_config():
    launch = dict(config.CONFIG.tts.gpt_sovits.launch)
    assert launch["enabled"] is False
    assert not any(str(launch.get(k, "")) for k in ("dir", "python", "script", "cwd"))
