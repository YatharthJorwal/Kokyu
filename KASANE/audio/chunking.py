"""
The last chunk of a finished stream: ambient remarks speak whatever text is left,
however short or unpunctuated, as one line.
"""

from __future__ import annotations


def flush(buffer: str) -> list[str]:
    """Call once the LLM stream ends: whatever's left, however short or
    unpunctuated, becomes one final chunk."""
    tail = buffer.strip()
    return [tail] if tail else []
