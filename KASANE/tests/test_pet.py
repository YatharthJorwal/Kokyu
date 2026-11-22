"""Her pet from a pose sheet (D-103, FR-P-2). Sheets are drawn here; never real assets."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

import app as kernel_app
import waifus
from waifu_fixtures import make_pack
from waifus import WaifuRegistry, pet

CELL = 100


def sheet(*, transparent: bool = False, empty: tuple[int, ...] = (11,)) -> bytes:
    """A 4×3 sheet: in each cell a figure 40 px wide whose height grows with the cell
    number, standing on the cell's bottom margin, with a white patch enclosed inside it."""
    bg = (0, 0, 0, 0) if transparent else (255, 255, 255, 255)
    img = Image.new("RGBA", (4 * CELL, 3 * CELL), bg)
    draw = ImageDraw.Draw(img)
    for n in range(12):
        if n in empty:
            continue
        x0, y1 = (n % 4) * CELL + 30, (n // 4) * CELL + 90
        height = 39 + n * 3                          # +1: the box includes both edges
        draw.rectangle((x0, y1 - height, x0 + 39, y1), fill=(220, 60, 120, 255))
        draw.rectangle((x0 + 15, y1 - 20, x0 + 24, y1 - 10), fill=(255, 255, 255, 255))  # her white shirt
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKYU_DATA_DIR", str(tmp_path / "data"))
    premade = tmp_path / "premade"
    make_pack(premade, "alpha")
    make_pack(premade, "beta")
    reg = WaifuRegistry(premade, tmp_path / "user")
    monkeypatch.setattr(waifus.registry, "_registry", reg)
    return reg


def test_a_flat_background_is_keyed_out_but_her_white_shirt_stays():
    cells = pet.cut(sheet())
    assert cells[11] is None                       # an empty cell
    first = cells[0]
    assert first.size == (40, 40)                  # trimmed to her outline
    assert first.getpixel((0, 0))[3] == 255
    assert first.getpixel((19, 25)) == (255, 255, 255, 255)   # enclosed white is kept
    whole = Image.open(io.BytesIO(sheet())).convert("RGBA")
    assert whole.getpixel((5, 5))[3] == 255        # the sheet itself was opaque


def test_a_transparent_sheet_is_cut_as_it_is():
    cells = pet.cut(sheet(transparent=True))
    assert [c is None for c in cells] == [False] * 11 + [True]
    assert cells[5].size == (40, 55)


def test_not_a_picture_is_refused():
    with pytest.raises(ValueError):
        pet.cut(b"not a png")
    with pytest.raises(ValueError):
        pet.make_draft("alpha", sheet(empty=tuple(range(12))))


def test_saved_poses_share_one_scale_and_show_in_the_roster(registry):
    assert pet.make_draft("alpha", sheet()) == [True] * 11 + [False]
    labels = list(pet.POSES[:11]) + [None]
    pet.save("alpha", labels)
    alpha = registry.get("alpha")
    assert pet.poses(alpha) == list(pet.POSES[:11])
    idle = Image.open(pet.pose_file(alpha, "idle"))
    sit = Image.open(pet.pose_file(alpha, "sit"))
    assert idle.height == pet.HEIGHT
    # cell 3 (sit) is 49 px tall, idle 40: drawn too big for sitting, it is shrunk to its box
    assert sit.height == round(0.74 * pet.HEIGHT)
    assert Image.open(pet.pose_file(alpha, "walk_1")).height == pet.HEIGHT   # 43 px: taller than idle, so fitted
    assert pet.pose_file(alpha, "surprised") is None
    assert not pet.draft_dir("alpha").exists()
    row = next(w for w in registry.describe() if w["id"] == "alpha")
    assert row["pet"] and row["pet_own"] and row["pet_poses"][0] == "idle"
    assert next(w for w in registry.describe() if w["id"] == "beta")["pet"] is None


def test_labels_must_be_known_and_used_once(registry):
    pet.make_draft("alpha", sheet())
    with pytest.raises(ValueError):
        pet.save("alpha", ["idle", "idle"])
    with pytest.raises(ValueError):
        pet.save("alpha", ["dance"])
    with pytest.raises(ValueError):
        pet.save("alpha", [None] * 12)
    with pytest.raises(ValueError):
        pet.save("alpha", [None] * 11 + ["idle"])    # cell 11 is empty


def test_removing_her_own_pet_brings_back_the_premade_one(registry):
    alpha = registry.get("alpha")
    shipped = alpha.root / "pet"
    shipped.mkdir()
    Image.new("RGBA", (10, 20), (1, 2, 3, 255)).save(shipped / "idle.png")
    assert pet.folder(alpha) == shipped
    pet.make_draft("alpha", sheet())
    pet.save("alpha", ["idle", "walk_1"])
    assert pet.folder(alpha) != shipped
    pet.remove("alpha")
    assert pet.folder(alpha) == shipped and pet.poses(alpha) == ["idle"]


def test_the_routes_serve_poses_and_draft_cells(registry):
    pet.make_draft("alpha", sheet())
    client = TestClient(kernel_app.app)
    assert client.get("/waifus/alpha/pet-draft/0").status_code == 200
    assert client.get("/waifus/alpha/pet-draft/11").status_code == 404
    assert client.get("/waifus/alpha/pet-draft/99").status_code == 404
    pet.save("alpha", ["idle"])
    assert client.get("/waifus/alpha/pet/idle").headers["content-type"] == "image/png"
    assert client.get("/waifus/alpha/pet/walk_1").status_code == 404
    assert client.get("/waifus/alpha/pet/..%2Fsecret").status_code == 404
    assert client.get("/waifus/nobody/pet/idle").status_code == 404


def test_the_size_checker_only_shrinks_a_pose_drawn_too_big():
    assert pet.fit("idle", 200, 320) == 1.0
    assert pet.fit("think", 200, 300) == 1.0                 # smaller is left as drawn
    assert pet.fit("sit", 206, 269) == pytest.approx(0.74 * 320 / 269)
    assert pet.fit("sleep", 270, 192) == pytest.approx(0.5 * 320 / 192)    # too big lying down
    assert pet.fit("happy", 240, 350) == 1.0                 # arms up may stand taller


def _figure(scale: float, body: int) -> Image.Image:
    """A face (eyes, mouth, fringe) on a body `body` px tall, everything times `scale`."""
    s = lambda v: round(v * scale)
    img = Image.new("RGBA", (s(120), s(100 + body)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((s(10), s(5), s(110), s(100)), fill=(60, 40, 30, 255))            # hair
    d.ellipse((s(25), s(30), s(95), s(100)), fill=(250, 220, 200, 255))         # face
    for x in (40, 70):
        d.ellipse((s(x), s(55), s(x + 12), s(70)), fill=(90, 70, 160, 255))     # eyes
    d.rectangle((s(50), s(82), s(70), s(86)), fill=(200, 80, 90, 255))          # mouth
    d.rectangle((s(35), s(100), s(85), s(100 + body)), fill=(30, 30, 30, 255))  # body
    return img


def test_her_head_is_matched_across_poses_drawn_at_another_scale():
    idle = _figure(1.0, 130)
    assert pet.head_scale(idle, _figure(1.2, 40)) == pytest.approx(1.2, abs=0.05)   # sitting: a short body, a bigger head
    assert pet.head_scale(idle, _figure(0.9, 130)) == pytest.approx(0.9, abs=0.05)
    assert pet.head_scale(idle, Image.new("RGBA", (120, 200), (200, 0, 0, 255))) is None   # no head to be found
