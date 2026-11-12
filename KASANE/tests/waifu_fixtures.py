"""Builds throwaway waifu packs for tests. Never touches real assets."""
from __future__ import annotations

from pathlib import Path

import yaml

PROMPTS = {
    "alpha": "You are Alpha, a calm and curious companion who answers in short spoken sentences.",
    "beta": "You are Beta, a playful and teasing companion who answers in short spoken sentences.",
}


def make_pack(
    root: Path,
    waifu_id: str,
    *,
    name: str | None = None,
    prompt: str | None = None,
    traits: list[str] | None = None,
    ref_text: str = "this is a short reference clip",
    skip: tuple[str, ...] = (),
    extra_manifest: dict | None = None,
) -> Path:
    pack = Path(root) / waifu_id
    (pack / "voice").mkdir(parents=True, exist_ok=True)
    if "prompt" not in skip:
        (pack / "prompt.md").write_text(prompt or PROMPTS.get(waifu_id, f"You are {waifu_id}, a test companion."), encoding="utf-8")
    if "vrm" not in skip:
        (pack / "model.vrm").write_bytes(b"glTF-not-really")
    if "wav" not in skip:
        (pack / "voice" / "ref.wav").write_bytes(b"RIFF-not-really")
    manifest = {
        "schema": 1,
        "id": waifu_id,
        "name": name or waifu_id.title(),
        "traits": traits or ["calm", "curious"],
        "vrm": "model.vrm",
        "prompt": "prompt.md",
        "voice": {"provider": "gpt_sovits", "ref_audio": "voice/ref.wav", "ref_text": ref_text, "ref_lang": "en"},
    }
    manifest.update(extra_manifest or {})
    if "manifest" not in skip:
        (pack / "waifu.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return pack
