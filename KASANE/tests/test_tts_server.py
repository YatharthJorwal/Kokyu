"""GPT-SoVITS server lifecycle: health check and managed launch."""

import asyncio
import dataclasses

import pytest

import config
from audio import tts


def with_launch(**overrides):
    launch = {**dict(config.CONFIG.tts.gpt_sovits.launch), **overrides}
    sovits = dataclasses.replace(config.CONFIG.tts.gpt_sovits, launch=launch)
    return dataclasses.replace(config.CONFIG, tts=dataclasses.replace(config.CONFIG.tts, gpt_sovits=sovits))


def with_fallback(engine: str):
    return dataclasses.replace(config.CONFIG, tts=dataclasses.replace(config.CONFIG.tts, fallback_engine=engine))


def with_engine(engine: str):
    return dataclasses.replace(config.CONFIG, tts=dataclasses.replace(config.CONFIG.tts, engine=engine))


@pytest.mark.asyncio
async def test_health_is_false_for_pyttsx3(monkeypatch):
    monkeypatch.setattr(tts, "CONFIG", with_engine("pyttsx3"))
    assert await tts.health() is False


@pytest.mark.asyncio
async def test_health_checks_the_port(monkeypatch):
    monkeypatch.setattr(tts, "_port_open", lambda host, port, timeout=0.5: (host, port) == ("127.0.0.1", 9880))
    assert await tts.health() is True


@pytest.mark.asyncio
async def test_ensure_server_is_true_when_already_running(monkeypatch):
    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: True)
    assert await tts.ensure_server() is True


@pytest.mark.asyncio
async def test_ensure_server_respects_disabled_launch(monkeypatch):
    monkeypatch.setattr(tts, "CONFIG", with_launch(enabled=False))
    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: False)
    assert await tts.ensure_server() is False


@pytest.mark.asyncio
async def test_ensure_server_launches_and_waits(monkeypatch):
    opened = {"value": False}

    class FakeProcess:
        returncode = None

        def poll(self):
            return None

    def fake_launch():
        opened["value"] = True
        return FakeProcess()

    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: opened["value"])
    monkeypatch.setattr(tts, "_launch_gpt_sovits", fake_launch)
    monkeypatch.setattr(tts, "CONFIG", with_launch(enabled=True, startup_timeout_s=5))

    assert await tts.ensure_server() is True


@pytest.mark.asyncio
async def test_ensure_server_gives_up_when_the_process_dies(monkeypatch):
    class DeadProcess:
        returncode = 1

        def poll(self):
            return 1

    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: False)
    monkeypatch.setattr(tts, "_launch_gpt_sovits", lambda: DeadProcess())
    monkeypatch.setattr(tts, "CONFIG", with_launch(startup_timeout_s=5))

    assert await tts.ensure_server() is False


def test_launch_refuses_missing_paths(monkeypatch):
    monkeypatch.setattr(
        tts, "CONFIG", with_launch(python=r"C:\definitely\not\here\python.exe", enabled=True)
    )
    assert tts._launch_gpt_sovits() is None


def test_service_address_parsing():
    assert tts._service_address("http://127.0.0.1:9880/tts") == ("127.0.0.1", 9880)
    assert tts._service_address("http://localhost/tts") == ("localhost", 9880)


# ---- the kernel owns the server (D-060) ----------------------------------------


@pytest.fixture(autouse=True)
def _no_server_state(monkeypatch):
    monkeypatch.setattr(tts, "_starting", None)
    monkeypatch.setattr(tts, "_process", None)


class _Alive:
    returncode = None

    def __init__(self):
        self.killed = False

    def poll(self):
        return 1 if self.killed else None

    def kill(self):
        self.killed = True


@pytest.mark.asyncio
async def test_concurrent_callers_share_one_launch(monkeypatch):
    launches, up = [], {"value": False}

    def launch():
        launches.append(1)
        up["value"] = True
        return _Alive()

    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: up["value"])
    monkeypatch.setattr(tts, "_launch_gpt_sovits", launch)
    monkeypatch.setattr(tts, "CONFIG", with_launch(enabled=True, startup_timeout_s=5))
    assert await asyncio.gather(tts.ensure_server(), tts.ensure_server()) == [True, True]
    assert launches == [1]


@pytest.mark.asyncio
async def test_a_line_waits_briefly_while_our_server_is_still_loading(monkeypatch):
    polls = {"n": 0}

    def port_open(*a, **k):
        polls["n"] += 1
        return polls["n"] > 2

    async def sovits(text):
        return b"WAV-FROM-SOVITS"

    gate = asyncio.Event()
    monkeypatch.setattr(tts, "_starting", asyncio.ensure_future(gate.wait()))
    monkeypatch.setattr(tts, "_port_open", port_open)
    monkeypatch.setattr(tts, "_synthesize_gpt_sovits", sovits)
    monkeypatch.setattr(tts, "_synthesize_pyttsx3_sync", lambda t: pytest.fail("fell back to pyttsx3"))
    assert await tts.synthesize("hello") == b"WAV-FROM-SOVITS"
    gate.set()


@pytest.mark.asyncio
async def test_no_wait_when_nothing_is_starting(monkeypatch):
    waited = {"n": 0}

    async def fake_wait(*a, **k):
        waited["n"] += 1
        return False

    async def sovits(text):
        raise tts.TTSUnreachableError("down")

    monkeypatch.setattr(tts, "_wait_for_health", fake_wait)
    monkeypatch.setattr(tts, "_synthesize_gpt_sovits", sovits)
    monkeypatch.setattr(tts, "_synthesize_pyttsx3_sync", lambda t: b"PYTTSX3")
    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: False)
    monkeypatch.setattr(tts, "CONFIG", with_fallback("pyttsx3"))  # the opt-in placeholder voice
    assert await tts.synthesize("a") == b"PYTTSX3" and waited["n"] == 0


@pytest.mark.asyncio
async def test_stop_server_ends_only_the_server_we_started(monkeypatch):
    tts.stop_server()                       # nothing started: nothing to do
    process = _Alive()
    up = {"value": False}

    def launch():
        up["value"] = True
        return process

    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: up["value"])
    monkeypatch.setattr(tts, "_launch_gpt_sovits", launch)
    monkeypatch.setattr(tts, "CONFIG", with_launch(enabled=True, startup_timeout_s=5))
    assert await tts.ensure_server() is True
    tts.stop_server()
    assert process.killed


@pytest.mark.asyncio
async def test_a_server_already_running_is_used_not_launched(monkeypatch):
    monkeypatch.setattr(tts, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tts, "_launch_gpt_sovits", lambda: pytest.fail("must not launch a second server"))
    monkeypatch.setattr(tts, "CONFIG", with_launch(enabled=True))
    assert await tts.ensure_server() is True
    tts.stop_server()                       # not ours: left alone (no process recorded)
