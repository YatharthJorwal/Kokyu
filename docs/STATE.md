# STATE — Kōkyū

**Living document.** The truth *right now*. Rewrite it at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. Narrative lives in `HANDOFF.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-15 (night), session 4 close, after the review notes (D-072, D-073)
- **Current phase:** **K1 is code-complete; the K1 gate needs the user.** Done: K1-00 to K1-15 with K1-09b and K1-13b, the session 4 cleanup (C-1, C-2: Yuri is only a character, D-062). Left: C-1b (the user deletes `KASANE/vrm/`) and the **K1 gate** (§6). The K0 manual gate (window, voice) is still open. **Proposed, not approved:** modes (Chat, Roleplay, Live) in `docs/notes/modes-plan.md`.
- **Repo:** `github.com/YatharthJorwal/Kokyu`, `main`. Last code commit `89bdb95`. This docs commit is pushed with it; if `git log origin/main..HEAD` shows anything, the push did not happen.
- **License:** proprietary, all rights reserved (D-040). The repository should be private.
- **Seed:** Yuri `e32af4f710cdf4e8c141df667a18c53046557ea3`, copied verbatim in commit `0cd2d20`.
- **Last green run (the user's PC, 2026-11-15, after `89bdb95`):** `npm run check`: tsc, frontend tests 124, vite build, `cargo check`, pytest 1001.

## 1. What exists

| Area | State |
|---|---|
| Docs, README, proprietary LICENSE, `THIRD-PARTY.md` | Written |
| Kernel `KASANE/` (flat modules), split by job (D-062): `app.py` server only, `session.py` (one `Session` per window, `on_<type>` per message), `turns.py`, `ambient.py`, `companions.py`, `boot.py`, `hub.py`, `doctor.py`, `vram.py`; port 8780, `paths.py`, waifu packs and registry, per-waifu TTS, shared memory | Done and tested; live verified in the browser pane |
| No Yuri in the code (D-062) | Done and tested; **the tray was not looked at** |
| Protocol v1 only; the avatar code waits in `src/engine/` for K2 | Done and tested |
| Threads store, per-thread model and effort (per model, `threads.efforts`), D-025 egress rules | Done and tested; live local calls verified |
| Token counts per reply where the backend reports them (K1-04b) | Done and tested; stored, not shown |
| Lazy boot (D-060, D-061); default chat model on this PC `local:ollama/qwen3.5:9b` | Done; live verified |
| Voice mode switch in the tray (D-061) | Done; live verified (47 s to start GPT-SoVITS); **no audible playback checked** |
| llama.cpp backend, Qwen3.6-35B-A3B on demand (D-051, D-052) | Done; live verified |
| **Window layout to the reference (K1-15, D-068, D-069):** frameless window with its own minimize / maximize / close; top bar with the companion chip and a Temp Chat switch; sidebar with logo, pink New chat, search, history, Settings gear; one-row input box (paperclip tray, mic disabled until K2, round Send / Stop); a status line and the model chip under it; replies end right above the heart | Done; live verified in the browser pane at 1586×992, 1000×625, 900×600; **the frameless Tauri window not seen** |
| Model chip and popover: one line per row (name, size or price, fits, badges), vision / thinking / tools badges from Ollama's `capabilities`, effort slider, "Spent today" footer; a "waking up" card with Try again / Switch model (K1-07a, K1-10, K1-11) | Done; live verified |
| Effort data in `config/models.yaml` / `models.example.yaml` (D-064); thinking gets `llm.reasoning_tokens` of room; an empty reply is an error | Done and tested; live verified on `qwen3.5:9b` |
| VRAM manager v1 (K1-09, D-065): NVML from the driver, measured sizes in `data/vram_measured.json`, fits hints, a refusal before any unload that names what holds the memory | Done and tested; live verified (refusal card, fits / won't fit); the llama-server measurement on a real start not seen |
| *Unload X* on that card (K1-09b, D-071): offered for a named Ollama model the kernel does not reload at once (the memory writer), not the classifier or the embedding model; one click unloads it and tries the load again | Done and tested (planner, loader, WebSocket path); **not seen in a window** (the user's `tauri dev` held the kernel port) |
| Inline turn failures (K1-12, D-066): a card under the failed turn, plain words per kind (key refused, out of credit, rate limit, timeout, provider error), the provider's words under Details | Done and tested; live verified with Ollama unreachable; **no live API failure** (no key) |
| Settings (K1-13, D-067): Models, Screen, Memory (correct, forget, restore), Doctor (one row per component with a fix hint), About | Done and tested; live verified in the browser pane |
| Editable settings (K1-13b, D-070): `settings.json` in the app data folder wins over `config/config.yaml`, applied with no restart: the Ollama address (this PC only), a custom API endpoint, the budget caps, screen companions "On now" / "On at start" | Done and tested; live verified in the browser pane against a scratch kernel (refusals, saves, the API slot and spend line following, the file, a restart); "On at start" with a vision model and the key form's custom entry in the desktop window not seen |
| Sidebar history (grouped, search, rename, delete), Markdown replies, Copy, Regenerate, Retry, heart and thinking lines, screen companions, companion chip with dividers | Done; live verified (screen companion remarks not seen end to end) |
| AI Router and one API endpoint at a time; key in the Windows Credential Manager (D-058, D-059) | Done and tested with fakes; **no live API call** (no key on this PC) |
| App icon | Done; not looked at in the taskbar or tray |
| Premade packs `assets/premade/{luna,yuri}/` | Built by a peer session, **untracked**; the user decides about committing VRM/WAV (D-041) |
| TTS backend (Track T) | Not started; development uses the existing install (D-042) |

## 2. Environment

### Stated by the user

| Item | Value |
|---|---|
| GPU / CPU / RAM | RTX 3060 12 GB; i5-14400F; 32 GB DDR5-4800 |
| OS | Windows 11 (PowerShell); repo at `D:\AI\Kokyu.ai` |
| GPT-SoVITS install | `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (**a space in the path**) |
| Ollama models | `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L`, `qwen3.5:9b`, `qwen3.5:4b`, `nomic-embed-text` |
| llama.cpp | **Qwen3.6**-35B-A3B `UD-Q4_K_XL` (unsloth, ~21 GB) under `D:\AI\hf_cache\hub\models--unsloth--Qwen3.6-35B-A3B-GGUF\...`; the kernel uses the `llama-server.exe` inside Ollama |
| API | An AI Router account; **no key is set up on this PC** |
| Assets | VRMs made by the user; voices generated on the ElevenLabs website (AI-generated) |
| VR headset | None |

### Measured on the user's PC

Node 26.13.0, npm 11.20.0, cargo/rustc 1.97.1, venv Python 3.13.5; Ollama 0.40.16 (its `/api/tags` returns each model's `capabilities`).

**K1-01 spike: Qwen3.6-35B-A3B Q4 on llama.cpp** (ctx 8192, flash attention, thinking off): with `n_cpu_moe 40, threads 10` about 3.0 GB VRAM, 19.5 GB RAM mapped, 54 to 58 prompt tok/s, about 23 gen tok/s (D-051). Loading the 35B from the picker took 109 s.

**Session 4 (2026-11-15):**
- `import app` 750 ms before the lazy imports, 615 ms after (D-062).
- A cold `qwen3.5:9b` load took 104.6 s once while the `qwen3.5:4b` classifier and the 9B swapped each other out of VRAM.
- **GPU at rest with the chat model up** (NVML): 12,288 MB total, 394 MB free; `qwen3.5:9b` 5,590 MB, `qwen3.5:4b` 3,207 MB, `nomic-embed-text` 320 MB, other programs about 2.7 GB. Nothing else large fits beside them.
- GPT-SoVITS took 47 s to answer after voice mode was turned on.

## 3. Verification status

| Claim | Status |
|---|---|
| Current tree on Windows: `npm run check` green (tsc, frontend 124, vite build, cargo check, pytest 1001) | **Verified** (user's PC, after `89bdb95`) |
| One chat model in memory (D-072): a pick unloads every other Ollama model but embeddings (an API pick also stops llama-server); classifier, memory writer and vision run on the picked Ollama model; `keep_alive` 30m for it, 0 for others | Done and tested with fakes; **not run against the real Ollama** |
| Appearance (D-073): three themes, accent, bubbles, text size, kept in localStorage | **Verified** in the browser pane with the kernel offline; not seen in the Tauri window |
| Effort slider: no overshoot past the track | **Verified** (browser pane, measured) |
| Invariance: a turn differs between waifus only in the system prompt and the TTS parameters; memory and the Doctor never look at a waifu | **Verified** (tests) |
| Every protocol client message type has a `Session.on_<type>` handler | **Verified** (test) |
| Effort slider: per-model levels, remembered per model per thread, the chip glows while generating; High on `qwen3.5:9b` answers instead of thinking itself out of room | **Verified** (browser pane) |
| VRAM: fits / won't fit hints; a model too big is refused before anything unloads, naming the blockers | **Verified** (browser pane, real GPU) |
| A failed turn shows the card under the turn with Retry / Switch model | **Verified** (browser pane, Ollama URL pointed at a dead port) |
| Settings → Memory: correct (a new fact supersedes the old), forget, restore; Settings → Doctor rows on this PC | **Verified** (browser pane, scratch data dir) |
| K1-15 layout, popovers, tray, Temp Chat switch (saved by the kernel, shown in the sidebar), status line, replies right above the heart | **Verified** (browser pane) |
| Settings → Models: a LAN Ollama address and a plain-http endpoint refused with the reason beside Save; a localhost address, a custom endpoint (the API heading switched to it) and caps (the spend line followed) saved to `settings.json` and back after a kernel restart; Settings → Screen "On at start" saved | **Verified** (browser pane, scratch data dir) |
| A screen companion turned on at start through the vision check | **Verified** with fakes only (test); not run live, it would capture the screen |
| *Unload X*: offered only for a model the card names and the kernel will not reload at once; a ref not offered is refused; an offered one is unloaded and the load runs again | **Verified** with fakes (tests); the card and a real unload not seen |
| Anything inside the Tauri window (`npm run tauri dev`): the frameless window (drag, resize, the three buttons, close to tray), the tray menu, voice playback in WebView2, drag-drop, the native file dialog, the Key form | **Not verified** (Claude cannot see the window) |
| Credential Manager and the kernel's stdin key pipe | **Verified** (`cargo test -- --ignored`, live vault) |
| A live API model call; an API failure card from a real provider | **Not verified** (no key on this PC) |
| llama-server's measured VRAM on a real start (D-065) | **Not verified** |
| llama.cpp with tool calls made by the model; thinking on | **Not verified** |
| Audible voice per waifu; screen companion remarks live; the voice and screen chips in their new place under the input box | **Not verified** |
| Latency, fps, VRAM targets | Targets and spot measurements only |

## 4. Known issues and risks

- **Two files set the same keys (D-070):** what Settings saved in `settings.json` (app data folder; `data/` in a checkout) wins over `config/config.yaml`. If a config.yaml edit seems ignored, look there first: Settings shows which values come from it ("Use the default" / Remove drops them). Hand edits to config.yaml still need a restart; Settings changes do not.
- **Helper roles now run on the picked chat model** (D-072): `models.local.classifier` / `memory_writer` in the user's config (`qwen3.5:4b`) apply only while a llama.cpp or API model is picked, and then load per call (cold). Task Guide's classifier on the 9B is slower per call than the 4B was.
- **The frameless window is unseen.** If dragging or edge resizing misbehaves in WebView2, `"decorations": true` in `src-tauri/tauri.conf.json` brings the system frame back (the in-page buttons would then be duplicates; `TopBar.tsx` draws them only in the desktop app).
- **`KASANE/vrm/`** still holds duplicate VRMs (TODO C-1b; the user deletes it).
- **Luna answered a request for a bullet list in prose** (live, session 4): the persona's "no markdown" rule wins. That is D-055's open question.
- **The Doctor's GPU row counts an unmeasured llama-server as "other programs"** until it has been measured once.
- **The persona is flat everywhere** (short, no Markdown): the pack prompts carry TTS rules meant for voice. The fix is the modes plan (persona-only prompts plus mode layers), waiting for the user.
- **The mic button is drawn but disabled** until voice input (K2).
- **No API key on this PC**, so nothing on the API side has run against a real provider. First live check: `npm run tauri dev`, model chip → API → Key, save a key, pick an API model, send; then a wrong key for the failure card.
- **Open questions waiting for the user:** the classifier, D-058 (unpriced models; a custom endpoint's models are unpriced too), D-055 ("no markdown"), D-057 (websocket token check), premade packs in git. See `HANDOFF.md` §6.
- **Untracked in the tree:** `assets/premade/` (VRM/WAV), `.claude/`, and an unrelated `package-lock.json` change. Always stage explicit paths.
- **Tests read the user's `config/config.yaml`** when it exists; the suite passes, but it is not isolated from local config.
- **Inherited:** faster-whisper on CUDA failed on this machine (CPU STT); port 1420 is shared by `dev:ui` and `tauri dev`; killing the process instead of tray Quit loses that session's memory pass until the next start; the 35B needs about 2 minutes to load and maps ~19.5 GB of RAM.

## 5. Recent issues log

| Date | Area | Issue | Status |
|---|---|---|---|
| 2026-11-15 | Settings | The Settings form fields stretched 220 px tall (a flex basis in a column) | Fixed before commit (`0222d2e`) |
| 2026-11-15 | Settings | A hand-edited `settings.json` with a plain value for a section would have replaced that whole section with the defaults | Fixed before commit (`0222d2e`): such a value is dropped with a warning |
| 2026-11-15 | UI | Replies ended about 66 px above the heart (an invisible actions row); blank space left of the model chip | Fixed (`3d87f72`, D-069, the user's review) |
| 2026-11-15 | Doctor | The GPU row warned whenever Kōkyū's own models filled the card | Fixed before commit (`3e62a27`) |
| 2026-11-15 | VRAM | A load started without room and swapped models in and out (104.6 s) | Fixed (`d7180b8`): refused before any unload, blockers named |
| 2026-11-15 | models | On High, `qwen3.5:9b` spent the whole 512-token cap thinking and replied with nothing | Fixed (`f69b1f6`, D-064): `llm.reasoning_tokens`; an empty reply is an error |
| 2026-11-15 | UI | The chip lost its effort label after a reconnect | Fixed (`f69b1f6`) |
| 2026-11-15 | kernel | Tray Quit could exit while a closing window's memory pass still ran | Fixed (`8e4997b`) |
| 2026-11-15 | kernel | Screen companion remarks were lost with voice off | Fixed (`d512ac9`) |

## 6. Manual gates (the user, on the PC)

Tick and date when done.

**K0**
- [x] `npm run check` passes on the PC (including `cargo check`) — 2026-11-14
- [x] Premade Luna and Yuri packs built from the real files — 2026-11-14 (by a peer session; untracked)
- [ ] `npm run tauri dev` opens the Kōkyū window
- [ ] Switching Luna ↔ Yuri changes persona and voice (existing GPT-SoVITS, voice mode on)
- [ ] With GPT-SoVITS stopped: the reply still appears, no robotic voice

**K1** (TODO "Gate K1")
- [ ] The frameless window: drag by the top bar, resize from the edges, minimize / maximize / close (close hides to the tray)
- [ ] Chat with one local and one API model (needs a key)
- [ ] Change model, effort and companion mid-thread, each without changing the others
- [ ] A forced API error (for example a wrong key) shows the failure card with Retry / Switch model
- [ ] Layout signed off against `docs/reference-images/chat-ui.webp`
- [ ] Settings → Models: a custom endpoint saved, its key saved with Key in the model picker (it is listed there), one of its models answers with the budget off
- [ ] A model marked *won't fit* picked: the card names what holds the memory; *Unload X* shows where offered (for example after switching away from the 9B) and loads the model when it frees enough

| Gate | Date | Evidence | Signed by |
|---|---|---|---|
| K0 (automated) | 2026-11-12 | `npm run check -- --skip-cargo` green | Claude |
| K0 (manual, PC) | | | |
| K1 (automated) | 2026-11-15 | `npm run check` green after `89bdb95`; browser-pane checks in §3 | Claude |
| K1 (manual, PC) | | | |

## 7. Update checklist (end of every session)

- [x] Snapshot header rewritten
- [x] "What exists" matches the repo
- [x] Verification table honest
- [x] Issues logged; gate sign-offs recorded
