"""
TTS backends. `synthesize(text) -> bytes` (WAV) is the only thing turns.py
calls, regardless of which engine is active -- picked by config.yaml's
tts.engine, same pattern as the LLM's config-driven backend choice.

- "pyttsx3": Phase 1's placeholder. Drives whatever TTS engine the OS
  already has (SAPI5 on Windows) -- no model download, works immediately,
  sounds robotic. Also used as an automatic fallback if the configured
  engine is "gpt_sovits" but its API server can't be reached, so a
  turn never goes silent just because that server isn't running -- the
  real error goes to logs/kasane.log when this happens,
  so "wrong voice came out" is diagnosable instead of a silent mystery --
  see synthesize() below.
- "gpt_sovits": real cloned voice, via GPT-SoVITS's own API server
  (https://github.com/RVC-Boss/GPT-SoVITS) running as a separate local
  process -- not embedded here. Request/response shape confirmed by
  reading a real reference implementation (rayenfeng/riko_project) rather
  than assumed: POST {api_url} with
  {text, text_lang, ref_audio_path, prompt_text, prompt_lang}, raw WAV
  bytes back. ref_audio_path/prompt_text point at your reference clip and
  its exact transcript -- fill those into config.yaml's tts.gpt_sovits
  block once you have a clip you're happy with (see docs/MODELS.md).
"""

import asyncio
import logging
import os
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import pyttsx3

import paths
from config import CONFIG

log = logging.getLogger(__name__)


class TTSUnreachableError(Exception):
    """The configured TTS backend's server couldn't be reached or errored
    out. synthesize() catches this itself for the gpt_sovits engine and
    falls back to pyttsx3 rather than letting a turn go silent -- callers
    in turns.py don't need to handle this directly."""


@dataclass(frozen=True)
class VoiceParams:
    """One waifu's voice for one request: the zero-shot reference clip, its exact
    transcript and languages. Sent with EVERY request, so switching waifus changes
    parameters only: no weights, no reload (D-006, FR-V-1)."""

    ref_audio_path: str
    prompt_text: str
    prompt_lang: str = "en"
    text_lang: str = "en"


def _synthesize_pyttsx3_sync(text: str) -> bytes:
    # Re-initializing per call is a little wasteful but far more reliable
    # than reusing one pyttsx3 engine across calls, which is known to hang
    # on some SAPI5 setups after the first use.
    engine = pyttsx3.init()
    engine.setProperty("rate", 175)

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        engine.save_to_file(text, path)
        engine.runAndWait()
        with open(path, "rb") as f:
            return f.read()
    finally:
        engine.stop()
        try:
            os.remove(path)
        except OSError:
            pass


async def _synthesize_gpt_sovits(text: str, voice: VoiceParams | None = None) -> bytes:
    cfg = CONFIG.tts.gpt_sovits
    # `voice` is the speaking waifu's clip; without one the legacy config clip is used.
    payload = {
        "text": text,
        "text_lang": voice.text_lang if voice else cfg.text_lang,
        "ref_audio_path": voice.ref_audio_path if voice else cfg.ref_audio_path,
        "prompt_text": voice.prompt_text if voice else cfg.prompt_text,
        "prompt_lang": voice.prompt_lang if voice else cfg.prompt_lang,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            response = await client.post(cfg.api_url, json=payload)
            content_type = response.headers.get("content-type", "")
            log.info(
                f"gpt_sovits response: {response.status_code}, "
                f"content-type={content_type!r}, {len(response.content)} bytes",
            )
            if response.status_code >= 400:
                raise TTSUnreachableError(
                    f"{response.status_code} from {cfg.api_url}: {response.text[:300]!r}"
                )
            # A 200 with an empty body, or a body that isn't actually
            # audio (e.g. a JSON error message the server returned with
            # the wrong status code), used to get handed to the frontend
            # as if it were real audio -- caught here instead, so it goes
            # through the same pyttsx3 fallback an unreachable server
            # already does, rather than the frontend trying to play back
            # garbage. "audio" in content_type (not startswith) also
            # treats a missing/empty content-type as non-audio -- stricter
            # than allowing it through by default, confirmed correct
            # against GPT-SoVITS's real responses on the user's machine.
            if not response.content:
                raise TTSUnreachableError(f"empty response body from {cfg.api_url}")
            if "audio" not in content_type.lower():
                body_preview = response.text[:1000]
                log.info(f"gpt_sovits non-audio body: {body_preview!r}")
                raise TTSUnreachableError(
                    f"expected audio from {cfg.api_url}, got content-type "
                    f"{content_type!r}: {body_preview[:300]!r}"
                )
            return response.content
    except httpx.RequestError as exc:
        raise TTSUnreachableError(f"couldn't reach {cfg.api_url}: {exc}") from exc


def _fallback_enabled() -> bool:
    return CONFIG.tts.fallback_engine == "pyttsx3"


async def prewarm(voice: VoiceParams) -> bool:
    """A short throwaway synthesis so the first real line in this waifu's voice is not
    slower (FR-S-3). Never raises; returns whether the backend answered."""
    if CONFIG.tts.engine != "gpt_sovits":
        return False
    try:
        await _synthesize_gpt_sovits("Hm.", voice)
        return True
    except TTSUnreachableError:
        return False


async def synthesize(text: str, voice: VoiceParams | None = None) -> bytes:
    """Returns WAV bytes for `text` from whichever engine config.yaml's
    tts.engine selects, in `voice` (the speaking waifu's clip) when given.
    Raises TTSUnreachableError when the backend is down and the pyttsx3 fallback is
    not enabled (the reply then stays text-only, FR-V-7). Runs pyttsx3's blocking
    engine in a thread so it doesn't stall the websocket event loop."""
    if CONFIG.tts.engine == "gpt_sovits":
        if starting() and not await health():
            # Our GPT-SoVITS is still loading: give the line a few seconds.
            await _wait_for_health(_PER_LINE_WAIT_S, interval=0.25)
        try:
            if voice is None:
                return await _synthesize_gpt_sovits(text)
            return await _synthesize_gpt_sovits(text, voice)
        except TTSUnreachableError as exc:
            if not _fallback_enabled():
                raise
            # Fall back to pyttsx3 for this one line rather than letting the
            # turn go silent -- she still says the actual reply, just in the
            # placeholder voice for that line. This WAS silent before, which
            # meant "wrong voice came out" had no visible cause anywhere --
            # printing it here is the whole difference between "check the
            # terminal" and "guess blindly."
            log.warning(f"gpt_sovits unreachable, falling back to pyttsx3: {exc}")

    return await asyncio.to_thread(_synthesize_pyttsx3_sync, text)


# ─── server lifecycle ────────────────────────────────────────────────────────
# The kernel owns the GPT-SoVITS server (D-060). It starts only while Read aloud
# is on (D-097): when it is turned on, or after the chat model at start if it was
# left on; the Tauri shell's Job Object still ends it with the app. Port-first: a server already answering is used, never a second.

_PER_LINE_WAIT_S = 8.0   # a line spoken while our server is still loading waits this long
_CREATE_NO_WINDOW = 0x08000000
_process: subprocess.Popen | None = None
_starting: asyncio.Task[bool] | None = None


def _service_address(api_url: str) -> tuple[str, int]:
    parsed = urlparse(api_url)
    return (parsed.hostname or "127.0.0.1", parsed.port or 9880)


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def health() -> bool:
    """True if the configured TTS server is accepting connections."""
    if CONFIG.tts.engine != "gpt_sovits":
        return False
    host, port = _service_address(CONFIG.tts.gpt_sovits.api_url)
    return await asyncio.to_thread(_port_open, host, port)


def _launch_gpt_sovits() -> subprocess.Popen | None:
    launch = dict(CONFIG.tts.gpt_sovits.launch or {})
    if not launch.get("enabled", False):
        return None
    root = str(launch.get("dir") or "")
    python = str(launch.get("python") or (os.path.join(root, "runtime", "python.exe") if root else ""))
    script = str(launch.get("script") or (os.path.join(root, "api_v2.py") if root else ""))
    cwd = str(launch.get("cwd") or root)
    if not (python and script and os.path.isfile(python) and os.path.isfile(script)):
        log.warning(
            "gpt_sovits: launch paths are missing or wrong "
            f"(python={python!r}, script={script!r}) -- not starting it",
        )
        return None
    args = [str(part) for part in (launch.get("args") or [])]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    env.pop("KOKYU_API_KEYS", None)
    try:
        paths.logs_dir().mkdir(parents=True, exist_ok=True)
        log_file = open(paths.logs_dir() / "gpt_sovits.log", "wb")  # noqa: SIM115 -- the child keeps it
    except OSError:
        log_file = subprocess.DEVNULL
    try:
        return subprocess.Popen(  # noqa: S603 -- local, configured executable
            [python, script, *args],
            cwd=cwd or None,
            env=env,
            stdin=subprocess.DEVNULL,   # the kernel's stdin carries API keys from the shell (D-059)
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=_CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        log.warning(f"gpt_sovits: could not start the server: {exc}")
        return None
    finally:
        if log_file is not subprocess.DEVNULL:
            log_file.close()


async def _wait_for_health(timeout: float, interval: float = 0.5) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        if await health():
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(interval)


async def ensure_server() -> bool:
    """Make the TTS server available if it can be. Returns whether it is up.
    Concurrent callers share one start. Never raises: without a server a reply
    stays text-only (FR-V-7), or uses pyttsx3 when that fallback is on."""
    global _starting
    if CONFIG.tts.engine != "gpt_sovits":
        return False
    if _starting is None or (_starting.done() and not await health()):
        _starting = asyncio.create_task(_start_server())
    return await asyncio.shield(_starting)


def starting() -> bool:
    """True while the kernel's own server is still loading."""
    return _starting is not None and not _starting.done()


async def _start_server() -> bool:
    global _process
    if await health():
        return True
    launch = dict(CONFIG.tts.gpt_sovits.launch or {})
    if not launch.get("enabled", False):
        log.info(
            "gpt_sovits: not running and tts.gpt_sovits.launch is off -- replies stay text-only",
        )
        return False

    process = await asyncio.to_thread(_launch_gpt_sovits)
    if process is None:
        return False
    _process = process

    timeout = float(launch.get("startup_timeout_s", 120))
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if await health():
            log.info("gpt_sovits: server is up")
            return True
        if process.poll() is not None:
            log.info(
                f"gpt_sovits: exited during startup (code {process.returncode}); see logs/gpt_sovits.log",
            )
            return False
        await asyncio.sleep(1.0)
    log.warning(f"gpt_sovits: still not listening after {timeout:.0f}s")
    return False


def stop_server() -> None:
    """End the server this kernel started (kernel shutdown). One we did not start is left alone."""
    global _process
    process, _process = _process, None
    if process is not None and process.poll() is None:
        process.kill()
