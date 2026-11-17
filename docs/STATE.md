# STATE — Kōkyū

**What is true right now.** Rewritten at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. The plan is `TODO.md`; the narrative is `HANDOFF.md`.

- **Last updated:** 2026-11-18, session 5 (K1c finished, the docs reset, UI1-01 model names, UI1-02 working controls, KASANE credit, 18+, UI1-03 unpriced models, UI1-06 her face and profile, UI1-07..10 message list, Markdown, shell, keyboard)
- **Phase:** K0, K1 and K1c are code-complete. The user ran and tested the K1c build on their PC (2026-11-17, "I've ran and tested on them my pc"); item-level results were not given, so the checkpoint below stays open. **UI-1 in progress:** UI1-01 model names (`883f4f7`), UI1-02 working controls and the disconnect banner (`a412120`, `c575b72`) UI1-03 unpriced models under the cap (`3e552e7`) and UI1-06 her face and profile (`04e0296`, `e62374f`, D-091) are done, and so are UI1-07 the message list (`0fac211`, D-092), UI1-08 Markdown (`12af2b8`, D-093), UI1-09 the shell (`cb24949`, D-094) and UI1-10 the keyboard (`77af8c0`, D-095), built in autonomous mode on Assumed answers, and the user's notes of 2026-11-18 (D-096: Tauri versions, the slider, thinking beside her face, typed replies, the loading strip). **UI-1 is code-complete; next is Checkpoint UI-1** (the user, in the desktop app). The design standard is its own phase, UI-2, planned from references before it is built (D-086).
- **Repo:** `github.com/YatharthJorwal/Kokyu`, `main`, private (D-040). Pushed through `599484c`. **Local only, waiting for the user's review:** `0fac211..` (UI1-07..10, the D-096 notes and their docs); the user said not to push yet.
- **Last green run (the user's PC, 2026-11-18, at `7203bb0`):** `npm run check`: tsc, frontend tests 166, vite build, cargo check, pytest 1263.
- **Seed:** Yuri `e32af4f`, copied verbatim in `0cd2d20` (D-002).

## 1. What exists

Levels (R-21): **T** = tests; **B** = seen in the browser pane (with a scratch kernel, or with injected state where noted); **D** = end to end in the desktop app with a real model. A level not listed was not reached.

| Feature | Level |
|---|---|
| Kernel split by job (D-062), port 8780, `paths.py`, companion packs and registry, shared memory with speakers | T, B |
| Waifu invariance (FR-W-3), one router door, egress rules (D-025), every message type has a handler | T |
| Threads (history, search, rename, delete, Temp Chat), Markdown replies, Copy, Regenerate, Stop | T, B |
| Message list: grouping, hover bar (time, model, Copy, Regenerate, Edit), thinking line in the reply slot, caret, jump-to-latest pill (D-092) | T, B (injected state, 900×600 and 1440×900, dark and light); edit-and-resend not run against a live model |
| Markdown tables, nested lists, coloured code with a header and Copy (D-093) | T, B (injected replies) |
| Shell: slim header, split New, thread menu, pins and the Pinned group, in-app confirm, toasts, empty state with starters (D-094) | T (pins in the store and over the socket), B (injected state); pin and delete not run against a live engine; window buttons not seen in the desktop app |
| Thinking beside her face (heart, animated word), replies typed out, the loading strip above the input box, the dragged effort slider (D-096) | T (word order, typing pace), B (injected state and pointer events; the hidden pane runs at 2-30 fps, so the pace was not judged by eye); not seen in the desktop app |
| Tauri crate and npm packages both 2.12 | `tauri info`, cargo check; `tauri dev` not started here |
| Shortcuts and the Ctrl+K palette; Esc stops a reply, but not while a dialog is open (D-095) | T, B (keys dispatched in the page); not tried in the desktop webview, where Ctrl+N could behave differently |
| Lazy boot (D-060), voice only when voice mode is on (D-061, 47 s to start GPT-SoVITS) | T, B; no audible playback checked |
| Model picker: Local and API sections, fits hints, capability badges, effort slider per model (D-064), "waking up" card | T, B (real Ollama and GPU) |
| Her face from the VRM thumbnail in the chip, the conversation list, her messages and the companion menu; her initial without one (D-091, FR-W-8) | T, B (real thumbnails from a scratch engine, injected roster); not seen in the desktop app |
| Her profile: About, traits, Chat (a new chat with her, no divider), Change picture, Use the model's face (D-091, FR-W-9) | T; picture change and reset live against a scratch engine; B with injected state; Chat not run against a live engine |
| Short model names; full id and details muted on hover or focus (D-084, FR-M-12) | T, B (injected rows named by the kernel's code); not seen in the desktop app with the real list |
| Only working controls; disconnect banner after 6 s offline with Reconnect, which restarts a stopped engine (D-082) | T (cargo check only for `restart_kernel`), B (banner and its states); Reconnect after a killed engine not run in the desktop app |
| One chat model in memory, helpers follow the pick (D-072) | T only (fakes) |
| VRAM check before a load, refusal naming the blockers (D-065), *Unload X* (D-071) | T, B (refusal card); *Unload X* T only |
| Failure card with Retry / Switch model (D-066) | T, B (Ollama pointed at a dead port); no live API failure |
| One API endpoint at a time, key in the Credential Manager (D-059) | T; Credential Manager live-tested; **no live API call** (no key) |
| Unpriced models run under a cap: "price unknown" in the picker, a one-time notice (D-083, FR-R-2) | T, B (injected rows and notice); no live call to an unpriced endpoint |
| Settings: Models, Screen, Memory (correct, forget, restore), Doctor, About, Appearance (D-067, D-070, D-073) | T, B |
| Window layout to the reference (D-068, D-069), frameless window with its own buttons | B; the frameless window in the desktop app not confirmed |
| Screen companions: Task Guide, OCR watch (D-048, D-056); quiet in roleplay | T; remarks not seen live |
| **Modes:** Chat and Roleplay per thread, layered prompts, no tools in roleplay, fiction kept out of memory (D-074) | T; the user ran the build on their PC |
| Story memory (`story.py`, folds logged as `story memory: folded …`) | T; no fold confirmed on real Ollama |
| Dialogue-only speech in roleplay (`DialogueFilter`) | T; not confirmed heard |
| Saved scenario cards, opening line as her first message | T, B (injected state) |
| New roleplay dialog, Roleplay badge, `*action*` and `(OOC …)` rendering | T, B (injected state) |
| Persona-only `persona.md` and a drafted About for Luna and Yuri | Written; packs load; untracked (open question 4); the About drafts await the user |
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

1. Design references for UI-2 (D-086): which apps and screens the look follows.
2. The voice a buyer hears: premades ship clips and transcripts (D-087); buyers without an NVIDIA GPU, and the ElevenLabs rights, are open.
3. Premade personas explicit or not (18+ is decided, D-090); payment provider, UK and SB 243 follow-ups (TODO B-10..12).
4. Premade packs in git: recommendation in `DECISIONS.md` (text tracked, VRM and WAV not).
5. An API key for testing the API path.
6. Closed: her face is the VRM thumbnail, changeable in her profile (D-091).
7. The six assumed K1c answers (D-074): confirm or reverse.
8. D-057: move the WebSocket token check earlier?
9. C-1b: the user deletes `KASANE/vrm/`.
10. D-092..D-095 (UI1-07..10) were Assumed in autonomous mode: confirm or reverse, including the four starter lines and pins stored by the engine.

## 4. Known issues and risks

- **The UI feels like a localhost shell** (the review of 2026-11-17): no design tokens, eleven font sizes down to 9 px, letter avatars, emoji glyphs. Names, dead controls and developer words are fixed (UI1-01, UI1-02); the look is phase UI-2 (D-086).
- **Premade personas carry explicit sexual instructions**, and every payment provider checked bans sexual products even for an 18+ app (D-090; the B-9 report): to resolve before release.
- **Reconnect cannot revive a hung engine:** `restart_kernel` starts one only when the process has exited; a running process that stopped answering needs tray Quit and a restart.
- **The unpriced-model notice is remembered in memory only:** it comes back once per model after each restart (a `shortcut:` comment in `router/__init__.py`).
- **The user's `config/config.yaml` still has `budget.on_exhausted`:** ignored now (unknown keys are skipped); delete the line when convenient.
- **Two files set the same keys (D-070):** `settings.json` wins over `config/config.yaml`.
- **Helper roles run on the picked chat model** (D-072): Task Guide's classifier on the 9B is slower per call than the 4B was.
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
| UI-1 automated | 2026-11-17 | `npm run check` green at `77af8c0` | Claude |
| UI-1 in the desktop app (the look, with a local model) | | | |
| K0 + K1 + K1c in the desktop app | | The user ran the K1c build on their PC (2026-11-17); the items above not yet ticked | |
