"""System prompt assembly (ARCHITECTURE s4.1, D-031).

    system = <the waifu's persona prompt> + <APP ADDENDUM>

The addendum is IDENTICAL for every waifu: only the persona text differs. That is what
the invariance tests (FR-W-3) pin down. Ephemeral blocks (recall, hints, scene context)
are still spliced in by the turn runner exactly as before.
"""
from __future__ import annotations

from persona import VALID_EMOTIONS

_EMOTION_LIST = " ".join(f"[{name}]" for name in ("happy", "angry", "sad", "teasing", "surprised", "neutral"))

# Guards the contract with persona.extract_emotion_tag even if the list above is edited.
assert set(_EMOTION_LIST.replace("[", "").replace("]", "").split()) == set(VALID_EMOTIONS)

APP_ADDENDUM = (
    "Format rule that applies to every reply, whoever you are playing: finish the reply with "
    "exactly one emotion tag in square brackets, chosen from these six words and nothing else: "
    f"{_EMOTION_LIST}. The tag is never spoken aloud. If your instructions above already say "
    "this, follow them. Never claim abilities, tools or knowledge you were not given; your "
    "intelligence and capabilities are those of the model you run on, and your character only "
    "shapes personality and voice."
)


def build_system_prompt(persona_prompt: str) -> str:
    """The full system message for one waifu."""
    return persona_prompt.rstrip() + "\n\n" + APP_ADDENDUM
