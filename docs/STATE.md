# STATE — Kōkyū

**Living document.** The truth *right now*. Rewrite it at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. Narrative lives in `HANDOFF.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-12, session 2
- **Current phase:** **K0 code-complete.** Waiting for the user's manual gate on the PC (below). K1 has not started.
- **Repo:** `github.com/YatharthJorwal/Kokyu`, `main` at `346f0c3` on the remote; the session-2 work is a bundle on top of it (not merged when this was written).
- **License:** proprietary, all rights reserved (D-040). The repository should be private.
- **Seed:** Yuri `e32af4f710cdf4e8c141df667a18c53046557ea3`, copied verbatim in commit `0cd2d20`.
- **Last green run (sandbox, Linux):** `npm run check -- --skip-cargo`: tsc, frontend tests (76), vite build, pytest (718). Cargo skipped.

## 1. What exists

| Area | State |
|---|---|
| Docs, README, proprietary LICENSE, `THIRD-PARTY.md` | Written |
| Kernel `KASANE/` (flat modules): seeded from Yuri, renamed, port 8780, `paths.py`, waifu packs and registry, `prompting.py`, per-waifu TTS, speaker-tagged memory (schema v3), `switch_waifu`, `GET /waifus/{id}/vrm` | Done and tested |
| Shell: Yuri's stage widget + a Companion picker in the quick-action menu, caption-only playback, per-waifu avatar by reload | Done; **only built and unit-tested here** |
| `scripts/build_premade.py` (premade Luna and Yuri packs from the user's files) | Done and tested with fixtures; **not yet run on the real files** |
| `npm run check` | Done |
| Premade packs `assets/premade/{luna,yuri}/` | **Do not exist yet**: the VRMs and `.wav` files are on the user's disk, not in git (transcripts are in `KASANE/voice_files/`) |
| Chat UI, sidebar, threads, model switcher, creator, pets, 3D | Not started (K1 onward) |
| TTS backend (Track T) | Not started; development uses the existing install (D-042) |

## 2. Environment

### Stated by the user

| Item | Value |
|---|---|
| GPU / CPU / RAM | RTX 3060 12 GB; i5-14400F; 32 GB DDR5-4800 |
| OS | Windows (PowerShell); local folder `Kokyu.ai` |
| GPT-SoVITS install | `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (**a space in the path**) |
| Ollama models | `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L`, `qwen3.5:9b`, `qwen3.5:4b`, `nomic-embed-text` |
| llama.cpp | Qwen3.5-35B-A3B Q4 available |
| API | AI Router key |
| Assets | VRMs made by the user; voices generated on the ElevenLabs website (AI-generated) |
| VR headset | None |

### Sandbox (Claude's session)

Linux, Python 3.12, Node 22. No Rust build, GPU, display, audio, Ollama or GPT-SoVITS.

### Unknown on the user's PC

Node, Rust, Python versions; WebView2; where the Luna repo and the VRM files live; whether `cargo check` passes.

## 3. Verification status

| Claim | Status |
|---|---|
| Seed copy is green (641 pytest, 65 frontend, tsc, build) | **Verified** (sandbox) |
| Current tree: pytest 718, test:fe 76, tsc, vite build | **Verified** (sandbox, `npm run check -- --skip-cargo`) |
| Real kernel over a real websocket: connect sends `waifu_state`; `switch_waifu` changes the active waifu; unknown id gives an error; choice remembered; `GET /waifus/{id}/vrm` serves the file with the right content type | **Verified** (sandbox, throwaway fixture packs) |
| Invariance: a turn differs between waifus only in the system prompt and the TTS parameters; router signatures carry no waifu | **Verified** (tests) |
| `cargo check` / the Rust edits (port 8780, `KOKYU_SHELL_STARTS_TTS`, `../KASANE` working directory, identifier, title) | **Not verified** (constants and strings only) |
| The window opens, the Companion picker works, the avatar swaps on reload, loads from the kernel | **Not verified** (needs the PC) |
| Audible voice per waifu with the real clips on the real GPT-SoVITS | **Not verified** (needs the PC) |
| `build_premade.py` on the real VRMs, wavs, and the Luna repo | **Not verified** (fixtures only) |
| The Rust launcher reads a `GPT_SOVITS_DIR` containing a space | **Not verified** (Yuri's example says no quotes are needed) |
| GPT-SoVITS API fields beyond the five in use; Ollama silent install; built-in voice model; Dodo policies | **Unverified** (later phases) |
| Latency, fps, VRAM numbers | **Targets / estimates** only |

## 4. Known issues and risks

- **First launch reloads once:** with no stored companion the page loads, the kernel names the active waifu, the page stores it and reloads to get her avatar. Temporary (D-046).
- **Parked features are still switched on:** Task Guide and OCR watch (D-029) are untouched in the code and still in the quick-action menu; hiding them is a K1 item.
- **`memory.db` moved** to `<repo>/data/memory.db` (it used to be inside the kernel folder). Nothing from Yuri's old memory is imported.
- **Cosmetic leftovers:** Cargo package/binary `yuri`, log file `orchestrator.log`, the old `window.__YURI_MODEL_PATH__` override, some "yuri" log prefixes (K7 / cleanup).
- Inherited: faster-whisper on CUDA failed on this machine (CPU STT); port 1420 is shared by `dev:ui` and `tauri dev`; killing instead of tray Quit loses that session's memory consolidation.
- Risks from the scope still apply (`SCOPE.md` §13).

## 5. Recent issues log

| Date | Area | Issue | Status |
|---|---|---|---|
| 2026-11-12 | build | A `tests/__init__.py` made pytest fail to collect 7 files | Removed; shared fixtures are imported as `waifu_fixtures` (no package) |
| 2026-11-12 | gitignore | `*.local.*` ignored `launcher.local.txt.example`; the animation notices were ignored | Fixed before the seed commit |
| 2026-11-12 | docs | Early docs assumed a `kasane` package and a draft protocol | Corrected (D-024) |

## 6. Manual gate: K0 (the user, on the PC)

Commands are in `HANDOFF.md` §5. Tick and date when done.

- [ ] `npm run check` passes on the PC (including `cargo check`)
- [ ] `scripts/build_premade.py` builds Luna and Yuri from the real files
- [ ] `npm run tauri dev` opens the Kokyū window
- [ ] The Companion picker (quick-action menu) switches Luna ↔ Yuri: the page reloads once and shows the other avatar
- [ ] Replies change persona; the voice is audibly different per companion (existing GPT-SoVITS)
- [ ] With GPT-SoVITS stopped: the reply still appears as a caption, no robotic voice

| Gate | Date | Evidence | Signed by |
|---|---|---|---|
| K0 (sandbox, automated) | 2026-11-12 | `npm run check -- --skip-cargo` green | Claude |
| K0 (manual, PC) | | | |

## 7. Update checklist (end of every session)

- [ ] Snapshot header rewritten
- [ ] "What exists" matches the repo
- [ ] Verification table honest
- [ ] Issues logged; gate sign-offs recorded
