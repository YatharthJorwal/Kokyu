"""scripts/build_premade.py assembles valid premade packs from the user's files (D-041)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import paths
from waifus import WaifuRegistry

_SPEC = importlib.util.spec_from_file_location("build_premade", paths.repo_root() / "scripts" / "build_premade.py")
build_premade = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_premade)


def _persona_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'"""doc"""\nSYSTEM_PROMPT = (\n    {text[:30]!r}\n    {text[30:]!r}\n)\nOTHER = 1\n', encoding="utf-8")
    return path


@pytest.fixture
def sources(tmp_path):
    voices = tmp_path / "voice_files"
    for name in ("Luna", "Yuri"):
        (voices / name).mkdir(parents=True)
        (voices / name / f"{name.lower()}_sample.wav").write_bytes(b"RIFF-" + name.encode())
        (voices / name / "transcript.txt").write_text(f"{name} reference transcript.\n", encoding="utf-8")
    (tmp_path / "luna.vrm").write_bytes(b"glTF-luna")
    (tmp_path / "yuri.vrm").write_bytes(b"glTF-yuri")
    yuri_persona = _persona_file(tmp_path / "yuri_persona.py", "You are Yuri. Stay in character and keep replies short.")
    _persona_file(tmp_path / "Luna" / "orchestrator" / "persona.py", "You are Luna. Stay in character and keep replies short.")
    return tmp_path, voices, yuri_persona


def _args(tmp, voices, yuri_persona, *extra):
    return [
        "--yuri-vrm", str(tmp / "yuri.vrm"), "--luna-vrm", str(tmp / "luna.vrm"),
        "--luna-repo", str(tmp / "Luna"), "--yuri-persona", str(yuri_persona),
        "--voice-root", str(voices), "--out", str(tmp / "out"), *extra,
    ]


def test_builds_two_packs_the_kernel_accepts(sources, capsys):
    tmp, voices, yp = sources
    assert build_premade.main(_args(tmp, voices, yp, "--yuri-traits", "calm,teasing", "--luna-traits", "cute,gentle")) == 0
    reg = WaifuRegistry(tmp / "out", tmp / "none")
    assert [w.id for w in reg.list()] == ["luna", "yuri"] and reg.problems == []
    yuri, luna = reg.get("yuri"), reg.get("luna")
    assert yuri.premade and yuri.traits == ("calm", "teasing") and luna.traits == ("cute", "gentle")
    assert yuri.prompt == "You are Yuri. Stay in character and keep replies short."   # copied verbatim
    assert luna.prompt.startswith("You are Luna.")
    assert yuri.voice.ref_text == "Yuri reference transcript."
    assert yuri.ref_audio_path.read_bytes() == b"RIFF-Yuri" and luna.vrm_path.read_bytes() == b"glTF-luna"


def test_refuses_to_overwrite_without_force(sources, capsys):
    tmp, voices, yp = sources
    assert build_premade.main(_args(tmp, voices, yp)) == 0
    assert build_premade.main(_args(tmp, voices, yp)) == 1
    assert "already exists" in capsys.readouterr().err
    assert build_premade.main(_args(tmp, voices, yp, "--force")) == 0


def test_missing_traits_default_to_a_placeholder_and_say_so(sources, capsys):
    tmp, voices, yp = sources
    assert build_premade.main(_args(tmp, voices, yp)) == 0
    assert "edit the traits" in capsys.readouterr().out


def test_two_wavs_or_no_transcript_is_a_clear_error(sources, capsys):
    tmp, voices, yp = sources
    (voices / "Luna" / "second.wav").write_bytes(b"x")
    assert build_premade.main(_args(tmp, voices, yp)) == 1
    assert "exactly one .wav" in capsys.readouterr().err
    (voices / "Luna" / "second.wav").unlink()
    (voices / "Luna" / "transcript.txt").unlink()
    assert build_premade.main(_args(tmp, voices, yp, "--force")) == 1
    assert "transcript.txt is missing" in capsys.readouterr().err


def test_persona_without_a_plain_constant_is_rejected(tmp_path):
    bad = tmp_path / "persona.py"
    bad.write_text("SYSTEM_PROMPT = f'x{1}'\n", encoding="utf-8")
    with pytest.raises(build_premade.BuildError):
        build_premade.extract_system_prompt(bad)
    with pytest.raises(build_premade.BuildError):
        build_premade.extract_system_prompt(tmp_path / "missing.py")


def test_the_real_yuri_persona_file_is_readable_by_the_extractor():
    text = build_premade.extract_system_prompt(paths.repo_root() / "KASANE" / "persona.py")
    assert len(text) > 200
