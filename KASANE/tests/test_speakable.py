"""speech.speakable (D-097, FR-V-2): what she says aloud of one finished reply.

Fixed rules, no model. Realistic replies, the user's own example first."""
import pytest

from audio import speech
from audio.speech import speakable


USER_EXAMPLE = (
    "What? You think just because I'm stuck here as an AI, you can order me around like a database? [angry]\n"
    "\n"
    "Fine — I'll do it, but only because you asked *nicely*. Here's your \"precious\" fruit list – "
    "don't say I never give you anything. [teasing]\n"
    "\n"
    "| Fruit | Colour | Taste |\n"
    "|-------|--------|-------|\n"
    "| Apple | Red | Sweet |\n"
    "| Lemon | Yellow | Sour |\n"
    "| Grape | Purple | Sweet |\n"
)


def test_the_users_example_in_chat():
    assert speakable(USER_EXAMPLE, "chat") == (
        "What? You think just because I'm stuck here as an AI, you can order me around like a database? "
        "Fine, I'll do it, but only because you asked nicely. Here's your precious fruit list, "
        "don't say I never give you anything."
    )


def test_the_users_example_as_a_roleplay_line_speaks_only_her_dialogue():
    reply = (
        "*She crosses her arms, glaring at the screen.* \"What? You think you can order me around "
        "like a database?\" [angry]\n"
        "\n"
        "*A long sigh.* \"Fine — here's your 'precious' list.\" *She flicks it over.*\n"
        "\n"
        "| Fruit | Colour |\n"
        "|---|---|\n"
        "| Apple | Red |\n"
        "\n"
        "(OOC: hope that's what you wanted!)"
    )
    assert speakable(reply, "roleplay") == (
        "What? You think you can order me around like a database? Fine, here's your precious list."
    )


def test_code_fences_and_inline_code_are_never_read():
    reply = (
        "Sure! Here's how to say hi in Python:\n"
        "\n"
        "```python\n"
        "def hi(name):\n"
        "    print(f\"Hi, {name}! *waves*\")\n"
        "```\n"
        "\n"
        "Save it as `hi.py` and you're set \U0001F60A"
    )
    assert speakable(reply) == "Sure! Here's how to say hi in Python. Save it as and you're set."


def test_an_unclosed_fence_runs_to_the_end():
    # Stopped mid-code: everything after the fence is code.
    assert speakable("Here you go:\n\n~~~js\nconst a = 1;\nconsole.log(a)") == "Here you go."


def test_only_code_says_nothing():
    assert speakable("```\nrm -rf build\n```") == ""
    assert speakable("") == ""
    assert speakable("   \n\n") == ""


def test_list_items_are_read_as_sentences():
    reply = (
        "Three things to pack:\n"
        "\n"
        "1. Water\n"
        "2. Sunscreen, lots of it\n"
        "   - the SPF 50 one\n"
        "3. **Snacks!**\n"
        "\n"
        "* Bonus: a hat;\n"
        "+ Have fun!"
    )
    assert speakable(reply) == (
        # (all caps outside the acronym list is lowered: normalize_spoken's shouting rule)
        "Three things to pack. Water. Sunscreen, lots of it. the spf 50 one. Snacks! Bonus: a hat. Have fun!"
    )


def test_headings_quotes_and_rules():
    reply = "## Tonight's plan\n\n> Rest is productive too.\n\n---\n\nSo: sleep early"
    assert speakable(reply) == "Tonight's plan. Rest is productive too. So: sleep early."


def test_links_keep_their_words_and_addresses_go():
    reply = (
        "Read [the guide](https://example.com/guide_(v2)) first, then https://example.com/faq?x=1. "
        "Or <https://example.com>. ![a cat](https://example.com/cat.png) www.example.org works too."
    )
    assert speakable(reply) == "Read the guide first, then. Or. works too."


def test_dashes_become_a_comma_pause_and_quote_marks_go():
    reply = "She said “maybe” – then left—again. It's 'fine' - really."
    assert speakable(reply) == "She said maybe, then left, again. It's fine, really."


def test_emoji_emoticons_and_tags_mid_text_go():
    reply = "Good morning! ☀️\U0001F496 [happy] Slept well? :) [teasing]"
    assert speakable(reply) == "Good morning! Slept well?"


def test_a_tag_on_its_own_line_leaves_no_stray_period():
    assert speakable("Hmph.\n[angry]\nWhatever.") == "Hmph. Whatever."


def test_markdown_marks_and_escapes():
    reply = "This is **really** _very_ ~~not~~ important, 5 \\* 3 = 15 \\[sic]."
    # an escaped "[" is still a bracketed aside to the voice: [sic] is dropped like a tag
    assert speakable(reply) == "This is really very not important, 5 3 = 15."


def test_roleplay_narration_before_any_quote_is_spoken_and_actions_are_not():
    assert speakable("*yawns* Morning already? [sad]", "roleplay") == "Morning already?"
    assert speakable("*She waves.*", "roleplay") == ""


def test_roleplay_code_is_dropped_before_the_dialogue_cut():
    # A "*" or quote inside code must not open an action or her line.
    reply = '"Look at this."\n\n```\nprint("*not dialogue*")\n```\n\n"Neat, right?"'
    assert speakable(reply, "roleplay") == "Look at this. Neat, right?"


@pytest.mark.parametrize("reply", [
    USER_EXAMPLE,
    "A—B “C” … *D* `E` **F** _G_ ~~H~~ [i](https://x.y) [tag]",
    "- “quoted item” – with a dash…\n- `code` item",
    "```\nunclosed",
])
@pytest.mark.parametrize("mode", ["chat", "roleplay"])
def test_no_banned_character_ever_reaches_the_voice(reply, mode):
    out = speakable(reply, mode)
    assert not speech.banned_chars_in(out), out
    assert "http" not in out and "[" not in out and "|" not in out


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        speakable("hi", "stage")


def test_pure_same_input_same_output():
    assert speakable(USER_EXAMPLE) == speakable(USER_EXAMPLE)
