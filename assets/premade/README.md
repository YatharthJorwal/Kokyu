# Premade companions

Luna and Yuri ship with the app as built-in, read-only packs (D-041). One folder per companion:

```
assets/premade/<id>/
  waifu.yaml      name, traits, voice settings
  prompt.md       persona prompt
  model.vrm       avatar
  voice/ref.wav   zero-shot reference clip (about 8 s)
```

Only the text is in git (D-118). `model.vrm` and `voice/ref.wav` are kept beside it and listed with their
SHA-256 in `ASSETS.sha256`; a fresh clone needs them copied in from the backup.

Do not edit these by hand. Rebuild them with `python scripts/build_premade.py --help`.
The kernel loads them through `KASANE/paths.py` (`premade_dir()`); a user-created waifu can
never reuse one of these ids.
