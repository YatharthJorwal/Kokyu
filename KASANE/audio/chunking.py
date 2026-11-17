"""
Splits a growing text buffer into sentence-ish chunks as soon as they're
ready, so turns.py can start TTS on the first sentence instead of waiting for
the whole LLM reply -- this is the "streamed text" half of
docs/ARCHITECTURE.md's "streamed text -> TTS -> lip-sync" pipeline (token-
level audio streaming isn't practical with pyttsx3, so chunking at
sentence granularity is the level that's actually achievable in Phase 2).

Not real NLP sentence segmentation -- it'll misfire on things like
abbreviations ("Mr. Smith"). Good enough for spoken-companion chat; revisit
only if it's audibly wrong often enough to matter.
"""

from __future__ import annotations

import re

# Sentences shorter than this get folded into the next one before being
# treated as ready -- pyttsx3 re-inits its engine per call (see tts.py), so
# firing it for every three-word fragment is wasteful and sounds choppy.
# Doesn't apply to the final trailing chunk, which always flushes regardless
# of length once the stream ends.
MIN_CHUNK_CHARS = 40

_SENTENCE_BOUNDARY = re.compile(r"[.!?]+(?=\s|$)")

# A `[word]` (maybe with a stray period) at the end of what has arrived so far may
# be the reply's emotion tag, which persona.extract_emotion_tag reads only once the
# stream ends. Held back until more text proves it is not the end: without this,
# "Sure thing, I can definitely do it now. [happy]." was one ready chunk, so the
# tag was spoken and the emotion lost (D-074, FR-MODE-8).
# No leading or trailing `\s*` in the pattern: searched over a long whitespace run
# (a local model stuck emitting newlines) that was cubic over the stream and froze
# the asyncio loop. The ends are trimmed with rstrip instead, and only the tail is
# searched.
_TRAILING_TAG = re.compile(r"\[\w+\]\.?$")
_TAG_WINDOW = 64


def _tag_start(buffer: str) -> int:
    """Where a possible trailing emotion tag (and the whitespace before it) starts;
    len(buffer) when there is none."""
    tail = buffer.rstrip()
    tag = _TRAILING_TAG.search(tail[-_TAG_WINDOW:])
    if tag is None:
        return len(buffer)
    return len(tail[: len(tail) - len(tag.group())].rstrip())


def extract_ready_chunks(buffer: str) -> tuple[list[str], str]:
    """Given the buffer so far (previous remainder + newly arrived text),
    returns (chunks ready to speak, new remainder to keep buffering)."""
    chunks: list[str] = []
    start = 0
    limit = _tag_start(buffer)
    for match in _SENTENCE_BOUNDARY.finditer(buffer):
        end = match.end()
        if end > limit:
            break
        candidate = buffer[start:end].strip()
        if len(candidate) >= MIN_CHUNK_CHARS:
            chunks.append(candidate)
            start = end
    return chunks, buffer[start:]


def flush(buffer: str) -> list[str]:
    """Call once the LLM stream ends: whatever's left, however short or
    unpunctuated, becomes one final chunk."""
    tail = buffer.strip()
    return [tail] if tail else []
