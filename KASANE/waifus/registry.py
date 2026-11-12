"""All waifus the kernel knows: premade (read-only) plus the user's own (FR-W-7).

Invalid packs are skipped and reported, never fatal (FR-W-6). A user pack can never
shadow a premade id. Nothing here knows about models, tools or memory (R-01).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import paths
from waifus.pack import PackError, Waifu, load_pack

log = logging.getLogger("kokyu.waifus")


@dataclass(frozen=True)
class PackProblem:
    folder: str
    message: str


class WaifuRegistry:
    def __init__(self, premade_dir: Path | None = None, user_dir: Path | None = None) -> None:
        self._premade_dir = Path(premade_dir) if premade_dir is not None else paths.premade_dir()
        self._user_dir = Path(user_dir) if user_dir is not None else paths.waifus_dir()
        self._waifus: dict[str, Waifu] = {}
        self._problems: list[PackProblem] = []
        self.reload()

    def reload(self) -> list[PackProblem]:
        waifus: dict[str, Waifu] = {}
        problems: list[PackProblem] = []
        for premade, folder in ((True, self._premade_dir), (False, self._user_dir)):
            for pack_dir in _pack_dirs(folder):
                try:
                    waifu = load_pack(pack_dir, premade=premade)
                except PackError as exc:
                    problems.append(PackProblem(pack_dir.name, str(exc)))
                    log.warning("skipping waifu pack: %s", exc)
                    continue
                if waifu.id in waifus:
                    kind = "a premade companion" if waifus[waifu.id].premade else "another pack"
                    problems.append(PackProblem(pack_dir.name, f"{pack_dir.name}: id {waifu.id!r} is already used by {kind}"))
                    continue
                waifus[waifu.id] = waifu
        self._waifus = waifus
        self._problems = problems
        return list(problems)

    @property
    def problems(self) -> list[PackProblem]:
        return list(self._problems)

    def list(self) -> list[Waifu]:
        """Premade first (stable order), then user packs by name."""
        return sorted(self._waifus.values(), key=lambda w: (not w.premade, w.name.lower(), w.id))

    def get(self, waifu_id: str) -> Waifu | None:
        return self._waifus.get(waifu_id)

    def default_id(self) -> str | None:
        waifus = self.list()
        return waifus[0].id if waifus else None

    def __len__(self) -> int:
        return len(self._waifus)

    def describe(self) -> list[dict]:
        """What clients may know about each waifu. No paths, no prompt text."""
        return [{"id": w.id, "name": w.name, "premade": w.premade, "traits": list(w.traits)} for w in self.list()]


def _pack_dirs(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


_registry: WaifuRegistry | None = None


def get_registry() -> WaifuRegistry:
    global _registry
    if _registry is None:
        _registry = WaifuRegistry()
    return _registry


def reset_registry() -> None:
    """Tests and the creator call this after packs change on disk."""
    global _registry
    _registry = None
