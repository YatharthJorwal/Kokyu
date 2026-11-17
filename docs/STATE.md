# STATE — Kōkyū

**What is true right now.** Rewritten at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. The plan is `TODO.md`; the narrative is `HANDOFF.md`.

- **Last updated:** 2026-11-17, session 5 (K1c finished, then the docs reset, D-076)
- **Phase:** K0, K1 and K1c are code-complete. The user ran and tested the K1c build on their PC (2026-11-17, "I've ran and tested on them my pc"); item-level results were not given, so the checkpoint below stays open. **Next: UI-1, chat app polish, model names first** (D-084, D-085 provisional).
- **Repo:** `github.com/YatharthJorwal/Kokyu`, `main`, private (D-040). Pushed through `7c16e95`; the docs reset commit follows.
- **Last green run (the user's PC, 2026-11-17, after `97de53a`):** `npm run check`: tsc, frontend tests 140, vite build, cargo check, pytest 1209. pytest 1209 and test:fe 140 again after `2b99262`.
- **Seed:** Yuri `e32af4f`, copied verbatim in `0cd2d20` (D-002).

## 1. What exists

Levels (R-21): **T** = tests; **B** = seen in the browser pane (with a scratch kernel, or with injected state where noted); **D** = end to end in the desktop app with a real model. A level not listed was not reached.

| Feature | Level |
|---|---|
| Kernel split by job (D-062), port 8780, `paths.py`, companion packs and registry, shared memory with speakers | T, B |
| Waifu invariance (FR-W-3), one router door, egress rules (D-025), every message type has a handler | T |
| Threads (history, search, rename, delete, Temp Chat), Markdown replies, Copy, Regenerate, Stop | T, B |
| Lazy boot (D-060), voice only when voice mode is on (D-061, 47 s to start GPT-SoVITS) | T, B; no audible playback checked |
| Model picker: Local and API sections, fits hints, capability badges, effort slider per model (D-064), "waking up" card | T, B (real Ollama and GPU) |
| One chat model in memory, helpers follow the pick (D-072) | T only (fakes) |
| VRAM check before a load, refusal naming the blockers (D-065), *Unload X* (D-071) | T, B (refusal card); *Unload X* T only |
| Failure card with Retry / Switch model (D-066) | T, B (Ollama pointed at a dead port); no live API failure |
| One API endpoint at a time, key in the Credential Manager (D-059) | T; Credential Manager live-tested; **no live API call** (no key) |
| Settings: Models, Screen, Memory (correct, forget, restore), Doctor, About, Appearance (D-067, D-070, D-073) | T, B |
| Window layout to the reference (D-068, D-069), frameless window with its own buttons | B; the frameless window in the desktop app not confirmed |
| Screen companions: Task Guide, OCR watch (D-048, D-056); quiet in roleplay | T; remarks not seen live |
| **Modes:** Chat and Roleplay per thread, layered prompts, no tools in roleplay, fiction kept out of memory (D-074) | T; the user ran the build on their PC |
| Story memory (`story.py`, folds logged as `story memory: folded …`) | T; no fold confirmed on real Ollama |
| Dialogue-only speech in roleplay (`DialogueFilter`) | T; not confirmed heard |
| Saved scenario cards, opening line as her first message | T, B (injected state) |
| New roleplay dialog, Roleplay badge, `*action*` and `(OOC …)` rendering | T, B (injected state) |
| Persona-only `persona.md` for Luna and Yuri | Written; packs load; untracked (open question 4) |
| App icon | Not looked at in the taskbar or tray |

## 2. Environment

| Item | Value |
|---|---|
| GPU / CPU / RAM | RTX 3060 12 GB; i5-14400F; 32 GB DDR5-4800 |
| OS | Windows 11; repo at `D:\AI\Kokyu.ai` |
| Toolchain (measured) | Node 26.13.0, npm 11.20.0, cargo/rustc 1.97.1, venv Python 3.13.5, Ollama 0.40.16 |
| Ollama models | `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L`, `qwen3.5:9b` (default chat model, D-060), `qwen3.5:4b`, `nomic-embed-text` |
| llama.cpp | Qwen3.6-35B-A3B `UD-Q4_K_XL` (~21 GB) through the `llama-server.exe` inside Ollama; about 3.0 GB VRAM, 19.5 GB RAM, ~23 tok/s generation; 109 s to load (D-051) |
| GPT-SoVITS (dev) | `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (a space in the path); 47 s to answer after start |
| GPU at rest with the chat model up | 12,288 MB total, 394 MB free (9B 5,590 MB; 4B 3,207 MB; embeddings 320 MB; other programs ~2.7 GB), measured before D-072 |
| API | An AI Router account; **no key on this PC** |
| VR headset | None |

## 3. Open questions (the user will come back to them)

1. A written design standard for the UI (`docs/DESIGN.md`, at the start of UI-1).
2. The 1.0 voice for buyers: the premades' voices exist only as GPT-SoVITS clips (ties to D-080).
3. Content stance and payment fit: the premade personas carry explicit sexual instructions; does the payment provider accept a companion and roleplay app? An age gate?
4. Premade packs in git: the VRM, WAV and `persona.md` drafts are untracked; decide what is versioned.
5. An API key for testing the API path.
6. A face for the companion (a portrait from the VRM thumbnail).
7. The six assumed K1c answers (D-074): confirm or reverse.
8. D-057: move the WebSocket token check earlier?
9. C-1b: the user deletes `KASANE/vrm/`.

## 4. Known issues and risks

- **The UI feels like a localhost shell** (the review of 2026-11-17): no design tokens, eleven font sizes down to 9 px, letter avatars, raw model ids, emoji glyphs, developer words in the UI. That is phase UI-1.
- **Raw model ids everywhere** (`hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L` in the chip). Fixed by UI1-01 (D-084).
- **Disabled placeholders** (the mic, "arrives in K2/K3" tooltips) break D-082. Fixed by UI1-02.
- **Unpriced models are refused while a cap is on** until UI1-03 lands (D-083 allows them).
- **Two files set the same keys (D-070):** `settings.json` wins over `config/config.yaml`.
- **Helper roles run on the picked chat model** (D-072): Task Guide's classifier on the 9B is slower per call than the 4B was.
- **`build_premade.py --force`** rewrites the packs' `waifu.yaml`, dropping the `prompt: persona.md` pointer.
- **The kernel port 8780 is hard-coded in several places** (`app.py`, `kernel.ts`, `lib.rs`, the CSP, dev scripts; `ARCHITECTURE.md` §12); a packaging risk (K7-08).
- **Tests read the user's `config/config.yaml`** when it exists; the suite passes, but it is not isolated from local config.
- **K1c follow-ups** (D-075, TODO backlog), none blocking.
- Inherited: faster-whisper on CUDA failed here (CPU STT); killing the process instead of tray Quit loses that session's memory pass.

## 5. Checkpoint (the user ticks; date each item)

This one list replaces the three stacked manual gates (K0, K1, K1c) (D-076). In the desktop app (`npm run tauri dev`) with `qwen3.5:9b`:

- [ ] The window opens; drag by the top bar, resize from the edges, minimize / maximize / close (close hides to the tray)
- [ ] A chat: a plain short answer; a list when asked; a screenshot tool call works
- [ ] A roleplay from a saved card and one blank: the opening line shows first; `*actions*` in italic; she never decides your character's actions
- [ ] Voice mode on: Luna and Yuri sound different; in a roleplay only dialogue is spoken; the emotion tag is never spoken; with GPT-SoVITS stopped the reply still appears
- [ ] Change model, effort and companion mid-thread, each without changing the others
- [ ] A forced failure (Ollama stopped, or later a wrong API key) shows the failure card with Retry / Switch model
- [ ] After about a dozen roleplay lines the kernel log shows `story memory: folded …`, and Settings → Memory shows nothing from the story

| Checkpoint | Date | Evidence | Signed by |
|---|---|---|---|
| K0 automated | 2026-11-12 | `npm run check -- --skip-cargo` green | Claude |
| K1 automated | 2026-11-15 | `npm run check` green after `89bdb95` | Claude |
| K1c automated | 2026-11-17 | `npm run check` green after `97de53a` | Claude |
| K0 + K1 + K1c in the desktop app | | The user ran the K1c build on their PC (2026-11-17); the items above not yet ticked | |
