"""The roleplay dialogue cut and the chunker's held-back emotion tag
(K1c-05; FR-MODE-8; D-074).

In a roleplay thread only her dialogue is spoken: `*actions*`, `(OOC ...)`,
`((...))` and `[...]` are dropped by code, and once a reply has used a double
quote only quoted text is spoken. The cut streams, so the output must not depend
on where the model's deltas happen to split.
"""
from __future__ import annotations

import pytest

from audio.chunking import extract_ready_chunks, flush
from audio.speech import DialogueFilter

LDQ, RDQ = "\u201c", "\u201d"


def cut(text: str) -> str:
    f = DialogueFilter()
    return f.feed(text) + f.finish()


# (raw reply, the dialogue it speaks). Outputs keep the filter's own spacing: one
# space for each dropped span or quote mark, whitespace collapsed, no leading space.
GOLDEN = [
    # plain text with no markup is all dialogue (FR-MODE-8: narration counts until a quote)
    ("Hello there. How are you?", "Hello there. How are you?"),
    # single-asterisk actions are dropped, and leave one space behind
    ("*She smiles.* Hello there.", "Hello there."),
    ("Hi. *waves* Bye.", "Hi. Bye."),
    ("Hi.*waves*Bye.", "Hi. Bye."),
    # a multi-sentence action, which a per-chunk filter would see unbalanced
    ("Wait. *She stands. She walks to the door. She stops.* Okay.", "Wait. Okay."),
    # **bold** keeps its words and loses the markers
    ("I **really** mean it.", "I really mean it."),
    ("**Stop!** Please.", "Stop! Please."),
    # bold inside an action is still the action
    ("Yes. *she says **loudly** and leaves* No.", "Yes. No."),
    # *** is bold markers then an action
    ("Ok. ***gasps*** Fine.", "Ok. Fine."),
    # an unclosed action at the end is dropped
    ("Hold on. *She turns away", "Hold on. "),
    ("Hold on. *", "Hold on. "),
    # OOC asides, any case, with or without a colon, nested parentheses counted
    ("Sure. (OOC: brb, getting food) See you.", "Sure. See you."),
    ("Sure. (ooc brb) See you.", "Sure. See you."),
    ("Sure. ( OOC: x) See you.", "Sure. See you."),
    ("Sure. (OOC: a (small) aside) See you.", "Sure. See you."),
    ("Sure. ((just a note)) See you.", "Sure. See you."),
    ("Sure. ((a (nested) note)) See you.", "Sure. See you."),
    # a parenthesis that is not an aside is text (speech.prepare deals with it later)
    ("An (oocyte) is a cell.", "An (oocyte) is a cell."),
    ("Fine (mostly).", "Fine (mostly)."),
    ("Fine (oo", "Fine (oo"),
    ("Fine (OOC", "Fine "),
    # brackets: the emotion tag and any other [...] span
    ("I missed you. [happy]", "I missed you. "),
    # the tag's stray period after a finished sentence goes with it; a period that
    # ends a sentence around a bracket stays
    ("I missed you. [happy].", "I missed you. "),
    ("I missed you! [happy].", "I missed you! "),
    ("Look [aside].", "Look ."),
    ("Look [aside] here.", "Look here."),
    # the first double quote switches narration off: only quoted text after it
    ('*smiles* "Hello there," she says. "How are you?" [happy]', "Hello there, How are you? "),
    ('She looks up. "Oh, it is you." She laughs.', "She looks up. Oh, it is you. "),
    # curly quotes work the same way
    (f"{LDQ}Hi,{RDQ} she said. {LDQ}Bye.{RDQ}", "Hi, Bye. "),
    (f"She nods. {LDQ}Fine.{RDQ} *leaves*", "She nods. Fine. "),
    # ...but they have a direction (review finding): a line over two paragraphs
    # reopens without closing first, and a stray closing quote opens nothing
    (
        f"{LDQ}First paragraph of her line.\n\n{LDQ}Second paragraph.{RDQ} She walks off, humming. *waves*",
        "First paragraph of her line. Second paragraph. ",
    ),
    (f"{LDQ}Hi.{RDQ} She waves.{RDQ} *nods* She leaves.", "Hi. "),
    (f"{LDQ}Hi.{RDQ}{RDQ} She waves.", "Hi. "),
    # inside a quote an asterisk is emphasis: words kept, markers dropped
    ('"I *really* missed you."', "I really missed you. "),
    # a quote inside an action is part of the action and does not switch narration off
    ('*She whispers "hi"* Hello.', "Hello."),
    # apostrophes are not quotes
    ("I don't know, it's Sam's.", "I don't know, it's Sam's."),
    ("I don\u2019t know.", "I don\u2019t know."),
    # whitespace and newlines collapse to single spaces
    ("Hi.\n\n*waves*\n\nBye.", "Hi. Bye."),
    ("   Hi.", "Hi."),
    # nothing left
    ("*She only smiles.*", ""),
    ("(OOC: back in a sec)", ""),
    ("", ""),
]


@pytest.mark.parametrize("raw, expected", GOLDEN)
def test_golden(raw: str, expected: str):
    # FR-MODE-8: only her dialogue is spoken, whatever the model wrote.
    assert cut(raw) == expected


SPLIT_CASES = [raw for raw, _ in GOLDEN if raw] + [
    "Hi. ***gasps*** (OOC: ok (fine)) ((a)) [sad] \"Yes,\" she said. *nods* \"No.\" [happy].",
    f"*a* {LDQ}b *c* **d**{RDQ} e (  OOC: f) g",
]


@pytest.mark.parametrize("raw", SPLIT_CASES)
def test_output_does_not_depend_on_where_the_stream_splits(raw: str):
    # FR-MODE-8: "**" and "(OOC" may be split across deltas; held-back text keeps
    # every split giving the same dialogue as one feed.
    whole = cut(raw)
    for k in range(len(raw) + 1):
        f = DialogueFilter()
        assert f.feed(raw[:k]) + f.feed(raw[k:]) + f.finish() == whole, k
    for i in range(len(raw) + 1):
        for j in range(i, len(raw) + 1, 3):
            f = DialogueFilter()
            assert f.feed(raw[:i]) + f.feed(raw[i:j]) + f.feed(raw[j:]) + f.finish() == whole, (i, j)
    f = DialogueFilter()
    assert "".join(f.feed(ch) for ch in raw) + f.finish() == whole


def test_a_trailing_asterisk_is_held_back_until_the_next_delta():
    # "**" split across deltas must not open an action.
    f = DialogueFilter()
    assert f.feed("I *") == "I "
    assert f.feed("*really** do.") == "really do."
    assert f.finish() == ""


def test_an_ooc_prefix_is_held_back_until_decided():
    f = DialogueFilter()
    assert f.feed("Sure (O") == "Sure "
    assert f.feed("o") == ""
    assert f.feed("cyte) ok") == "(Oocyte) ok"
    f = DialogueFilter()
    assert f.feed("Sure (O") == "Sure "
    assert f.feed("OC: x) ok") == "ok"   # the space after "Sure" was already out


def test_finish_flushes_what_was_held_back():
    f = DialogueFilter()
    assert f.feed("Total (oo") == "Total "
    assert f.finish() == "(oo"


def test_dropped_spans_keep_sentence_boundaries_for_the_chunker():
    # A dropped span becomes a space, so "now." is still a boundary for the chunker.
    spoken = cut("That is enough waiting around for one day now.*She stands.*Let us go somewhere else entirely.")
    chunks, rest = extract_ready_chunks(spoken)
    assert chunks == ["That is enough waiting around for one day now."]
    assert flush(rest) == ["Let us go somewhere else entirely."]


# -- the chunker holds back a trailing emotion tag (both modes) -------------------


def test_a_trailing_tag_after_a_short_sentence_is_not_a_ready_chunk():
    # The map's verified case: 39 characters, then the tag with a stray period, used
    # to come out as one ready chunk, so the tag was spoken and the emotion lost.
    text = "Sure thing, I can definitely do it now. [happy]."
    assert extract_ready_chunks(text) == ([], text)
    assert extract_ready_chunks("Sure thing, I can definitely do it now. [happy]") == ([], "Sure thing, I can definitely do it now. [happy]")


def test_a_trailing_tag_does_not_hold_back_earlier_ready_sentences():
    chunks, rest = extract_ready_chunks("This sentence is long enough to be spoken right away. Short. [sad].")
    assert chunks == ["This sentence is long enough to be spoken right away."]
    assert rest == " Short. [sad]."


def test_a_bracket_followed_by_more_text_is_not_held_back():
    chunks, rest = extract_ready_chunks("Sure thing, I can definitely do it now. [happy]. And then some more here. ")
    assert chunks == ["Sure thing, I can definitely do it now. [happy]."]
    assert rest == " And then some more here. "


def test_plain_chunking_is_unchanged():
    chunks, rest = extract_ready_chunks("This is a long enough sentence to be spoken now. Next")
    assert chunks == ["This is a long enough sentence to be spoken now."] and rest == " Next"


def test_a_trailing_tag_after_whitespace_and_a_newline_is_still_held_back():
    text = "Sure thing, I can definitely do it now.\n\n  [happy]. \n"
    assert extract_ready_chunks(text) == ([], text)
    chunks, rest = extract_ready_chunks("This sentence is long enough to be spoken right away.\n\n  [sad]. \n")
    assert chunks == ["This sentence is long enough to be spoken right away."] and rest == "\n\n  [sad]. \n"


def test_a_long_whitespace_run_is_chunked_in_linear_time():
    # Review finding: the tag pattern began with `\s*`, so every delta of a newline
    # run (a small model stuck in a loop) cost O(w^2) and the stream O(w^3): 2000
    # newlines took about 3 s on the asyncio loop. Now it is a few milliseconds.
    import time

    buffer, started = "Here is the plan", time.perf_counter()
    for _ in range(3000):
        _chunks, buffer = extract_ready_chunks(buffer + "\n")
    assert time.perf_counter() - started < 1.0
    assert buffer == "Here is the plan" + "\n" * 3000
