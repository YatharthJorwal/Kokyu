# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** If the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-14
- **Session:** 3 (K1 begins: threads, typed protocol, streaming)
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
9. Since session 3, Claude works **directly on the user's Windows PC** (`D:\AI\Kokyu.ai`, via the Claude desktop app, often while the user is away) and commits and pushes `main` itself. Rust, Node and the venv are there; a window, audio and the GPU are there too, but Claude cannot see or hear them, so visual/audio results stay "not verified" until the user looks.
10. Plan: `TODO.md`; K1 in progress (K1-00, K1-00b done).

## 2. How the user works

Solo developer, casual, wants direct commands (no manual file shuffling), phases with gates, honesty about verified vs not. Session 3: "work on the next phase, commit for me and push", item by item, pushing after each green `npm run check`. Treats the feature list as growing ("we will discover features"); the phase plan stays.

## 3. What happened

### Session 3 (2026-11-14)
- **Run on the user's PC for the first time.** `npm run check` (with cargo) was red on Windows only because of a path-separator test bug; fixed (`baa0b54`). Everything else, including `cargo check`, passed.
- **Decided by the user:** D-025 approved (D-047). Task Guide and OCR watch become real features, "screen companions" (D-048, SPEC §2.17 FR-SC-1..6, TODO K1-05b). K1 starts without the K0 manual gate; deliver item by item.
- **Built:** K1-00 threads store + conversation manager (`5deb6b6`); K1-00b typed protocol v1 + token streaming (`32d9bef`, D-049).
- **Surprises:** a module-level `asyncio.Event` (`app._shutdown_event`) binds to the first event loop, so each TestClient test must patch in a fresh one; `_run_turn` reads `sys.exc_info()` in its `finally` to know Stop cut the reply.

### Session 2 (2026-11-12)
- **Decided by the user:** the project is not open source; Luna and Yuri are the defaults (their VRMs are self-made, voices generated on the ElevenLabs website); Dodo and release work wait; the SoVITS path; "finalize the spec and proceed". Recorded as D-040 to D-044; `LICENSE` is now proprietary; `.gitignore` allows committed assets only under `assets/premade/`.
- **Built (Phase 0), each step committed with tests:** verbatim seed of Yuri; rename `orchestrator/` → `KASANE/` and rebrand; `paths.py`; waifu packs and registry; shared prompt addendum; per-waifu TTS parameters with opt-in fallback; active waifu per connection with `switch_waifu`, `waifu_state`, the VRM endpoint; speaker-tagged shared memory (schema v3); invariance tests; `scripts/build_premade.py`; Companion picker and caption-only playback in the shell; `npm run check`; `THIRD-PARTY.md`.
- **Verified in the sandbox:** 718 pytest, 76 frontend tests, tsc, vite build, and a real kernel plus websocket smoke test. **Not verified:** Rust, the window, audio, the real assets (see `STATE.md` §3).
- **Surprises worth remembering:** the VRMs and `.wav` files were never in git (the earlier `.gitignore` excluded them; only the transcripts were committed); Yuri's prompt and tag rules are tangled, so premade prompts are copied verbatim and a shared addendum carries the emotion tag (D-045); adding `tests/__init__.py` broke pytest collection.

## 4. Where we stopped

K1-00 and K1-00b are done, green on the PC and pushed. Next is **K1-00c** (`llm.py` model/effort parameters, the `chat` role and the D-025 egress rules in `router/decision.py`). The UI still shows Yuri's widget; nothing in K1 is visible until K1-00d/K1-02.

## 5. Next session: start here

1. `git log -5`, `git status`, `npm run check` (set `KOKYU_PYTHON` to `.venv\Scripts\python.exe` if needed).
2. Continue K1 in TODO order: K1-00c, K1-00d (normal app window, CSP, Temp Chat per thread already stored), K1-01 (llama.cpp spike; can run on this PC), K1-02 (React shell on the v1 protocol).
3. The K0 manual gate is still open (`STATE.md` §6): building the premade packs needs the user's VRM/wav paths and traits.

**Commands the user may want (PowerShell, in the repo folder):**

```powershell
npm run check
npm run tauri dev
# premade companions (paths and traits are the user's):
.\.venv\Scripts\python.exe scriptsuild_premade.py --yuri-vrm "C:\path\yuri.vrm" --luna-vrm "C:\path\luna.vrm" --luna-repo "C:\path	o\Luna" --yuri-traits "trait1,trait2" --luna-traits "trait1,trait2"
```

## 6. Open questions for the user

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
- TestClient WebSocket tests: patch `app._shutdown_event` with a fresh `asyncio.Event()`, `app._driver` to None, `app._conversation_manager` to None, and set `KOKYU_DATA_DIR` to tmp, or `threads.db` lands in the real `data/` (see `tests/test_conversation.py`).
- Git Bash on this PC: `python3` exists; a `cmd1 <<EOF || cmd2 <<EOF` fallback runs the first heredoc and swallows the second. Use the venv Python directly.

## 8. Deliberately not done

- Real-window, audio and Rust verification (impossible in the sandbox).
- Hiding Task Guide and OCR watch; renaming Cargo/binary/log names; a `kernel.port` config key.
- Yuri's old memory is not imported into the new `memory.db`.
- K1 from K1-00c on.

## 9. Update checklist (end of every session)

- [ ] Date, session, author
- [ ] §3 new entry; §4 exact stopping point; §5 first actions; §6 open questions only
- [ ] §7 new traps; §8 skipped items
