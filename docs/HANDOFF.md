# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** If the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-12
- **Session:** 2 (license, spec baseline, Phase 0 code)
- **Written by:** Claude, with the user (Yatharth)

## 1. The project in ten lines

1. Kōkyū: a Windows chat app for a roster of AI companions; KASANE (`KASANE/`) is the Python kernel; Tauri + three.js shell.
2. A waifu is a **voice and a persona only**; she never changes the model, intelligence or capabilities. Memory is shared. (D-003, D-005)
3. **Luna and Yuri ship as the two premade companions** with the user's own assets (D-041).
4. The code is **proprietary**, not open source (D-040); keep the repo private.
5. Zero-shot voices: each request carries the speaking waifu's clip and transcript (D-006). Development uses the existing GPT-SoVITS at `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (D-042).
6. Seeded from Yuri (verbatim commit `0cd2d20`), renamed to `KASANE/`, port 8780.
7. Commercial and release work (Dodo, website, signing) is deferred until the product is developed (D-043).
8. Spec v1.0 baseline is final (D-044). Changes go through new decisions.
9. Work is delivered as a git bundle (D-030); the sandbox cannot run Rust, GPU, audio or a window.
10. Plan: `TODO.md`; K0 done in code, K1 (chat shell, model switcher) is next.

## 2. How the user works

Solo developer, casual, wants direct commands (no manual file shuffling), phases with gates, honesty about verified vs not. Delivery: PowerShell merge of a bundle, then push.

## 3. What happened

### Session 2 (2026-11-12)
- **Decided by the user:** the project is not open source; Luna and Yuri are the defaults (their VRMs are self-made, voices generated on the ElevenLabs website); Dodo and release work wait; the SoVITS path; "finalize the spec and proceed". Recorded as D-040 to D-044; `LICENSE` is now proprietary; `.gitignore` allows committed assets only under `assets/premade/`.
- **Built (Phase 0), each step committed with tests:** verbatim seed of Yuri; rename `orchestrator/` → `KASANE/` and rebrand; `paths.py`; waifu packs and registry; shared prompt addendum; per-waifu TTS parameters with opt-in fallback; active waifu per connection with `switch_waifu`, `waifu_state`, the VRM endpoint; speaker-tagged shared memory (schema v3); invariance tests; `scripts/build_premade.py`; Companion picker and caption-only playback in the shell; `npm run check`; `THIRD-PARTY.md`.
- **Verified in the sandbox:** 718 pytest, 76 frontend tests, tsc, vite build, and a real kernel plus websocket smoke test. **Not verified:** Rust, the window, audio, the real assets (see `STATE.md` §3).
- **Surprises worth remembering:** the VRMs and `.wav` files were never in git (the earlier `.gitignore` excluded them; only the transcripts were committed); Yuri's prompt and tag rules are tangled, so premade prompts are copied verbatim and a shared addendum carries the emotion tag (D-045); adding `tests/__init__.py` broke pytest collection.

## 4. Where we stopped

K0 code is complete and committed in the sandbox clone and bundled. **Nothing has run on the user's PC yet.** The remaining K0 work is the user's manual gate (`STATE.md` §6).

## 5. Next session: start here

1. `git log`; confirm the session-2 bundle was merged and pushed. Ask for the results of the manual gate.
2. If the user hit problems, fix those first (likely suspects: `cargo check`, the launcher path with a space, the avatar reload, `build_premade.py` input paths).
3. Then ask the user to confirm **D-025** (API-model egress rule) and start **K1** (`TODO.md`): conversation manager and threads store, typed protocol and token streaming, `llm.py` model/effort parameters, the app window, hiding Task Guide and OCR watch.

**Commands for the user (PowerShell, in the repo folder):**

```powershell
# 1. merge the bundle and push
git pull --ff-only "C:\Users\User\Downloads\kokyu.bundle" main
git push

# 2. tell the Rust shell where GPT-SoVITS lives (gitignored file)
Set-Content -Path src-tauri\launcher.local.txt -Value 'GPT_SOVITS_DIR=D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228'

# 3. environment
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r KASANE\requirements-dev.txt
npm install

# 4. build the premade companions from your files (adjust the paths and traits)
.\.venv\Scripts\python.exe scripts\build_premade.py --yuri-vrm "C:\path\yuri.vrm" --luna-vrm "C:\path\luna.vrm" --luna-repo "C:\path\to\Luna" --yuri-traits "trait1,trait2" --luna-traits "trait1,trait2"
git status                      # expect assets/premade/luna and assets/premade/yuri (vrm + wav included)
git rm -r --cached KASANE/voice_files   # optional: the originals are copied into the packs

# 5. check and run
npm run check
npm run tauri dev

# 6. commit the premade companions
git add assets/premade
git commit -m "feat: premade companions Luna and Yuri"
git push
```

## 6. Open questions for the user

- OK with **D-025** (your chosen API model may receive files you attach, never camera/screen captures)? Needed at K1 start.
- Task Guide and OCR watch: park them (hide in the UI, keep the code) as proposed in D-029?
- Which traits describe Luna and Yuri (the build script needs 1 to 12 adjectives each; a placeholder is used if you give none)?
- Track the licensed VRMA animation pack in git (K4)?

## 7. Traps and gotchas

- **No bulk string replacement** in source (Yuri once corrupted five files that way); targeted edits, tests after each.
- Kernel modules are **flat**: `import paths`, `from audio import tts`. Tests have **no `__init__.py`**; shared helpers are imported by module name (`from waifu_fixtures import make_pack`).
- Tests stub `llm.<fn>`, `tts.synthesize` and `router.stream_with_tools` by module attribute. Keep one-argument stubs working: `_synthesize_for` calls `tts.synthesize(text)` with no voice when no waifu is active.
- `_run_turn` must never mention a waifu (a test enforces it). Persona and voice enter through `_system_message` and `_synthesize_for`.
- The kernel on **8780**, GPT-SoVITS on **9880**, Vite on **1420** (never run `dev:ui` with `tauri dev`).
- Quit via the tray; killing loses memory consolidation. STT stays on CPU.
- In the sandbox, never `pkill -f` with a pattern that appears in your own command line (it kills the shell).
- The path `GPT SoVITS` has a space: single-quote it in YAML; `launcher.local.txt` needs no quotes.
- Never commit secrets, databases, logs. Assets are committed **only** under `assets/premade/`.

## 8. Deliberately not done

- Real-window, audio and Rust verification (impossible in the sandbox).
- Hiding Task Guide and OCR watch; renaming Cargo/binary/log names; a `kernel.port` config key.
- Yuri's old memory is not imported into the new `memory.db`.
- Nothing from K1 onward.

## 9. Update checklist (end of every session)

- [ ] Date, session, author
- [ ] §3 new entry; §4 exact stopping point; §5 first actions; §6 open questions only
- [ ] §7 new traps; §8 skipped items
