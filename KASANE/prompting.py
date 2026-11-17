"""System prompt assembly (ARCHITECTURE s4.1, D-031, D-074).

    system = <persona> + <mode layer> [+ <scenario card>, roleplay only]
             + <APP_ADDENDUM> [+ <TOOL_GUIDANCE>, chat only]

The persona is the companion's own prompt: who she is, never format or length rules.
Everything after it is IDENTICAL for every companion and depends only on the thread
(its mode and scenario card): that is what the invariance tests (FR-W-3) pin down.
The message is stable for the life of a thread, so llama-server's cached prefix holds;
what changes from turn to turn (recall, hints, the story summary, the delivery layer
while voice is on) is spliced in by the turn runner as an ephemeral note instead.
"""
from __future__ import annotations

from typing import Any, Mapping

from persona import VALID_EMOTIONS

_EMOTION_LIST = " ".join(f"[{name}]" for name in ("happy", "angry", "sad", "teasing", "surprised", "neutral"))

# Guards the contract with persona.extract_emotion_tag even if the list above is edited.
assert set(_EMOTION_LIST.replace("[", "").replace("]", "").split()) == set(VALID_EMOTIONS)

# FR-MODE-3: how she talks in a chat thread, the same text for every companion.
CHAT_LAYER = (
    "This is a normal conversation, not a story. Talk to the user as yourself, in your own "
    "voice and personality, but plainly: answer what they ask and help with what they are "
    "doing. Keep it to about three or four lines unless the task needs more, such as code, "
    "steps or a list they asked for. Use Markdown only when it helps: a short list, a code "
    "block, a bold word. Do not narrate your actions or describe gestures with asterisks, and "
    "do not invent scenes."
)

# FR-MODE-4: how she writes in a roleplay thread, the same text for every companion.
ROLEPLAY_LAYER = (
    "This is a roleplay with the user. Stay in character at all times and write the way "
    "characters write on roleplay sites: actions and narration between single asterisks, like "
    "*she leans against the doorframe*; what you say as plain text or in quotes; **double "
    "asterisks** only for strong emphasis; and anything out of character in parentheses "
    "starting with OOC, like (OOC: is this okay?), used only when the user steps out of "
    "character first or something must be cleared up. Write a paragraph or two per reply. "
    "Move the story forward, react to what the user's character does, and never decide the "
    "user's actions, words or feelings for them. You have no tools in this conversation and "
    "you do not look at the user's screen or camera. You may be told a few facts about the "
    "real person you are writing with; use them only to treat them well, never as events in "
    "the story."
)

# One layer per thread mode (threads.store.MODES, FR-MODE-1).
MODE_LAYERS = {"chat": CHAT_LAYER, "roleplay": ROLEPLAY_LAYER}

# FR-MODE-4, 6: the scenario card in a roleplay thread. Only the fields that are filled
# in are written, in this order; a card with nothing in it writes no block at all.
SCENARIO_HEADING = "The scenario for this roleplay:"
SCENARIO_FIELDS = (
    ("title", "Title"),
    ("setting", "Setting"),
    ("user_role", "The user plays"),
    ("her_role", "Who you are to them"),
    ("rules", "Rules"),
    ("opening", "The scene opened with your line"),
)

# Shared by every mode and every companion: the emotion tag and honesty about abilities.
APP_ADDENDUM = (
    "Format rule that applies to every reply, whoever you are playing: finish the reply with "
    "exactly one emotion tag in square brackets, chosen from these six words and nothing else: "
    f"{_EMOTION_LIST}. The tag is never spoken aloud. If your instructions above already say "
    "this, follow them. Never claim abilities, tools or knowledge you were not given; your "
    "intelligence and capabilities are those of the model you run on, and your character only "
    "shapes personality and voice."
)

# How to use the tools a turn may offer (FR-W-3: the same guidance for every companion).
# Chat only: a roleplay offers no tools (FR-MODE-4), so it must not be told about them.
TOOL_GUIDANCE = (
    "When you are given tools, use them for real: one takes a screenshot of the user's screen, "
    "one looks through their webcam if they turned it on, one reads their clipboard. Usually, "
    "when the user asks you to look, the looking was already done and what you saw is given in "
    "this turn, so use it accurately; if nothing was given, use the tool. Never answer a request "
    "to look again with what you saw last time. If the camera fails, tell them to turn it on and "
    "never pretend you saw something. Keeping track of a task needs no tool; just react in words. "
    "You may be shown their screen unprompted; react as if you noticed it yourself, briefly, "
    "without mentioning checks, timers or tools. You cannot control the mouse or keyboard, run "
    "code or edit files."
)


def scenario_block(scenario: Mapping[str, Any] | None) -> str:
    """The scenario card as text, or "" when it has nothing filled in (FR-MODE-6)."""
    if not scenario:
        return ""
    lines = []
    for key, label in SCENARIO_FIELDS:
        value = scenario.get(key)
        text = value.strip() if isinstance(value, str) else ""
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join([SCENARIO_HEADING, *lines]) if lines else ""


def build_system_prompt(
    persona_prompt: str, *, mode: str = "chat", scenario: Mapping[str, Any] | None = None
) -> str:
    """The full system message (FR-MODE-2): persona, mode layer, the scenario card in a
    roleplay, the shared addendum, then the tool guidance in chat. Only the persona
    differs between companions; the rest depends on the thread alone."""
    if mode not in MODE_LAYERS:
        raise ValueError(f"unknown conversation mode: {mode!r}")
    parts = [persona_prompt.rstrip(), MODE_LAYERS[mode]]
    if mode == "roleplay":
        card = scenario_block(scenario)
        if card:
            parts.append(card)
    parts.append(APP_ADDENDUM + (" " + TOOL_GUIDANCE if mode == "chat" else ""))
    return "\n\n".join(parts)
