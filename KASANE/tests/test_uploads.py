"""Uploads are opened strictly (D-106)."""
from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

import uploads


def _png(w: int = 4, h: int = 4, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "GIF"])
def test_allowed_pictures_open(fmt):
    assert uploads.open_image(_png(fmt=fmt)).size == (4, 4)


@pytest.mark.parametrize("fmt", ["BMP", "TIFF", "ICO"])
def test_other_formats_are_refused(fmt):
    with pytest.raises(ValueError):
        uploads.open_image(_png(fmt=fmt))


def test_garbage_and_bad_base64_are_refused():
    with pytest.raises(ValueError):
        uploads.open_image(b"not a picture")
    with pytest.raises(ValueError):
        uploads.check_b64("abc$")
    uploads.check_b64(base64.b64encode(_png()).decode())


def test_too_many_pixels_is_refused_before_decoding(monkeypatch):
    monkeypatch.setattr(uploads, "MAX_PIXELS", 15)
    with pytest.raises(ValueError):
        uploads.open_image(_png())
