# Premade companions

Luna and Yuri ship with the app as built-in, read-only packs (D-041). One folder per companion:

```
assets/premade/<id>/
  waifu.yaml      name, traits, voice settings
  prompt.md       persona prompt
  model.vrm       avatar
  voice/ref.wav   zero-shot reference clip (about 8 s)
```

Do not edit these by hand. Rebuild them with `python scripts/build_premade.py --help`.
The kernel loads them through `KASANE/paths.py` (`premade_dir()`); a user-created waifu can
never reuse one of these ids.
