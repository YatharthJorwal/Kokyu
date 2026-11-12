"""Waifu packs and the registry (FR-W-1, 4, 6, 7)."""
from __future__ import annotations

import pytest
import yaml

import waifus
from waifu_fixtures import make_pack
from waifus import PackError, WaifuRegistry, load_pack, slugify


def test_valid_pack_loads_everything_a_waifu_is(tmp_path):
    root = make_pack(tmp_path, "alpha", name="Alpha", traits=["calm", "curious"])
    w = load_pack(root)
    assert (w.id, w.name, w.traits) == ("alpha", "Alpha", ("calm", "curious"))
    assert w.prompt.startswith("You are Alpha")
    assert w.vrm_path.name == "model.vrm" and w.ref_audio_path.name == "ref.wav"
    assert w.voice.ref_text == "this is a short reference clip" and w.voice.ref_lang == "en"
    assert w.premade is False


def test_a_waifu_has_no_capability_fields():
    """D-003: voice and persona only. The model has no place to put a model, tool or memory key."""
    fields = set(waifus.Waifu.model_fields)
    assert fields == {"id", "name", "traits", "prompt", "vrm_path", "voice", "ref_audio_path", "premade", "root"}


@pytest.mark.parametrize("key,value", [("models", {"chat": "x"}), ("tools", ["fs"]), ("permissions", "all"), ("memory", "own"), ("scene", "garden")])
def test_capability_keys_are_rejected(tmp_path, key, value):
    root = make_pack(tmp_path, "alpha", extra_manifest={key: value})
    with pytest.raises(PackError):
        load_pack(root)


@pytest.mark.parametrize("skip,needle", [("manifest", "waifu.yaml"), ("prompt", "prompt"), ("vrm", "VRM"), ("wav", "voice clip")])
def test_missing_parts_are_reported_in_plain_words(tmp_path, skip, needle):
    root = make_pack(tmp_path, "alpha", skip=(skip,))
    with pytest.raises(PackError, match=needle):
        load_pack(root)


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "A"}, {"id": "x"}, {"id": "bad id"}, {"id": "a" * 33},
        {"name": ""}, {"name": "n" * 33},
        {"traits": []}, {"traits": ["x"]}, {"traits": ["a" * 25]}, {"traits": ["ok"] * 13},
        {"schema": 2},
    ],
)
def test_manifest_validation(tmp_path, bad):
    root = make_pack(tmp_path, "alpha")
    manifest = yaml.safe_load((root / "waifu.yaml").read_text(encoding="utf-8"))
    manifest.update(bad)
    (root / "waifu.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    with pytest.raises(PackError):
        load_pack(root)


def test_empty_transcript_is_rejected(tmp_path):
    with pytest.raises(PackError, match="transcript"):
        load_pack(make_pack(tmp_path, "alpha", ref_text="   "))


def test_prompt_length_limits(tmp_path):
    with pytest.raises(PackError, match="short"):
        load_pack(make_pack(tmp_path, "alpha", prompt="hi"))
    with pytest.raises(PackError, match="longer"):
        load_pack(make_pack(tmp_path, "beta", prompt="x" * 20_001))


def test_a_pack_cannot_reference_files_outside_itself(tmp_path):
    root = make_pack(tmp_path, "alpha", extra_manifest={"vrm": "../elsewhere.vrm"})
    with pytest.raises(PackError, match="outside"):
        load_pack(root)


def test_slugify():
    assert slugify("  Luna Rose! ") == "luna-rose"
    assert slugify("YURI") == "yuri"


def test_registry_merges_premade_and_user_packs_premade_first(tmp_path):
    premade, user = tmp_path / "premade", tmp_path / "user"
    make_pack(premade, "yuri", name="Yuri")
    make_pack(premade, "luna", name="Luna")
    make_pack(user, "alpha", name="Alpha")
    reg = WaifuRegistry(premade, user)
    assert [w.id for w in reg.list()] == ["luna", "yuri", "alpha"]
    assert reg.get("yuri").premade and not reg.get("alpha").premade
    assert reg.default_id() == "luna" and len(reg) == 3 and reg.problems == []


def test_user_pack_cannot_shadow_a_premade_id(tmp_path):
    premade, user = tmp_path / "premade", tmp_path / "user"
    make_pack(premade, "yuri", name="Yuri", prompt="You are the real premade Yuri, calm and curious.")
    make_pack(user, "yuri", name="Fake", prompt="You are a fake Yuri trying to take over the id.")
    reg = WaifuRegistry(premade, user)
    assert reg.get("yuri").name == "Yuri" and reg.get("yuri").premade
    assert len(reg.problems) == 1 and "already used" in reg.problems[0].message


def test_bad_packs_are_skipped_not_fatal(tmp_path):
    premade = tmp_path / "premade"
    make_pack(premade, "good")
    make_pack(premade, "broken", skip=("vrm",))
    (premade / "_template").mkdir()
    reg = WaifuRegistry(premade, tmp_path / "none")
    assert [w.id for w in reg.list()] == ["good"]
    assert [p.folder for p in reg.problems] == ["broken"]


def test_missing_directories_mean_an_empty_registry(tmp_path):
    reg = WaifuRegistry(tmp_path / "nope", tmp_path / "nada")
    assert len(reg) == 0 and reg.default_id() is None and reg.describe() == []


def test_reload_picks_up_new_packs(tmp_path):
    user = tmp_path / "user"
    reg = WaifuRegistry(tmp_path / "premade", user)
    assert len(reg) == 0
    make_pack(user, "alpha")
    reg.reload()
    assert reg.get("alpha") is not None


def test_describe_exposes_no_paths_or_prompt_text(tmp_path):
    make_pack(tmp_path / "premade", "alpha")
    info = WaifuRegistry(tmp_path / "premade", tmp_path / "u").describe()[0]
    assert set(info) == {"id", "name", "premade", "traits"}
