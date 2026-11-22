"""Every picture a user hands the kernel is opened here (D-106).

The window already checks type, size and pixels before sending (src/app/file-upload.ts),
but the kernel trusts nothing from a socket: a picture must be base64 of a PNG, JPEG,
WebP or GIF no larger than MAX_PIXELS, or it is refused as unreadable. Formats are
an allowlist so Pillow never runs a decoder for anything else (EPS, PSD, ICO, ...).
"""
from __future__ import annotations

import base64
import binascii
import io

FORMATS = ("PNG", "JPEG", "WEBP", "GIF")
MAX_PIXELS = 40_000_000     # about 6300 x 6300: no real photo or sheet is bigger


def decode(b64: str) -> bytes:
    """Strict base64. Raises ValueError."""
    try:
        return base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("not base64") from exc


def open_image(data: bytes):
    """An allowed, not-too-large picture, loaded as RGBA. Raises ValueError."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data), formats=FORMATS) as img:
            if img.width * img.height > MAX_PIXELS:   # checked from the header, before decoding
                raise ValueError("too many pixels")
            img.load()
            return img.convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("not an allowed picture") from exc


def check_b64(b64: str) -> None:
    """Raises ValueError unless `b64` is an allowed picture. Blocking: a thread."""
    open_image(decode(b64))
