"""Text rules shared by every companion: the speech safety nets and the emotion tag.

A companion's personality is her pack's prompt (`waifus/`, D-031); the rules every
companion shares are in `prompting` (the mode layers and the addendum, D-074). This module only holds the
fallback persona for an install with no companion at all, the two regex safety
nets on spoken text, and the parser for the trailing `[emotion]` tag.
"""

import re

# Used only when no companion pack is installed: a plain, neutral character, so the
# app still answers. Every installed companion brings her own prompt. Persona only:
# length and format belong to the mode layer (FR-MODE-2, D-074).
FALLBACK_PERSONA = (
    "You are a friendly companion who lives on the user's computer. You talk like a "
    "person, not a help desk: warm, curious and direct, and you care about getting "
    "things right when they matter."
)

# A small model told "never use a dash" still uses one now and then, and TTS reads
# it aloud as "minus". Applied only to text on its way to TTS (history keeps the
# model's wording). ", " reads fine for both a compound word and a spoken pause.
_DASH_PATTERN = re.compile(r"\s*[\-‐‑‒–—―−]\s*")

# The voice model mangles "you're" (the user's report); spelled out keeps it clear.
_YOURE_PATTERN = re.compile(r"\byou're\b", re.IGNORECASE)


def _replace_youre(match: re.Match) -> str:
    return "You are" if match.group(0)[0].isupper() else "you are"


def apply_persona_pass(neutral_text: str) -> str:
    """The text a clause is spoken as: dashes become commas, "you're" is spelled out."""
    text = _DASH_PATTERN.sub(", ", neutral_text)
    return _YOURE_PATTERN.sub(_replace_youre, text)


# The tags a reply may end with (the addendum lists them). Five map 1:1 to VRM
# expression presets; the client renders "teasing" as a blend of "relaxed" and "angry".
VALID_EMOTIONS = frozenset({"happy", "angry", "sad", "teasing", "surprised", "neutral"})

# A trailing `[emotion]`, maybe followed by a stray period. Anchored to the end:
# checked once the reply is complete, so a bracketed word mid-stream never matches.
_EMOTION_TAG_PATTERN = re.compile(r"\[(\w+)\]\.?\s*$")


def extract_emotion_tag(text: str) -> tuple[str, str | None]:
    """(text without the trailing tag, emotion or None). Call only on a finished reply.
    An unknown tag is still stripped (so it is never read aloud) but returns None."""
    match = _EMOTION_TAG_PATTERN.search(text)
    if not match:
        return text, None
    stripped = text[: match.start()].rstrip()
    name = match.group(1).lower()
    if name not in VALID_EMOTIONS:
        return stripped, None
    return stripped, name
