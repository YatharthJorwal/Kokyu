# STATE — Kōkyū

**Living document.** The truth *right now*. Rewrite it at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. Narrative lives in `HANDOFF.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-15 (about 12:45), session 4 (in progress)
- **Current phase:** **K1 in progress.** Done: K1-00 to K1-08b except K1-04b and K1-07b. Left: K1-04b, K1-07b, K1-09, K1-11, K1-12, K1-13, K1-14, then the K1 gate. The K0 manual gate (window, voice) is still open (§6).
- **Repo:** `github.com/YatharthJorwal/Kokyu`, `main`. Last code commits `9a667ba` (lazy boot, D-060) and `d89c094` (app icon). **Not pushed:** the push was blocked by a permission prompt; the user pushes.
- **License:** proprietary, all rights reserved (D-040). The repository should be private.
- **Seed:** Yuri `e32af4f710cdf4e8c141df667a18c53046557ea3`, copied verbatim in commit `0cd2d20`.
- **Last green run (the user's PC, 2026-11-15, session 4):** tsc, frontend tests (121, one from the peer's uncommitted effort slider), vite build, `cargo check`; pytest 951 after D-060.

## 1. What exists

| Area | State |
|---|---|
| Docs, README, proprietary LICENSE, `THIRD-PARTY.md` | Written |
| Kernel `KASANE/` (flat modules): seeded from Yuri, renamed, port 8780, `paths.py`, waifu packs and registry, `prompting.py`, per-waifu TTS, speaker-tagged memory, `switch_waifu` | Done and tested |
| Threads store, conversation manager, typed protocol v1 with token streaming, per-thread model and effort, D-025 egress rules (K1-00 to K1-00c) | Done and tested; live local calls verified |
| Normal 1200×800 app window, explicit CSP (K1-00d) | Done; **the window was not looked at** |
| Lazy boot (D-060): port first, nothing heavy until a window connects, then chat model → GPT-SoVITS → (opt-in) STT → memory pass; llama.cpp only when picked or messaged; the kernel owns GPT-SoVITS (`tts.gpt_sovits.launch` in config.yaml; `launcher.local.txt` gone); default chat model on this PC `local:ollama/qwen3.5:9b` | Done; **live verified** with the real config in a scratch data dir (not in the Tauri window) |
| App icon from the owner's reference, transparent corners (`src-tauri/app-icon.png`, `icons/`, favicon) | Done; not looked at in the taskbar or tray |
| llama.cpp backend, Qwen3.6-35B-A3B as the default chat model, boot warm-up (K1-01, K1-01b; D-051, D-052) | Done; **live verified** |
| React chat window (K1-02, D-053); Yuri's widget still at `widget.html` | Done; verified live in a browser |
| Model chip and popover in the input row: Local (llama.cpp presets, Ollama) and API sections, search, badges, spend footer; one background loader with a "waking up" card, Try again / Switch model; an Ollama pick stops llama-server (K1-10, K1-07a; D-054) | Done; verified live in the browser pane (35B load 109 s, switch to the 9B 54 s) |
| Sidebar: companions, history grouped by day, search, inline rename, delete (K1-03) | Done; verified live in the browser pane |
| Markdown replies (in-house parser, no HTML from the model), Copy, kernel-side Regenerate and Retry (K1-04, D-055) | Done; verified live in the browser pane |
| `＋` tray (Upload file live, the rest disabled until K2), paste/drop attach, status heart (K1-05) | Done; verified live in the browser pane (drop, empty-file alert) |
| Screen companions: Task Guide and OCR watch in the tray, status chips, local-vision check (K1-05b, D-056) | Done; switched on and off live; a real nudge or OCR remark not seen end to end |
| Companion chip and "Switched to …" dividers; a switch mid-reply takes effect when the reply ends (K1-06) | Done; verified live with two test packs |
| Ambient content kept off API models; the kernel websocket refuses foreign Origins (D-057) | Done and tested |
| AI Router provider: catalog and cache, SSE streaming, spend ledger, budget caps with reservations, audit, redaction (K1-08, D-058) | Done and tested with fakes; **no live API call** (no key on this PC) |
| One API endpoint at a time (AI Router, OpenRouter, DeepSeek presets, or a custom one in config); key saved in the Windows Credential Manager by the shell, handed to the kernel at spawn and over its stdin when changed; Key form in the model menu (K1-08b, D-059) | Done and tested; live vault tests pass; **the form was not used in the Tauri window** |
| Premade packs `assets/premade/{luna,yuri}/` (VRM, prompt, voice, `waifu.yaml`) | **Built by a peer session, untracked.** The user decides whether VRM/WAV files get committed (D-041) |
| Peer work waiting for its TODO item (untracked, do not commit early): `KASANE/vram.py` + `tests/test_vram.py` (K1-09); `src/app/effort-slider.ts`, `ui/EffortSlider.tsx`, `ui/effort-slider.css`, `tests-fe/effort-slider.test.mjs` (K1-11) | Written, not integrated |
| Design references `docs/reference-images/` (chat UI, stage view, app icon; GPT Image, by the owner) | Stored for later; not used yet |
| VRAM manager, effort slider, inline API failure UX, Settings/Doctor/Memory viewer | Not started (K1-09, K1-11, K1-12, K1-13) |
| TTS backend (Track T) | Not started; development uses the existing install (D-042) |

## 2. Environment

### Stated by the user

| Item | Value |
|---|---|
| GPU / CPU / RAM | RTX 3060 12 GB; i5-14400F; 32 GB DDR5-4800 |
| OS | Windows 11 (PowerShell); repo at `D:\AI\Kokyu.ai` |
| GPT-SoVITS install | `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (**a space in the path**) |
| Ollama models | `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L`, `qwen3.5:9b`, `qwen3.5:4b`, `nomic-embed-text` |
| llama.cpp | **Qwen3.6**-35B-A3B `UD-Q4_K_XL` (unsloth, ~21 GB) under `D:\AI\hf_cache\hub\models--unsloth--Qwen3.6-35B-A3B-GGUF\...`; the kernel uses the `llama-server.exe` inside Ollama (`%LOCALAPPDATA%\Programs\Ollama\lib\ollama`) |
| API | An AI Router account; **no key is set up on this PC** (no `.env` key, nothing in the Credential Manager) |
| Assets | VRMs made by the user; voices generated on the ElevenLabs website (AI-generated) |
| VR headset | None |

### Measured on the user's PC (2026-11-14)

Node 26.13.0, npm 11.20.0, cargo/rustc 1.97.1, venv Python 3.13.5; Ollama 0.40.16. About 1.2 to 1.4 GB VRAM in use by the desktop; 18 to 19 GB RAM free before loading a model. `windows-sys` 0.59 was already in `Cargo.lock` (through Tauri), so K1-08b downloaded nothing.

**K1-01 spike: Qwen3.6-35B-A3B Q4 on llama.cpp** (`scripts/spike_llamacpp.py`, ctx 8192, flash attention, `--jinja`, thinking off, 256 generated tokens):

| `--n-cpu-moe` | threads | VRAM | RAM (working set / private) | prompt tok/s | gen tok/s |
|---|---|---|---|---|---|
| 40 (all experts on CPU) | 6 | 2.8 to 3.0 GB | 19.5 / 4.6 GB | 16 to 76 (2,210-token prompt) | 6.9 and 21.5 (two runs) |
| 40 | 10 | 3.0 GB | 19.5 / 4.6 GB | 54 | 22.9 |
| 40 | 10, `--threads-batch 6` | 3.0 GB | 19.5 / 4.6 GB | 58.5 | 23.6 |

Run-to-run variance is large (the file is memory-mapped), so treat these as ranges. **Chosen:** `n_cpu_moe 40, threads 10` (D-051). Through the real router: first turn 74 to 111 s to the first token cold; with the boot warm-up (D-052) the first message after it starts in 1.7 s; the second turn re-reads 23 tokens, first token 0.8 s, 24 to 26 tok/s. Loading the 35B from the picker took 109 s in K1-10's live run.

## 3. Verification status

| Claim | Status |
|---|---|
| Current tree on Windows: pytest 948, test:fe 121, tsc, vite build, cargo check, cargo test | **Verified** (user's PC, 2026-11-15) |
| Invariance: a turn differs between waifus only in the system prompt and the TTS parameters; router signatures carry no waifu | **Verified** (tests) |
| Real kernel + 35B: boot warm-up, first WebSocket message's first token 1.7 s, classifier on `qwen3.5:4b`, `/shutdown` frees ports | **Verified** (user's PC, 2026-11-14); boot no longer starts the 35B (D-060) |
| D-060 boot: kernel port answers 1.2 s after start with nothing loaded; after the window connects, `qwen3.5:9b` ready in 51 s (cold disk: 9B 36.7 s + 4B 12.3 s), then GPT-SoVITS up; no `llama-server`; `/shutdown` frees 8780 and 9880 and ends GPT-SoVITS | **Verified** (user's PC, 2026-11-15, browser pane + scratch data dir) |
| React chat window in a browser against the real kernel: streaming, Stop, threads, sidebar, Markdown, Regenerate, tray upload, model picker loads and switches, companion chip and dividers | **Verified** (built-in browser pane, 2026-11-14) |
| Anything inside the Tauri window (`npm run tauri dev`): the window itself, voice playback in WebView2, drag-drop, the native file dialog, the Key form | **Not verified** (Claude cannot see the window) |
| Credential Manager: write, read back, list, replace, delete, keys written by Windows' own tools, bad names refused without echo | **Verified** (`cargo test -- --ignored`, live vault, cleaned up) |
| The kernel's stdin key pipe: lines parsed, BOM tolerated, a normal exit with the reader running is clean (the old reader crashed with 0xC0000005) | **Verified** (tests and a live repro) |
| A live API model call (AI Router, OpenRouter or DeepSeek): streaming, billing from reported usage, `reasoning_effort` accepted | **Not verified** (no key on this PC) |
| llama.cpp with tool calls actually made by the model; thinking on | **Not verified** |
| Audible voice per waifu with the real clips on GPT-SoVITS; the premade packs loaded in the app | **Not verified** |
| Latency, fps, VRAM targets | Targets and spot measurements only |

## 4. Known issues and risks

- **Explorer crashes / lag at boot (D-060):** the cause was everything loading at once. The PC's page file is only 3.5 GB (commit limit 35.4 GB on 32 GB of RAM), so a 35B load plus the rest can come close to the limit. The user can set a system-managed page file (Windows setting; Claude does not change system settings). Not reproduced.
- **A blank window for several seconds on the first `tauri dev`** is Vite's first page transform (reproduced in a plain browser with no kernel); it renders after a few seconds.
- **No API key on this PC**, so nothing on the API side has run against a real provider. The first live check should be: `npm run tauri dev`, model menu → API → Key, save a key, pick an API model, send a message, then look at `data/spend.db` and `logs/audit.jsonl`.
- **Open questions waiting for the user:** D-058 (unpriced models such as DeepSeek's: block or flag while a cap is on; currently blocked), D-055 (relax the persona's "no markdown" rule), D-057 (move the websocket token check earlier), speaker tags. See `HANDOFF.md` §6.
- **The 35B needs about 2 minutes to load** (from boot, or after switching back to it). The "waking up" card shows it; the user asked to keep the model selector as documented and offer other models, which K1-10 did.
- **Custom API endpoints are config-only** until Settings (K1-13). A preset's URLs cannot be overridden: use your own id (D-059).
- **The 35B maps ~19.5 GB of RAM** while loaded; with other heavy apps open, generation can drop to ~7 tok/s.
- **Tests read the user's `config/config.yaml`** when it exists. The suite passes with the 35B default, but it is not isolated from local config.
- **Peer files sit untracked in the tree** (§1): `git add -A` would commit them, and the VRM/WAV files with them. Always stage explicit paths.
- **Yuri leftovers (proposed cleanup, awaiting approval, see TODO "Session 4 proposal"):** Cargo package/binary `yuri`, `orchestrator.log`, `[yuri]` log prefixes, `widget.html` + Yuri's engine in `src/*.ts`, the legacy flat protocol, the tray's API-model and click-through items, `KASANE/vrm/` and `KASANE/voice_files/` (gitignored copies of the premade assets), a 2,429-line `app.py`.
- **Inherited:** faster-whisper on CUDA failed on this machine (CPU STT); port 1420 is shared by `dev:ui` and `tauri dev`; killing instead of tray Quit loses that session's memory consolidation.
- Risks from the scope still apply (`SCOPE.md` §13).

## 5. Recent issues log

| Date | Area | Issue | Status |
|---|---|---|---|
| 2026-11-15 | keys | Review of K1-08b: changing only `preset:` in a copied config would send the new provider's key to the old URL | Fixed before commit (`5b04a30`): presets fix their URLs |
| 2026-11-15 | kernel | A daemon thread reading `sys.stdin.buffer` crashed any normal interpreter exit | Fixed (`5b04a30`): own unbuffered handle |
| 2026-11-15 | billing | Tool rounds, Stop and failed streams were not always billed; the cap ignored calls in flight | Fixed (`c54a938`, D-058) |
| 2026-11-14 | privacy | Ambient content (screen remarks, capture tools) could reach an API model; the websocket accepted any Origin | Fixed (`460aa1f`, D-057) |
| 2026-11-14 | build | `npm run check` red on Windows: a test built a Linux venv path with the host's `path.join` | Fixed (`baa0b54`) |

## 6. Manual gate: K0 (the user, on the PC)

Tick and date when done.

- [x] `npm run check` passes on the PC (including `cargo check`) — 2026-11-14
- [x] Premade Luna and Yuri packs built from the real files — 2026-11-14 (by a peer session; untracked)
- [ ] `npm run tauri dev` opens the Kokyū window
- [ ] Switching Luna ↔ Yuri changes persona and voice (existing GPT-SoVITS)
- [ ] With GPT-SoVITS stopped: the reply still appears, no robotic voice

| Gate | Date | Evidence | Signed by |
|---|---|---|---|
| K0 (automated) | 2026-11-12 | `npm run check -- --skip-cargo` green | Claude |
| K0 (manual, PC) | | | |

## 7. Update checklist (end of every session)

- [x] Snapshot header rewritten
- [x] "What exists" matches the repo
- [x] Verification table honest
- [x] Issues logged; gate sign-offs recorded
