"""System prompt layers (FR-MODE-2, 3, 4; D-074) and the shared addendum (FR-W-3)."""
from __future__ import annotations

import pytest

import persona
import prompting

CARD = {
    "title": "  Rain at the station  ",
    "setting": "A train station at night.",
    "user_role": "",
    "her_role": "An old friend.",
    "rules": "   ",
    "opening": "*She shakes the rain off her umbrella.* \"You came.\"",
}


def test_every_valid_emotion_is_named_in_the_addendum():
    for name in persona.VALID_EMOTIONS:
        assert f"[{name}]" in prompting.APP_ADDENDUM


def test_build_keeps_the_persona_text_first_and_unmodified():
    text = "You are Alpha. Speak softly."
    out = prompting.build_system_prompt(text + "\n\n")
    assert out.startswith(text + "\n\n" + prompting.CHAT_LAYER)
    assert out.endswith(prompting.APP_ADDENDUM + " " + prompting.TOOL_GUIDANCE)


def test_chat_layers_come_in_order():
    """FR-MODE-2: persona, the chat layer, the shared addendum, then the tool guidance."""
    out = prompting.build_system_prompt("You are Alpha.", mode="chat", scenario=CARD)
    assert out == "\n\n".join(
        ["You are Alpha.", prompting.CHAT_LAYER, prompting.APP_ADDENDUM + " " + prompting.TOOL_GUIDANCE]
    )
    assert prompting.SCENARIO_HEADING not in out   # a card means nothing in a chat thread


def test_roleplay_layers_come_in_order_without_tool_guidance():
    """FR-MODE-2, FR-MODE-4: persona, the roleplay layer, the card, the addendum; no tools."""
    out = prompting.build_system_prompt("You are Alpha.", mode="roleplay", scenario=CARD)
    card = (
        "The scenario for this roleplay:\n"
        "Title: Rain at the station\n"
        "Setting: A train station at night.\n"
        "Who you are to them: An old friend.\n"
        "The scene opened with your line: *She shakes the rain off her umbrella.* \"You came.\""
    )
    assert out == "\n\n".join(["You are Alpha.", prompting.ROLEPLAY_LAYER, card, prompting.APP_ADDENDUM])
    assert prompting.TOOL_GUIDANCE not in out and "screenshot" not in out.lower()


@pytest.mark.parametrize("scenario", [None, {}, {"title": " ", "rules": ""}, {"unknown": "x"}])
def test_an_empty_card_writes_no_scenario_block(scenario):
    out = prompting.build_system_prompt("You are Alpha.", mode="roleplay", scenario=scenario)
    assert out == "\n\n".join(["You are Alpha.", prompting.ROLEPLAY_LAYER, prompting.APP_ADDENDUM])


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        prompting.build_system_prompt("You are Alpha.", mode="live")


@pytest.mark.parametrize("mode", ["chat", "roleplay"])
def test_everything_after_the_persona_is_identical_for_every_waifu(mode):
    """FR-W-3: only the persona differs between companions, in every mode."""
    a = prompting.build_system_prompt("You are Alpha.", mode=mode, scenario=CARD)
    b = prompting.build_system_prompt("You are Beta, someone entirely different.", mode=mode, scenario=CARD)
    assert a.removeprefix("You are Alpha.") == b.removeprefix("You are Beta, someone entirely different.")


def test_addendum_does_not_grant_or_name_capabilities():
    lowered = prompting.APP_ADDENDUM.lower()
    for word in ("memory", "tool:", "model:", "permission"):
        assert word not in lowered
    assert "never claim abilities, tools or knowledge you were not given" in lowered   # the honesty sentence


def test_every_companion_gets_the_same_tool_guidance():
    # Once only in Yuri's own prompt, so other companions never learned to use the tools.
    lowered = prompting.TOOL_GUIDANCE.lower()
    assert "screenshot" in lowered and "clipboard" in lowered and "webcam" in lowered
    assert "already done" in lowered
    assert "never answer a request to look again with what you saw last time" in lowered
    assert "you can only observe and advise" not in lowered   # once suppressed tool use outright
    assert "screenshot" not in prompting.APP_ADDENDUM.lower()   # tool guidance is chat only (FR-MODE-4)


def test_the_fallback_persona_is_nobody_in_particular():
    assert "yuri" not in persona.FALLBACK_PERSONA.lower() and "luna" not in persona.FALLBACK_PERSONA.lower()


def test_the_fallback_persona_holds_no_length_or_format_rule():
    """FR-MODE-2: the persona says who she is; length and format are the mode layer's."""
    lowered = persona.FALLBACK_PERSONA.lower()
    assert "short" not in lowered and "reply" not in lowered and "replies" not in lowered
