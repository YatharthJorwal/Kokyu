#!/usr/bin/env python3
"""Assemble the premade companion packs (Luna, Yuri) from the user's own files (D-041).

    python scripts/build_premade.py --yuri-vrm C:\\path\\yuri.vrm --luna-vrm C:\\path\\luna.vrm

Inputs, per companion:
  * voice clip + transcript: KASANE/voice_files/<Name>/ (exactly one .wav and transcript.txt)
  * VRM: the path you pass
  * persona prompt: Yuri's from KASANE/persona.py (SYSTEM_PROMPT), Luna's from the Luna repo
    (--luna-repo, default ../Luna, file orchestrator/persona.py). The prompt text is read from
    those files and copied verbatim; this script never writes or edits persona text.

Output: assets/premade/<id>/{waifu.yaml, prompt.md, model.vrm, voice/ref.wav}, validated with the
same loader the kernel uses. Safe to re-run with --force. Nothing is deleted.
"""
from __future__ import annotations

import argparse
import ast
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "KASANE"))

from waifus import PackError, load_pack  # noqa: E402

COMPANIONS = {
    "yuri": {"name": "Yuri", "voice_dir": "Yuri"},
    "luna": {"name": "Luna", "voice_dir": "Luna"},
}


class BuildError(RuntimeError):
    pass


def extract_system_prompt(persona_py: Path) -> str:
    """Reads the SYSTEM_PROMPT string constant out of a persona.py without importing it."""
    if not persona_py.is_file():
        raise BuildError(f"persona file not found: {persona_py}")
    tree = ast.parse(persona_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SYSTEM_PROMPT" for t in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError as exc:
                raise BuildError(f"{persona_py}: SYSTEM_PROMPT is not a plain string constant") from exc
            if not isinstance(value, str) or not value.strip():
                raise BuildError(f"{persona_py}: SYSTEM_PROMPT is empty")
            return value.strip()
    raise BuildError(f"{persona_py}: no SYSTEM_PROMPT constant found")


def find_voice(voice_root: Path, folder: str) -> tuple[Path, str]:
    d = voice_root / folder
    wavs = sorted(d.glob("*.wav"))
    if len(wavs) != 1:
        raise BuildError(f"{d}: expected exactly one .wav voice clip, found {len(wavs)}")
    transcript = d / "transcript.txt"
    if not transcript.is_file():
        raise BuildError(f"{d}: transcript.txt is missing")
    text = transcript.read_text(encoding="utf-8").strip()
    if not text:
        raise BuildError(f"{transcript}: the transcript is empty")
    return wavs[0], text


def build_pack(
    out_dir: Path, companion_id: str, *, vrm: Path, voice_wav: Path, transcript: str,
    prompt: str, traits: list[str], force: bool,
) -> Path:
    meta = COMPANIONS[companion_id]
    pack = out_dir / companion_id
    if pack.exists():
        if not force:
            raise BuildError(f"{pack} already exists (use --force to rebuild it)")
        shutil.rmtree(pack)
    if not vrm.is_file() or vrm.suffix.lower() != ".vrm":
        raise BuildError(f"{meta['name']}: VRM file not found or not a .vrm: {vrm}")
    (pack / "voice").mkdir(parents=True)
    shutil.copy2(vrm, pack / "model.vrm")
    shutil.copy2(voice_wav, pack / "voice" / "ref.wav")
    (pack / "prompt.md").write_text(prompt + "\n", encoding="utf-8")
    manifest = {
        "schema": 1,
        "id": companion_id,
        "name": meta["name"],
        "traits": traits,
        "vrm": "model.vrm",
        "prompt": "prompt.md",
        "voice": {"provider": "gpt_sovits", "ref_audio": "voice/ref.wav", "ref_text": transcript, "ref_lang": "en"},
    }
    (pack / "waifu.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    try:
        load_pack(pack, premade=True)
    except PackError as exc:
        raise BuildError(f"built pack failed validation: {exc}") from exc
    return pack


def _traits(text: str | None) -> list[str]:
    items = [t.strip() for t in (text or "").split(",") if t.strip()]
    return items or ["companion"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yuri-vrm", type=Path, required=True)
    ap.add_argument("--luna-vrm", type=Path, required=True)
    ap.add_argument("--luna-repo", type=Path, default=ROOT.parent / "Luna", help="Luna checkout (default: ../Luna)")
    ap.add_argument("--yuri-persona", type=Path, default=ROOT / "KASANE" / "persona.py")
    ap.add_argument("--voice-root", type=Path, default=ROOT / "KASANE" / "voice_files")
    ap.add_argument("--out", type=Path, default=ROOT / "assets" / "premade")
    ap.add_argument("--yuri-traits", help="comma-separated adjectives, e.g. 'calm,teasing'")
    ap.add_argument("--luna-traits", help="comma-separated adjectives")
    ap.add_argument("--force", action="store_true", help="rebuild packs that already exist")
    args = ap.parse_args(argv)

    plan = {
        "yuri": (args.yuri_vrm, args.yuri_persona, _traits(args.yuri_traits)),
        "luna": (args.luna_vrm, args.luna_repo / "orchestrator" / "persona.py", _traits(args.luna_traits)),
    }
    try:
        for cid, (vrm, persona_py, traits) in plan.items():
            wav, text = find_voice(args.voice_root, COMPANIONS[cid]["voice_dir"])
            pack = build_pack(args.out, cid, vrm=vrm, voice_wav=wav, transcript=text,
                              prompt=extract_system_prompt(persona_py), traits=traits, force=args.force)
            note = "  (edit the traits in waifu.yaml)" if traits == ["companion"] else ""
            print(f"built {pack.relative_to(ROOT) if pack.is_relative_to(ROOT) else pack}{note}")
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("done. Review with `git status`, then commit assets/premade/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
