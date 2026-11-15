# STATE — Kōkyū

**Living document.** The truth *right now*. Rewrite it at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. Narrative lives in `HANDOFF.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-15 (about 14:05), session 4
- **Current phase:** **K1 in progress.** Done: K1-00 to K1-08b except K1-04b and K1-07b; the session 4 cleanup (C-1, C-2: Yuri is only a character, D-062); K1-15a (heart and thinking lines, D-063). Left: C-1b (user), K1-04b, K1-07b with K1-11, K1-09, K1-12, K1-13, K1-15, K1-14, then the K1 gate. The K0 manual gate (window, voice) is still open (§6).
- **Repo:** `github.com/YatharthJorwal/Kokyu`, `main`. Last code commits `d5da9f8` (kernel split, D-062) and `8e4997b` (Quit waits for the memory pass). **Not pushed:** `main` is 10 commits ahead of `origin/main` with this docs commit (`9a667ba` onwards); auto mode refuses `git push`, so the user pushes.
- **License:** proprietary, all rights reserved (D-040). The repository should be private.
- **Seed:** Yuri `e32af4f710cdf4e8c141df667a18c53046557ea3`, copied verbatim in commit `0cd2d20`.
- **Last green run (the user's PC, 2026-11-15, after `d5da9f8`):** `npm run check`: tsc, frontend tests 115 (includes the peer's untracked effort-slider tests), vite build, `cargo check`, pytest 944. After `8e4997b`: pytest 945.

## 1. What exists

| Area | State |
|---|---|
| Docs, README, proprietary LICENSE, `THIRD-PARTY.md` | Written |
| Kernel `KASANE/` (flat modules), split by job (D-062): `app.py` server only, `session.py` (one `Session` per window, `on_<type>` per message), `turns.py`, `ambient.py`, `companions.py`, `boot.py`, `hub.py`; port 8780, `paths.py`, waifu packs and registry, `prompting.py`, per-waifu TTS, speaker-tagged memory | Done and tested; live verified in the browser pane |
| No Yuri in the code (D-062): module loggers, `logs/kernel.log`, crate `kokyu`, neutral fallback persona, tool guidance in the shared addendum; tray click-through, "Use API model" and the F9 hotkey removed | Done and tested; **the tray was not looked at** |
| Protocol v1 only (D-062): the window and kernel exchange typed frames; Yuri's widget (`widget.html`, `src/main.ts`, …) deleted; the avatar code waits in `src/engine/` for K2 | Done and tested; live verified in the browser pane |
| Threads store, conversation manager, per-thread model and effort, D-025 egress rules (K1-00 to K1-00c) | Done and tested; live local calls verified |
| Normal 1200×800 app window, explicit CSP (K1-00d) | Done; **the window was not looked at** |
| Lazy boot (D-060, D-061): port first; after the first window connects, the chat model, then the memory pass; llama.cpp only when picked or messaged; default chat model on this PC `local:ollama/qwen3.5:9b` | Done; live verified in the browser pane |
| Voice mode switch in the `＋` tray (D-061): starts GPT-SoVITS, then faster-whisper; stops the voice server `tts.idle_stop_s` after it goes off | Done; live verified (47 s to start GPT-SoVITS); **no audible playback checked** |
| App icon (`src-tauri/app-icon.png`, `icons/`, favicon) | Done; not looked at in the taskbar or tray |
| llama.cpp backend, Qwen3.6-35B-A3B on demand (K1-01, K1-01b; D-051, D-052) | Done; live verified |
| React chat window (K1-02, D-053) | Done; verified live in a browser |
| Model chip and popover; one background loader with a "waking up" card, Try again / Switch model (K1-10, K1-07a; D-054) | Done; verified live in the browser pane |
| Sidebar: companions, history grouped by day, search, inline rename, delete (K1-03) | Done; verified live in the browser pane |
| Markdown replies, Copy, kernel-side Regenerate and Retry (K1-04, D-055) | Done; verified live in the browser pane |
| `＋` tray (Upload file, Voice, screen companions; the rest disabled until K2), paste/drop attach (K1-05) | Done; verified live in the browser pane |
| Heart above the input that traces while thinking, beside rotating "<name> is …" lines; one beat when the reply starts; threads fill from the bottom (K1-15a, D-063) | Done; verified live in the browser pane |
| Screen companions (K1-05b, D-056); their remarks are stored in the thread, flagged ambient, never sent to a model (D-062) | Done and tested; a real nudge or OCR remark not seen end to end |
| Companion chip and "Switched to …" dividers (K1-06) | Done; verified live (Luna ↔ Yuri) |
| AI Router provider and one API endpoint at a time; key in the Windows Credential Manager (K1-08, K1-08b; D-058, D-059) | Done and tested with fakes; **no live API call** (no key on this PC) |
| Premade packs `assets/premade/{luna,yuri}/` (VRM, prompt, voice, `waifu.yaml`) | Built by a peer session, **untracked**. The user decides whether VRM/WAV files get committed (D-041) |
| Peer work waiting for its TODO item (untracked, do not commit early): `KASANE/vram.py` + `tests/test_vram.py` (K1-09); `src/app/effort-slider.ts`, `ui/EffortSlider.tsx`, `ui/effort-slider.css`, `tests-fe/effort-slider.test.mjs` (K1-11) | Written, not integrated |
| Design references `docs/reference-images/` (chat UI, stage view, app icon) | Used for K1-15 |
| VRAM manager, effort slider, inline API failure UX, Settings/Doctor/Memory viewer, UI to the reference | Not started (K1-09, K1-11, K1-12, K1-13, K1-15) |
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
| API | An AI Router account; **no key is set up on this PC** |
| Assets | VRMs made by the user; voices generated on the ElevenLabs website (AI-generated) |
| VR headset | None |

### Measured on the user's PC

Node 26.13.0, npm 11.20.0, cargo/rustc 1.97.1, venv Python 3.13.5; Ollama 0.40.16. About 1.2 to 1.4 GB VRAM in use by the desktop; 18 to 19 GB RAM free before loading a model.

**K1-01 spike: Qwen3.6-35B-A3B Q4 on llama.cpp** (`scripts/spike_llamacpp.py`, ctx 8192, flash attention, `--jinja`, thinking off, 256 generated tokens):

| `--n-cpu-moe` | threads | VRAM | RAM (working set / private) | prompt tok/s | gen tok/s |
|---|---|---|---|---|---|
| 40 (all experts on CPU) | 6 | 2.8 to 3.0 GB | 19.5 / 4.6 GB | 16 to 76 (2,210-token prompt) | 6.9 and 21.5 (two runs) |
| 40 | 10 | 3.0 GB | 19.5 / 4.6 GB | 54 | 22.9 |
| 40 | 10, `--threads-batch 6` | 3.0 GB | 19.5 / 4.6 GB | 58.5 | 23.6 |

Run-to-run variance is large (the file is memory-mapped). **Chosen:** `n_cpu_moe 40, threads 10` (D-051). Loading the 35B from the picker took 109 s in K1-10's live run.

**Session 4 (2026-11-15):**
- `import app` (the kernel's import cost before the port opens): about 750 ms before the lazy imports, 615 ms after (D-062). FastAPI is about 260 ms of it.
- A cold `qwen3.5:9b` load took **104.6 s** once, while the `qwen3.5:4b` classifier and the 9B swapped each other out of VRAM; about 6.6 GB of VRAM was in use before the load. Another cold start measured 51 s (9B 36.7 s + 4B 12.3 s). Input for K1-09.
- GPT-SoVITS took 47 s to answer after voice mode was turned on.

## 3. Verification status

| Claim | Status |
|---|---|
| Current tree on Windows: `npm run check` green (tsc, frontend 115, vite build, cargo check, pytest 944), then pytest 945 | **Verified** (user's PC, 2026-11-15) |
| Invariance: a turn differs between waifus only in the system prompt and the TTS parameters; router signatures carry no waifu | **Verified** (tests) |
| Every protocol client message type has a `Session.on_<type>` handler | **Verified** (test) |
| Tray Quit waits for a closing window's memory pass before it stops the children and exits | **Verified** by a test only (a real tray Quit not tried) |
| After the split, in the browser pane against `qwen3.5:9b`: thread reopened, a reply streamed with the thinking row, switch to Yuri and back with dividers, no errors in the kernel log | **Verified** (2026-11-15) |
| v1-only window: send, streamed reply, switch with divider, Stop keeps the partial reply | **Verified** (browser pane, 2026-11-15) |
| Heart row and rotating lines while thinking, quiet heart after; short thread sits on the input | **Verified** (browser pane, 2026-11-15) |
| D-060/D-061 boot: port answers at once with nothing loaded; chat model after the window connects; no voice server and no faster-whisper at launch; voice mode starts and stops GPT-SoVITS | **Verified** (browser pane, scratch data dir) |
| Anything inside the Tauri window (`npm run tauri dev`): the window, the tray menu, voice playback in WebView2, drag-drop, the native file dialog, the Key form | **Not verified** (Claude cannot see the window) |
| Credential Manager and the kernel's stdin key pipe | **Verified** (`cargo test -- --ignored`, live vault; tests and a live repro) |
| A live API model call | **Not verified** (no key on this PC) |
| llama.cpp with tool calls actually made by the model; thinking on | **Not verified** |
| Audible voice per waifu with the real clips; screen companion remarks live | **Not verified** |
| Latency, fps, VRAM targets | Targets and spot measurements only |

## 4. Known issues and risks

- **`KASANE/vrm/`** still holds `luna.vrm` and `yuri.vrm`: byte-identical copies of the pack VRMs (SHA-256 checked), gitignored, read by nothing. Claude's delete was refused by auto mode; the user can delete the folder (TODO C-1b).
- **Two Ollama models fight for VRAM:** the 4B classifier and the 9B chat model swapped each other out during one cold load (104.6 s). K1-09 should decide what stays resident.
- **Explorer crashes / lag at boot (D-060):** caused by everything loading at once, fixed by the lazy boot. The page file is only 3.5 GB; a system-managed page file is the user's call (Claude does not change system settings). Not reproduced.
- **A blank window for several seconds on the first `tauri dev`** is Vite's first page transform; it renders after a few seconds.
- **No API key on this PC**, so nothing on the API side has run against a real provider. First live check: `npm run tauri dev`, model menu → API → Key, save a key, pick an API model, send a message, then look at `data/spend.db` and `logs/audit.jsonl`.
- **Open questions waiting for the user:** D-058 (unpriced models), D-055 ("no markdown" rule), D-057 (websocket token check), premade packs in git. See `HANDOFF.md` §6.
- **The 35B needs about 2 minutes to load**; the "waking up" card shows it.
- **Custom API endpoints are config-only** until Settings (K1-13).
- **The 35B maps ~19.5 GB of RAM** while loaded.
- **Tests read the user's `config/config.yaml`** when it exists; the suite passes, but it is not isolated from local config.
- **Peer files sit untracked in the tree** (§1): `git add -A` would commit them, and the VRM/WAV files with them. Always stage explicit paths.
- **Inherited:** faster-whisper on CUDA failed on this machine (CPU STT); port 1420 is shared by `dev:ui` and `tauri dev`; killing the process instead of tray Quit loses that session's memory pass until the next start's catch-up pass.
- Risks from the scope still apply (`SCOPE.md` §13).

## 5. Recent issues log

| Date | Area | Issue | Status |
|---|---|---|---|
| 2026-11-15 | kernel | Tray Quit could exit while a closing window's memory pass still ran | Fixed (`8e4997b`, SPEC §4.2) |
| 2026-11-15 | kernel | An image the vision model could not see left the window on "thinking" | Fixed (`d512ac9`) |
| 2026-11-15 | kernel | Screen companion remarks were lost with voice off | Fixed (`d512ac9`): stored in the thread, never sent to a model |
| 2026-11-15 | shell | The global F9 hotkey (nothing listened) took F9 from every other app | Removed (`038ad7e`) |
| 2026-11-15 | prompts | Tool instructions lived only in Yuri's prompt, so Luna never learned the tools | Fixed (`038ad7e`): shared addendum |
| 2026-11-15 | keys | Changing only `preset:` in a copied config would send the new provider's key to the old URL | Fixed before commit (`5b04a30`) |
| 2026-11-15 | billing | Tool rounds, Stop and failed streams were not always billed | Fixed (`c54a938`, D-058) |

## 6. Manual gate: K0 (the user, on the PC)

Tick and date when done.

- [x] `npm run check` passes on the PC (including `cargo check`) — 2026-11-14
- [x] Premade Luna and Yuri packs built from the real files — 2026-11-14 (by a peer session; untracked)
- [ ] `npm run tauri dev` opens the Kokyū window
- [ ] Switching Luna ↔ Yuri changes persona and voice (existing GPT-SoVITS, voice mode on)
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
