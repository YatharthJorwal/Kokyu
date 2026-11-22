"""Her face (D-091, FR-W-8): the VRM's own thumbnail, scaled down, or the picture
the user chose in her profile.

A VRM 1.0 file is a GLB: a JSON chunk that describes it, then one binary chunk.
`VRMC_vrm.meta.thumbnailImage` names the image; VRoid exports a face shot there.
Only that image's bytes are read, never the whole model. The scaled copy is cached
in the app data folder under a name that changes with the VRM file, so a new model
gives a new face. Nothing here is written into a pack (premades are read-only, D-039).
"""
from __future__ import annotations

import io
import json
import logging
import re
import struct
from pathlib import Path

import paths
import uploads
from waifus.pack import Waifu

log = logging.getLogger("kokyu.waifus")

SIZE = 512                          # the profile shows it at 160 px; sharp at 2x and more
MAX_THUMBNAIL_BYTES = 16 * 1024 * 1024
_GLB_MAGIC = b"glTF"
_JSON_CHUNK = 0x4E4F534A
_BIN_CHUNK = 0x004E4942


def vrm_thumbnail(vrm_path: Path) -> bytes | None:
    """The thumbnail's encoded bytes (PNG or JPEG), or None when the file has none or
    is not a VRM 1.0 GLB. Never raises for a bad file: she just shows her initial."""
    try:
        with open(vrm_path, "rb") as f:
            magic, _version, _length = struct.unpack("<4sII", f.read(12))
            if magic != _GLB_MAGIC:
                return None
            json_len, json_type = struct.unpack("<II", f.read(8))
            if json_type != _JSON_CHUNK:
                return None
            doc = json.loads(f.read(json_len))
            index = doc["extensions"]["VRMC_vrm"]["meta"]["thumbnailImage"]
            view = doc["bufferViews"][doc["images"][index]["bufferView"]]
            length = int(view["byteLength"])
            if not 0 < length <= MAX_THUMBNAIL_BYTES:
                return None
            bin_len, bin_type = struct.unpack("<II", f.read(8))
            start = int(view.get("byteOffset", 0))
            if bin_type != _BIN_CHUNK or start + length > bin_len:
                return None
            f.seek(start, io.SEEK_CUR)
            data = f.read(length)
            return data if len(data) == length else None
    except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error):
        return None


def square(data: bytes, size: int = SIZE) -> bytes:
    """Any allowed picture (uploads.FORMATS) as a centred square PNG of `size` px.
    Raises ValueError if it is not one."""
    from PIL import Image

    rgba = uploads.open_image(data)
    side = min(rgba.size)
    left, top = (rgba.width - side) // 2, (rgba.height - side) // 2
    out = rgba.crop((left, top, left + side, top + side)).resize((size, size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def chosen_path(waifu_id: str) -> Path:
    """The picture the user chose for her (UI1-06b)."""
    return paths.portraits_dir() / f"{waifu_id}.png"


def choose(waifu_id: str, data: bytes | None) -> None:
    """Saves the picture the user chose for her (cut square), or with None goes back
    to the model's face. Raises ValueError if `data` is not an image. Blocking."""
    path = chosen_path(waifu_id)
    if data is None:
        path.unlink(missing_ok=True)
        return
    png = square(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(png)
    tmp.replace(path)


def _stamp(path: Path) -> str:
    st = path.stat()
    return f"{st.st_mtime_ns:x}-{st.st_size:x}"


def version(waifu: Waifu) -> str | None:
    """Changes whenever her face may have changed, so the window's URL does too.
    Cheap: two stats, no parsing."""
    try:
        chosen = chosen_path(waifu.id)
        return "c" + _stamp(chosen) if chosen.is_file() else "m" + _stamp(waifu.vrm_path)
    except OSError:
        return None


def portrait_file(waifu: Waifu) -> Path | None:
    """The PNG to serve: her chosen picture, else the cached thumbnail (made on first
    ask), else None. Blocking: call it in a thread."""
    chosen = chosen_path(waifu.id)
    if chosen.is_file():
        return chosen
    try:
        stamp = _stamp(waifu.vrm_path)
    except OSError:
        return None
    cache_dir = paths.portraits_dir() / "cache"
    cached = cache_dir / f"{waifu.id}-{stamp}.png"
    if cached.is_file():
        return cached
    raw = vrm_thumbnail(waifu.vrm_path)
    if raw is None:
        return None
    try:
        png = square(raw)
    except ValueError:
        log.warning("portrait: %s's VRM thumbnail is not a readable image", waifu.id)
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    # her older copies only: "luna-…" must not match "luna-2-…"
    mine = re.compile(rf"{re.escape(waifu.id)}-[0-9a-f]+-[0-9a-f]+\.png")
    for old in cache_dir.glob("*.png"):
        if mine.fullmatch(old.name):
            old.unlink(missing_ok=True)
    tmp = cached.with_suffix(".tmp")
    tmp.write_bytes(png)
    tmp.replace(cached)
    return cached
