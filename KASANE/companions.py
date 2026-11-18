"""A window's active companion: a voice and a persona, nothing more (R-01, D-003).

Her prompt, her voice parameters and the switch between companions live here.
Model, effort, tools, permissions and memory never depend on who she is (FR-W-3,
FR-S-5); she supplies only the prompt, the voice, the VRM and the pet sprites.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import conversation
import paths
import prompting
import protocol
import waifus
from audio import read_aloud, tts
from persona import FALLBACK_PERSONA

log = logging.getLogger(__name__)


# --- the active waifu (a voice and a persona, nothing more: R-01, D-003) -----------

_background_tasks: set[asyncio.Task] = set()


def waifu_of(websocket: Any) -> "waifus.Waifu | None":
    waifu = getattr(getattr(websocket, "state", None), "waifu", None)
    return waifu if isinstance(waifu, waifus.Waifu) else None


def voice_of(websocket: Any) -> "tts.VoiceParams | None":
    return voice_for(waifu_of(websocket))


def voice_for(waifu: Any) -> "tts.VoiceParams | None":
    """A companion's voice parameters (her clip, its transcript, her language)."""
    if waifu is None:
        return None
    # The waifu speaks the language of her own reference clip.
    return tts.VoiceParams(
        ref_audio_path=str(waifu.ref_audio_path),
        prompt_text=waifu.voice.ref_text,
        prompt_lang=waifu.voice.ref_lang,
        text_lang=waifu.voice.ref_lang,
    )


def speaker_of(websocket: Any) -> str | None:
    """The name recorded with a turn so shared memory knows who spoke (FR-MEM-2)."""
    active = waifu_of(websocket)
    return active.name if active else None


def system_message(
    waifu: "waifus.Waifu | None", *, mode: str = "chat", scenario: "dict[str, Any] | None" = None
) -> str:
    """Her persona prompt with the thread's layers (FR-MODE-2). The companion picks
    only the persona text; `mode` and `scenario` come from the thread and are the same
    for every companion (FR-W-3, D-074). With no companion installed a neutral
    fallback persona answers, so a fresh checkout still talks."""
    persona_text = FALLBACK_PERSONA if waifu is None else waifu.prompt
    return prompting.build_system_prompt(persona_text, mode=mode, scenario=scenario)


def _active_id_path() -> Path:
    return paths.app_data_dir() / "active_waifu.txt"


def load_active_id() -> str:
    try:
        return _active_id_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_active_id(waifu_id: str) -> None:
    try:
        path = _active_id_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(waifu_id, encoding="utf-8")
    except OSError as exc:
        log.warning(f"could not remember the active companion: {exc}")


async def send_waifu_state(websocket: Any, registry: "waifus.WaifuRegistry", pending: str | None = None) -> None:
    active = waifu_of(websocket)
    await websocket.send_json(
        protocol.frame(
            "waifu_state",
            {
                "active": active.id if active else None,
                "waifus": registry.describe(),
                "problems": [p.message for p in registry.problems],
                "pending": pending,
            },
        )
    )


async def apply_switch(
    websocket: Any,
    history: list[dict[str, str]],
    registry: "waifus.WaifuRegistry",
    waifu_id: str,
    *,
    mode: str = "chat",
    scenario: "dict[str, Any] | None" = None,
) -> "waifus.Waifu | None":
    """Changes ONLY the persona text and the voice. History, model, effort, memory and
    tools are untouched (FR-W-3, FR-S-5), and so is the thread's mode: the caller
    passes the open thread's `mode` and `scenario` (FR-MODE-2), so a switch inside a
    roleplay keeps the roleplay layer. Returns None for an unknown id."""
    target = registry.get(waifu_id)
    if target is None:
        return None
    websocket.state.waifu = target
    history[0]["content"] = system_message(target, mode=mode, scenario=scenario)
    save_active_id(target.id)
    await send_waifu_state(websocket, registry)
    voice_params = voice_of(websocket)
    if voice_params is not None and read_aloud.READ_ALOUD.on:
        task = asyncio.create_task(tts.prewarm(voice_params))  # FR-S-3; never raises
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    return target


def speaker_record(websocket: Any) -> "conversation.Speaker":
    active = waifu_of(websocket)
    return conversation.Speaker(active.id if active else None, active.name if active else None)
