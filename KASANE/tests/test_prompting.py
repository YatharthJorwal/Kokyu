from __future__ import annotations

import persona
import prompting


def test_every_valid_emotion_is_named_in_the_addendum():
    for name in persona.VALID_EMOTIONS:
        assert f"[{name}]" in prompting.APP_ADDENDUM


def test_build_keeps_the_persona_text_first_and_unmodified():
    text = "You are Alpha. Speak softly."
    out = prompting.build_system_prompt(text + "\n\n")
    assert out.startswith(text)
    assert out.endswith(prompting.APP_ADDENDUM)


def test_addendum_is_identical_for_every_waifu():
    a = prompting.build_system_prompt("You are Alpha.")
    b = prompting.build_system_prompt("You are Beta, someone entirely different.")
    assert a.split("\n\n")[-1] == b.split("\n\n")[-1] == prompting.APP_ADDENDUM


def test_addendum_does_not_grant_or_name_capabilities():
    lowered = prompting.APP_ADDENDUM.lower()
    for word in ("memory", "tool:", "model:", "permission"):
        assert word not in lowered


def test_every_companion_gets_the_same_tool_guidance():
    # Once only in Yuri's own prompt, so other companions never learned to use the tools.
    lowered = prompting.APP_ADDENDUM.lower()
    assert "screenshot" in lowered and "clipboard" in lowered and "webcam" in lowered
    assert "already done" in lowered
    assert "never answer a request to look again with what you saw last time" in lowered
    assert "you can only observe and advise" not in lowered   # once suppressed tool use outright


def test_the_fallback_persona_is_nobody_in_particular():
    assert "yuri" not in persona.FALLBACK_PERSONA.lower() and "luna" not in persona.FALLBACK_PERSONA.lower()
