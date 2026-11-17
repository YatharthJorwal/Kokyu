"""Her face from the VRM thumbnail (D-091, FR-W-8). Tiny GLB files built here; never real assets."""
from __future__ import annotations

import io
import json
import os
import struct

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as kernel_app
import waifus
from waifu_fixtures import make_pack
from waifus import WaifuRegistry, portrait


def png(width: int, height: int, colour=(200, 40, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buf, format="PNG")
    return buf.getvalue()


def glb(image: bytes | None, *, padding: bytes = b"\0" * 7) -> bytes:
    """A minimal VRM 1.0 GLB: `padding` first in the binary chunk, so the image's
    byteOffset is not 0, then the image named by meta.thumbnailImage."""
    blob = padding + (image or b"")
    doc: dict = {"asset": {"version": "2.0"}, "extensionsUsed": ["VRMC_vrm"], "extensions": {"VRMC_vrm": {"meta": {"name": "x"}}}}
    if image is not None:
        doc["bufferViews"] = [{"buffer": 0, "byteOffset": len(padding), "byteLength": len(image)}]
        doc["images"] = [{"name": "Thumbnail", "mimeType": "image/png", "bufferView": 0}]
        doc["extensions"]["VRMC_vrm"]["meta"]["thumbnailImage"] = 0
    text = json.dumps(doc).encode()
    text += b" " * (-len(text) % 4)
    blob += b"\0" * (-len(blob) % 4)
    body = struct.pack("<II", len(text), 0x4E4F534A) + text + struct.pack("<II", len(blob), 0x004E4942) + blob
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    premade = tmp_path / "premade"
    for waifu_id in ("alpha", "alpha-2", "beta"):
        make_pack(premade, waifu_id)
    (premade / "alpha" / "model.vrm").write_bytes(glb(png(400, 300)))
    (premade / "alpha-2" / "model.vrm").write_bytes(glb(png(64, 64, (0, 0, 255))))
    (premade / "beta" / "model.vrm").write_bytes(glb(None))     # a VRM without a thumbnail
    reg = WaifuRegistry(premade, tmp_path / "user")
    monkeypatch.setattr(waifus.registry, "_registry", reg)
    return reg


def test_the_thumbnail_is_read_from_the_vrm(registry):
    raw = portrait.vrm_thumbnail(registry.get("alpha").vrm_path)
    assert Image.open(io.BytesIO(raw)).size == (400, 300)
    assert portrait.vrm_thumbnail(registry.get("beta").vrm_path) is None


@pytest.mark.parametrize("data", [b"", b"glTF-not-really", b"PK\3\4zipfile", glb(png(8, 8))[:40]])
def test_a_broken_or_foreign_file_has_no_thumbnail(tmp_path, data):
    path = tmp_path / "x.vrm"
    path.write_bytes(data)
    assert portrait.vrm_thumbnail(path) is None


def test_the_portrait_is_a_cached_centred_square(registry, monkeypatch):
    alpha = registry.get("alpha")
    first = portrait.portrait_file(alpha)
    assert Image.open(first).size == (portrait.SIZE, portrait.SIZE)

    def unread(path):
        raise AssertionError("the cache should have answered")

    monkeypatch.setattr(portrait, "vrm_thumbnail", unread)
    assert portrait.portrait_file(alpha) == first


def test_the_square_is_cut_from_the_middle():
    img = Image.new("RGB", (400, 300), (0, 0, 255))
    img.paste((255, 0, 0), (0, 0, 50, 300))                     # a stripe the centred crop leaves out
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    out = Image.open(io.BytesIO(portrait.square(buf.getvalue()))).convert("RGB")
    assert out.getpixel((0, 128)) == (0, 0, 255) and out.size == (portrait.SIZE, portrait.SIZE)


def test_a_new_vrm_replaces_only_her_own_cached_face(registry):
    alpha, alpha2 = registry.get("alpha"), registry.get("alpha-2")
    old, other = portrait.portrait_file(alpha), portrait.portrait_file(alpha2)
    alpha.vrm_path.write_bytes(glb(png(300, 300, (10, 200, 10))))
    os.utime(alpha.vrm_path, ns=(1, 1))                         # a different stamp even on a coarse clock
    new = portrait.portrait_file(alpha)
    assert new != old and not old.exists()
    assert other.exists()                                       # "alpha-…" did not match "alpha-2-…"
    assert Image.open(new).getpixel((128, 128))[:3] == (10, 200, 10)


def test_her_chosen_picture_wins_and_changes_the_version(registry):
    alpha = registry.get("alpha")
    before = portrait.version(alpha)
    chosen = portrait.chosen_path("alpha")
    chosen.parent.mkdir(parents=True, exist_ok=True)
    chosen.write_bytes(portrait.square(png(50, 80)))
    assert portrait.portrait_file(alpha) == chosen
    assert portrait.version(alpha) != before


def test_square_refuses_what_is_not_an_image():
    with pytest.raises(ValueError):
        portrait.square(b"not an image at all")


def test_the_roster_carries_a_version_and_the_route_serves_the_face(registry):
    info = {w["id"]: w for w in registry.describe()}
    assert info["alpha"]["portrait"] and info["beta"]["portrait"]   # a stamp; the route decides
    client = TestClient(kernel_app.app)
    reply = client.get(f"/waifus/alpha/portrait?v={info['alpha']['portrait']}")
    assert reply.status_code == 200 and reply.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(reply.content)).size == (portrait.SIZE, portrait.SIZE)
    assert client.get("/waifus/beta/portrait").status_code == 404    # no thumbnail: her initial
    assert client.get("/waifus/nobody/portrait").status_code == 404
