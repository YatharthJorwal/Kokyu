"""Her pet (D-103, FR-P-2): chibi her, as up to twelve labelled poses.

A pet is made from one pose sheet: a 4×3 grid an image model drew from the prompt
the window gives. `make_draft` cuts the grid into cells (keying out a flat
background when the sheet has no transparency) and keeps them for the user to
check; `save` stores them under the pose names the user confirmed, on one shared
scale so her feet line up. The user's pets live in the app data folder; a premade
pet ships in her pack's `pet/` folder (premades are read-only, D-039).
Every function here blocks: call it in a thread.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import paths
import uploads
from waifus.pack import Waifu

COLS, ROWS = 4, 3
# The sheet's reading order. The window's prompt names them in this order.
POSES: tuple[str, ...] = (
    "idle", "walk_1", "walk_2", "sit",
    "sleep", "eat", "wave", "think",
    "talk", "happy", "sad", "surprised",
)
HEIGHT = 320                    # idle's height in px once saved; the window scales it by Size
MAX_SIDE = 4096                 # a bigger sheet is scaled down before cutting
# The size checker (D-107): the box each pose must fit, as (width, height) in HEIGHTs.
# The image model often draws some cells larger than others (her head bigger when
# sitting or lying), so a pose drawn too big for its box is shrunk to fit. Never grown:
# an arm raised or a hand on the chin may legitimately make a pose shorter or taller.
_BOX: dict[str, tuple[float, float]] = {
    **{pose: (1.0, 1.0) for pose in POSES},
    "happy": (1.0, 1.12),     # arms up
    "sit": (0.75, 0.74),
    "sleep": (0.72, 0.5),     # curled up on the floor
}
_KEY = (255, 0, 255)            # the fill colour that marks background while keying
_THRESH = 40                    # how far from the background colour still counts as background


def _open(data: bytes):
    from PIL import Image

    rgba = uploads.open_image(data)   # allowed formats and size only (D-106)
    if max(rgba.size) > MAX_SIDE:
        rgba.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    return rgba


def _has_transparency(img) -> bool:
    """At least 5% of the sheet is see-through: the model kept the background clear."""
    hist = img.getchannel("A").histogram()
    return sum(hist[:128]) >= 0.05 * img.width * img.height


def _key_out(img):
    """A flat background made see-through: flood-filled from every cell's edges, so a
    white shirt inside her outline stays. shortcut: no edge softening, so a
    contrasting halo can stay round her; upgrade to a matting model if sheets need it."""
    from PIL import Image, ImageChops, ImageDraw

    rgb = img.convert("RGB")
    corners = [rgb.getpixel(p) for p in ((0, 0), (rgb.width - 1, 0), (0, rgb.height - 1), (rgb.width - 1, rgb.height - 1))]
    bg = sorted(corners)[len(corners) // 2]

    def near(px) -> bool:
        return sum(abs(a - b) for a, b in zip(px, bg)) <= _THRESH * 3

    cw, ch = rgb.width / COLS, rgb.height / ROWS
    seeds: list[tuple[int, int]] = []
    for c in range(COLS):
        for r in range(ROWS):
            x0, y0 = int(c * cw), int(r * ch)
            x1, y1 = min(int((c + 1) * cw) - 1, rgb.width - 1), min(int((r + 1) * ch) - 1, rgb.height - 1)
            seeds += [(x, y) for x in range(x0, x1 + 1, 6) for y in (y0, y1)]
            seeds += [(x, y) for y in range(y0, y1 + 1, 6) for x in (x0, x1)]
    for xy in seeds:
        px = rgb.getpixel(xy)
        if px != _KEY and near(px):
            ImageDraw.floodfill(rgb, xy, _KEY, thresh=_THRESH)
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, _KEY)).convert("L")
    alpha = diff.point(lambda v: 255 if v > 0 else 0)
    out = img.copy()
    out.putalpha(ImageChops.multiply(alpha, img.getchannel("A")))
    return out


def cut(data: bytes) -> list:
    """The sheet's twelve cells in reading order, each trimmed to her outline, or None
    for an empty cell. Raises ValueError if `data` is not an image."""
    img = _open(data)
    if not _has_transparency(img):
        img = _key_out(img)
    cw, ch = img.width / COLS, img.height / ROWS
    cells = []
    for r in range(ROWS):
        for c in range(COLS):
            cell = img.crop((int(c * cw), int(r * ch), int((c + 1) * cw), int((r + 1) * ch)))
            box = cell.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
            tiny = box is None or (box[2] - box[0]) * (box[3] - box[1]) < 0.02 * cell.width * cell.height
            cells.append(None if tiny else cell.crop(box))
    return cells


def _dir(waifu_id: str) -> Path:
    return paths.pets_dir() / waifu_id


def draft_dir(waifu_id: str) -> Path:
    return _dir(waifu_id) / "draft"


def make_draft(waifu_id: str, data: bytes) -> list[bool]:
    """Cuts a sheet and keeps its cells for the user to check. Which cells hold a pose.
    Raises ValueError for a picture that is not a sheet of poses."""
    cells = cut(data)
    if not any(cells):
        raise ValueError("no poses found")
    folder = draft_dir(waifu_id)
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for n, cell in enumerate(cells):
        if cell is not None:
            cell.save(folder / f"cell_{n}.png", format="PNG", optimize=True)
    return [c is not None for c in cells]


def draft_file(waifu_id: str, n: int) -> Path | None:
    path = draft_dir(waifu_id) / f"cell_{n}.png"
    return path if path.is_file() else None


def save(waifu_id: str, labels: list[str | None]) -> None:
    """Stores the draft's cells as her pet, cell n under `labels[n]` (None: left out).
    All poses share one scale, set so *idle* (else the tallest) is HEIGHT px; then any
    pose too big for its box is shrunk to fit (`fit`).
    Raises ValueError for unknown or repeated labels, or when nothing is labelled."""
    from PIL import Image

    chosen = [(n, label) for n, label in enumerate(labels) if label is not None]
    names = [label for _, label in chosen]
    if not chosen:
        raise ValueError("no poses labelled")
    if any(label not in POSES for label in names) or len(set(names)) != len(names):
        raise ValueError("each pose may be used once")
    images = {}
    for n, label in chosen:
        path = draft_file(waifu_id, n)
        if path is None:
            raise ValueError("that cell is empty")
        with Image.open(path) as img:
            images[label] = img.convert("RGBA")
    base = images["idle"].height if "idle" in images else max(i.height for i in images.values())
    scale = HEIGHT / base
    tmp = _dir(waifu_id) / "live.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for label, img in images.items():
        k = scale * fit(label, img.width * scale, img.height * scale)
        size = (max(1, round(img.width * k)), max(1, round(img.height * k)))
        img.resize(size, Image.Resampling.LANCZOS).save(tmp / f"{label}.png", format="PNG", optimize=True)
    live = _dir(waifu_id) / "live"
    shutil.rmtree(live, ignore_errors=True)
    tmp.replace(live)
    shutil.rmtree(draft_dir(waifu_id), ignore_errors=True)


def fit(pose: str, width: float, height: float) -> float:
    """How much to shrink a pose drawn at `width` x `height` px so it fits its box: 1 if it already does."""
    bw, bh = _BOX.get(pose, (1.0, 1.0))
    return min(1.0, bw * HEIGHT / width, bh * HEIGHT / height)


def remove(waifu_id: str) -> None:
    """Her own pet goes; a premade one in her pack comes back."""
    shutil.rmtree(_dir(waifu_id), ignore_errors=True)


def folder(waifu: Waifu) -> Path | None:
    """Where her poses are: the user's, else her pack's, else None."""
    for candidate in (_dir(waifu.id) / "live", waifu.root / "pet"):
        if any(candidate.glob("*.png")):
            return candidate
    return None


def poses(waifu: Waifu) -> list[str]:
    where = folder(waifu)
    return [p for p in POSES if where is not None and (where / f"{p}.png").is_file()]


def version(waifu: Waifu) -> str | None:
    """Changes whenever her poses change, so the window's URLs do too."""
    where = folder(waifu)
    if where is None:
        return None
    try:
        stamps = [f.stat().st_mtime_ns for f in where.glob("*.png")]
    except OSError:
        return None
    return f"{max(stamps):x}-{len(stamps)}" if stamps else None


def pose_file(waifu: Waifu, pose: str) -> Path | None:
    if pose not in POSES:
        return None
    where = folder(waifu)
    path = where / f"{pose}.png" if where is not None else None
    return path if path is not None and path.is_file() else None
