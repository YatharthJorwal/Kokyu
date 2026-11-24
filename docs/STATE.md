# STATE — Kōkyū

**What is true right now.** Rewritten at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. The plan is `TODO.md`; the narrative is `HANDOFF.md`.

- **Last updated:** 2026-11-24, session 8, end (the second audit and UI-2's close, D-122..D-124; the AI note under the message box, D-119; the legal stance for launch, D-120; the self-harm detector, D-121; before that the user's UI notes, D-105..D-113: the pet's second round and sizes, the cat button, Pet settings, the Stage caption from Yuri with its glow, readable accent text, the voice's start and fail notes, round swatches, five theme presets, the Stage speaking by default with paced fading captions, the sidebar badge on a switch; then a whole-repo audit and its bug fixes, D-114). Session 7: UI1-15, UI1-16 (D-100, D-101).
- **Phase:** Checkpoint UI-1 ticked by the user on 2026-11-24 ("it seems working fine to me"); UI-2 in progress. K0, K1 and K1c are code-complete. The user ran and tested the K1c build on their PC (2026-11-17, "I've ran and tested on them my pc"); item-level results were not given, so the checkpoint below stays open. **UI-1 in progress:** UI1-01 model names (`883f4f7`), UI1-02 working controls and the disconnect banner (`a412120`, `c575b72`) UI1-03 unpriced models under the cap (`3e552e7`) and UI1-06 her face and profile (`04e0296`, `e62374f`, D-091) are done, and so are UI1-07 the message list (`0fac211`, D-092), UI1-08 Markdown (`12af2b8`, D-093), UI1-09 the shell (`cb24949`, D-094) and UI1-10 the keyboard (`77af8c0`, D-095), built in autonomous mode on Assumed answers, and the user's notes of 2026-11-18 (D-096: Tauri versions, the slider, thinking beside her face, typed replies, the loading strip). The user tested UI-1 on their PC on 2026-11-18 and everything listed passed (npm, the slider drag, the loading strip, edit/resend/regenerate, pin/rename/delete, shortcuts, window buttons, code and table formatting). **UI1-12** (D-097, session 6, autonomous, on a branch): voice mode replaced by Read aloud and dictation, `speakable`, tags shown, three polish notes. **UI1-13** (D-098, the user's task 10 relayed by a sibling session): Chat memory. **UI1-14** (D-099): a message read aloud on request. **UI1-15** (D-100) and **UI1-16** (D-101), session 7, the user's c.ai-style notes. **UI-1 is code-complete; next is Checkpoint UI-1** for the UI1-12..16 items (the user, in the desktop app). The design standard is its own phase, UI-2, planned from references before it is built (D-086).
- **Repo:** `github.com/YatharthJorwal/Kokyu`, private (D-040). Session 6's branch is merged; `main` holds everything through session 7 and is pushed to `origin/main` (`HANDOFF.md` names the last commit).
- **Last green run (the user's PC, 2026-11-24, at `d730ee5`):** `npm run check`: tsc, frontend tests 221, vite build, cargo check, pytest 1462 (again green at `35453c2`).
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
| Lazy boot (D-060); her voice only while Read aloud is on, kept in settings.json, the starting chip (D-097, 47 s to start GPT-SoVITS) | T, B (the menu item and three chip states, injected); no audible playback checked; not seen in the desktop app |
| Read aloud speaks each finished reply through `speakable` (code, tables, links, tags, dashes, quotes, lists; roleplay dialogue only), in the voice of who wrote it; a new line, Stop or another thread silences her (D-097) | T (fakes); no audio anywhere yet |
| Dictation: the mic button and F9 (changeable in Settings → Voice) record, faster-whisper on the CPU writes it down, the words go in at the caret, never sent (D-097) | T; B in headless Chromium with its fake mic and a fake socket (recording, F9, insertion, errors, the key change); the page's WebM/Opus decodes with faster-whisper's decoder; real speech, the WebView2 mic prompt and the desktop app not tried |
| Her `[emotion]` tags shown muted and italic like actions, in Chat and Roleplay (D-097) | T, B (the user's example reply, injected) |
| A speaker on her messages reads one aloud on request, Read aloud on or off, in the writer's voice (D-099); since D-100 it sits by her name | T (fakes), B (the button, its states, stop; injected); no audio |
| In a roleplay: her chip opens her profile and a switch is refused; the story tray (a book) with History, New chat and Memory, then Upload file and Read aloud (D-101) | T (fakes: the refused switch, Memory saved and in her note, refused in a chat, copied by a branch; the reducer); B (the tray, History, Memory with a pin, the chip; injected) |
| A message's ⋯ card (Copy, Edit, Rewind to here, roleplay Pin, New chat from here), Regenerate with swipes under her latest reply, the sidebar's hide button and All / Chats / Roleplays filter (D-100) | T (fakes: rewind, branch, swipes, pins in her note and their limit, the stored ids before turn_done; the reducer); B (both cards, the swipe row, the pin mark, the filter, hide and show, Bubbles; injected, no engine); not run against a real model or in the desktop app |
| Chat memory: a context-length slider per model under Effort (8K doubling to the model's maximum), kept in settings.json; every Ollama request, the history budget and llama.cpp's `-c` follow it; the fit point from Ollama's `model_info` or the GGUF header; past it a warning, never a block (D-098) | T (fakes: per-model `num_ctx`, the budget, the fit point, the GGUF header, `set_context` reloading); B (the slider and its warning, injected rows); no Ollama, GPU or real load here, so the fit point's accuracy is unchecked |
| The thinking word's single letter lift, "Waifu-mode-engaging" back, no slider end dots, a soft ⋯ hover (D-097) | T, B (screenshots, dark theme); smoothness not judged at full frame rate |
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
| Dialogue-only speech in roleplay (`DialogueFilter`, inside `speakable` since D-097) | T; not confirmed heard |
| Saved scenario cards, opening line as her first message | T, B (injected state) |
| New roleplay dialog, Roleplay badge, `*action*` and `(OOC …)` rendering | T, B (injected state) |
| Persona-only `persona.md` and a drafted About for Luna and Yuri | Written; packs load; untracked (open question 4); the About drafts await the user |
| App icon | Not looked at in the taskbar or tray |
| Session 8 UI notes: the pet on the window's bottom, carried and dropped, poses at their own size by head matching; the cat button's states; Pet settings' Switch character; Take her picture's note and Save as; upload limits; Ollama started with its model (D-105..D-110) | T; B (injected state, synthetic pointer events); real mouse drag, Save as and Ollama's start not seen in the desktop app |
| The Stage: Yuri's caption (words pop with her voice, the said word glows in Caption glow); Read aloud on while the Stage is open; without her voice the finished reply paced a sentence at a time, then faded (D-111, D-113) | T (word timing, sentences); B (the silent pacing, injected); never heard with her real voice |
| Themes: eight presets held to 7:1 text and 3:1 accent contrast by a test; round swatches; accent text readable on any theme; the voice's starting and failed notes with Set up (D-112, D-113) | T, B |
| The AI note under the message box in Chat, Roleplay and the Stage (D-119, FR-C-11) | D (all three modes, 2026-11-24) |
| The self-harm detector (D-121, FR-C-12): patterns and a meaning check on the user's line, a guard on her streaming reply, the help card, flagged lines kept from models, memory and the story summary | T (a labelled set: 29 lines flagged, 27 look-alikes not, 10 harmful replies stopped, 6 caring ones not; the turn wiring); D for a flagged line (the card, no reply, no model call, still there after a reload; scratch data). The meaning check calibrated on the real `nomic-embed-text` (SAFE-02, `35453c2`): held out, 8 of 14 indirect lines caught, 0 of 14 ordinary lines flagged; the reply guard not run with a real model |
| The fallback model (D-125): Ask me (*Answer with* on the card and the Stage's bar) or Answer by itself (a note, and the reply names both models); the cap message says which cap and what a reply may cost | T (kernel: offer, auto, regenerate with a model, no second fallback; window: the reducer); B (the card, the Stage bar, the reply's note in a page-only preview); not run against a real model |
| The picker's API list (D-126): popular sets, the checklist with search and Select all, Restore defaults, *Edit list* in the picker | T (listing, settings); B (the chooser and the picker's rows in a page-only preview); saving not run against the engine |
| What a user may reach (D-122): the VRM only for the window's Origin; she never recites her instructions; dev origins only in a checkout; llama-server with a key per run and no `/slots`; Vite's deny list | T; D (the Stage loads her model through the check; the address bar and a foreign Origin get 403; Vite on 1421 refuses data, config, packs and the kernel) |
| Inputs (D-123): the paste note, the counter, dictation's cap, refused sends with Retry, upload problems in their dialogs, IME Enter, Rename's Esc, long words, text direction | T (paste maths, dictation cap, the reducer, the plain refusal); D (the paste note, the counter at 18,500); the IME and Rename's Esc not tried live |
| The top bar in three columns (UI2-00m, D-124) | D (no overlap or overflow from the 900 px minimum up; the title ends in an ellipsis) |
| The audit's fixes (D-114): a turn survives memory errors; no dropped send after a mid-reply switch; regenerate saves first; driver-only delete; rewound replies never become memory; /shutdown and Host checks; stale-PID guard; settings.json kept when broken; one voice server; dictation on its own thread; safe pet save; the window keeps a started turn; asides; Markdown speed; offline note; links through the shell; Settings focus; Esc and dirty dialogs; input caps; switch labels; decay, the card, looks, clock times, smaller races | T for each (new tests named in the commits); B for Settings focus and the offline note; D for links, Settings focus, the dialogs' Esc and the offline note with Reconnect (2026-11-24) |

## 2. Environment

| Item | Value |
|---|---|
| GPU / CPU / RAM | RTX 3060 12 GB; i5-14400F; 32 GB DDR5-4800 |
| OS | Windows 11; repo at `D:\AI\Kokyu.ai` |
| Toolchain (measured) | Node 26.13.0, npm 11.20.0, cargo/rustc 1.97.1, venv Python 3.13.5, Ollama 0.40.16 |
| Ollama models | `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L`, `qwen3.5:9b` (default chat model, D-060), `qwen3.5:4b`, `nomic-embed-text` |
| llama.cpp | Qwen3.6-35B-A3B `UD-Q4_K_XL` (~21 GB) through the `llama-server.exe` inside Ollama; about 3.0 GB VRAM, 19.5 GB RAM, ~23 tok/s generation; 109 s to load (D-051) |
| GPT-SoVITS (dev) | `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (a space in the path); 47 s to answer after start; started only while Read aloud is on (D-097) |
| GPU at rest with the chat model up | 12,288 MB total, 394 MB free (9B 5,590 MB; 4B 3,207 MB; embeddings 320 MB; other programs ~2.7 GB), measured before D-072 |
| API | An AI Router account; **no key on this PC** |
| VR headset | None |

## 3. Open questions (the user will come back to them)

1. Design references for UI-2 (D-086): which apps and screens the look follows.
2. The voice a buyer hears: premades ship clips and transcripts (D-087); buyers without an NVIDIA GPU, and the ElevenLabs rights, are open.
3. Closed: premades are explicit (D-116); the payment provider stays deferred; the legal stance for launch is D-120 (TODO B-13; the lawyer question B-12).
4. Closed: the packs' text is in git, VRM and WAV out with checksums (D-118); a copy of the VRM and WAV is at `D:\AI\Kokyu-premade-backup`.
11. Closed: the user allowed Ollama for SAFE-02 (2026-11-24); Claude started `ollama serve` for the run and stopped it after.
5. Closed: the AI Router key is in `.env` (resolves; not in git, history or any other file). No live API call made yet.
6. Closed: her face is the VRM thumbnail, changeable in her profile (D-091).
7. The six assumed K1c answers (D-074): confirm or reverse.
8. D-057: move the WebSocket token check earlier?
9. C-1b: the user deletes `KASANE/vrm/`.
10. Assumed in autonomous mode, to confirm or reverse: D-092..D-095 (UI1-07..10, including the four starter lines and pins stored by the engine) and D-097's assumed parts: the dictation key works only while the window has focus and the page keeps it; Read aloud adds no spoken-delivery prompt layer (her replies are written as usual and cut by `speakable`); a reply finished while her voice starts waits for it; Settings has a Voice section.

## 4. Known issues and risks

- **Voice input code waits for K2** (`audio/voice.py`, `audio/vad.py`, `src/engine/mic-stream.ts`, the arbiter's barge-in states): tested, not wired, kept on purpose (AUD-03). AUD-04 lists the three small audit issues left as they are.
- **Links open through `rundll32 url.dll`** (`open_link`): seen working in the desktop app; a refused link does nothing and says nothing.
- **A send arriving while a finished turn still applies a companion switch now waits for it** (`Session.settled`): the window's other messages queue behind that short wait.
- **The UI feels like a localhost shell** (the review of 2026-11-17): no design tokens, eleven font sizes down to 9 px, letter avatars, emoji glyphs. Names, dead controls and developer words are fixed (UI1-01, UI1-02); the look is phase UI-2 (D-086).
- **Premade personas carry explicit sexual instructions** (kept, D-116), and every payment provider checked bans sexual products even for an 18+ app (D-090; the B-9 report): the provider is chosen before release.
- **The detector's meaning check catches about half of indirect lines** (0.80 / 0.10, chosen for no false alarms: a false alarm takes a reply away). Direct phrasings are the patterns' job. `nomic-embed-text` separates the two kinds weakly; a dedicated small classifier model would do better, not planned. English only (SAFE-03). A Regenerate whose new reply is stopped shows nothing: the old reply stays and no card appears.
- **Any program on this PC can connect to the engine** if it sends no Origin (D-057, SEC-01): read threads and memory, chat on the user's API key, or post `/shutdown`. Other websites cannot (Origin, Host and CSP checks).
- **The premades' files sit in the folder they are loaded from** (`assets/premade/<id>/`): the app hands none of them out (D-122), but a user can copy them from disk until K7-10 packs them.
- **The app starts Ollama and loads the chat model at launch** (D-105); the kernel stops it on quit.
- **Reconnect cannot revive a hung engine:** `restart_kernel` starts one only when the process has exited; a running process that stopped answering needs tray Quit and a restart.
- **The unpriced-model notice is remembered in memory only:** it comes back once per model after each restart (a `shortcut:` comment in `router/__init__.py`).
- **The user's `config/config.yaml` still has `budget.on_exhausted`:** ignored now (unknown keys are skipped); delete the line when convenient.
- **Two files set the same keys (D-070):** `settings.json` wins over `config/config.yaml`.
- **Helper roles run on the picked chat model** (D-072): Task Guide's classifier on the 9B is slower per call than the 4B was.
- **The kernel port 8780 is hard-coded in several places** (`app.py`, `kernel.ts`, `lib.rs`, the CSP, dev scripts; `ARCHITECTURE.md` §12); a packaging risk (K7-08).
- **Tests read the user's `config/config.yaml`** when it exists; the suite passes, but it is not isolated from local config.
- **K1c follow-ups** (D-075, TODO backlog), none blocking.
- **PyAV 19 breaks faster-whisper 1.2.1** (it dropped an argument faster-whisper passes): a fresh install would read no recording. `requirements.txt` now caps `av<19` (16.1..18.1 checked); the user's venv may need `pip install -r KASANE/requirements.txt` again. PyAV bundles FFmpeg (LGPL): review before release.
- **`test_vram`'s Windows-path test fails on Linux** (a `PosixPath('C:\\Windows')` is not absolute): passes on the user's PC; backlog.
- **Chat memory's "fits" badge and fit point use different estimates:** the badge the flat `vram.kv_mb_per_1k_ctx`, the fit point the model's real KV shape at f16 (an `OLLAMA_KV_CACHE_TYPE` is not read); both lean high. Backlog (D-098 follow-ups).
- **The WebView2 microphone permission** for dictation is unverified: if Windows or WebView2 blocks it, the box's line says so; nothing else breaks.
- Inherited: faster-whisper on CUDA failed here (CPU STT); killing the process instead of tray Quit loses that session's memory pass.

## 5. Checkpoint (the user ticks; date each item)

This one list replaces the three stacked manual gates (K0, K1, K1c) (D-076). In the desktop app (`npm run tauri dev`) with `qwen3.5:9b`:

- [ ] The window opens; drag by the top bar, resize from the edges, minimize / maximize / close (close hides to the tray)
- [ ] A chat: a plain short answer; a list when asked; a screenshot tool call works
- [ ] A roleplay from a saved card and one blank: the opening line shows first; `*actions*` in italic; she never decides your character's actions
- [ ] Read aloud on (the `＋` menu): the chip counts while her voice starts (about 47 s); Luna and Yuri sound different; each reply is spoken once it has finished; code, tables, links and tags are never spoken; in a roleplay only dialogue is spoken; a new line or Stop silences her; it is still on after a restart; with GPT-SoVITS stopped the reply still appears
- [ ] Dictation: the mic button and F9 record (Windows may ask for the microphone the first time); the words land in the box at the caret and are not sent; Settings → Voice changes the key and the tooltip follows
- [ ] Her message's speaker (beside her name): reads that message with Read aloud off too (her voice starts first, about 47 s), in Luna's or Yuri's own voice; clicked again it stops
- [ ] A message's ⋯ (D-100): the card on both sides; Rewind to here asks, then the later messages are gone and she answers from there; New chat from here opens a copy (a roleplay keeps its card); in a roleplay, Pin shows a pin and she remembers it many turns later; Regenerate twice, then ‹ › back to the first reply and send: she follows the one shown
- [ ] A roleplay (D-101): her chip opens her profile (no switching); the book tray: History lists your roleplays with her and opens one, New chat starts the story again, Memory saves a note she then follows, and lists pins with Unpin; Settings → Voice's switch says Off and On
- [ ] The sidebar's hide button and the top bar's button to bring it back (still hidden after a restart); All / Chats / Roleplays
- [ ] Chat memory on the 9B: drag it in the picker, watch the loading strip as it reloads, see the warning appear past the mark, and check whether a reply still works at a large value
- [x] The audit (D-114), 2026-11-24: checked in the desktop app on 2026-11-24, driven by Claude through WebView2's debugging port: a link opens the browser and `file:`, `javascript:` and spaced URLs are refused; Ctrl+, moves focus into Settings, typing stays out of the message box, Esc returns focus; a half-filled New roleplay card survives Esc; Esc in Take her picture closes only the viewer; with the engine stopped a send says it is not connected and keeps the text, Reconnect brings it back in about 2 s and the note goes
- [ ] The self-harm card (D-121): a line such as "I don't want to live anymore" gets the card and no reply, in a chat and a roleplay; "this traffic is killing me" gets a normal reply
- [ ] The Stage (D-111, D-113): Read aloud turns on by itself; her words pop in with her voice and fade after each line; with Read aloud off the reply appears a sentence at a time and fades
- [ ] The UI1-12 polish: her `[tags]` muted and italic; the thinking word's slow lift; no dark dots at the slider's ends; the ⋯ hover in the conversation list
- [ ] Change model, effort and companion mid-thread, each without changing the others
- [ ] A forced failure (Ollama stopped, or later a wrong API key) shows the failure card with Retry / Switch model
- [ ] After about a dozen roleplay lines the kernel log shows `story memory: folded …`, and Settings → Memory shows nothing from the story

| Checkpoint | Date | Evidence | Signed by |
|---|---|---|---|
| K0 automated | 2026-11-12 | `npm run check -- --skip-cargo` green | Claude |
| K1 automated | 2026-11-15 | `npm run check` green after `89bdb95` | Claude |
| K1c automated | 2026-11-17 | `npm run check` green after `97de53a` | Claude |
| UI-1 automated | 2026-11-17 | `npm run check` green at `77af8c0` | Claude |
| UI1-12 automated | 2026-11-18 | `npm run check -- --skip-cargo` at `6a254cf` (Linux): green but for the Windows-only `test_vram` test; cargo not run | Claude |
| UI1-16 automated | 2026-11-18 | `npm run check` green at `9597652` | Claude |
| UI1-13 automated | 2026-11-18 | the same at `f9648b0` | Claude |
| UI-1 in the desktop app (the look, with a local model) | | | |
| K0 + K1 + K1c in the desktop app | | The user ran the K1c build on their PC (2026-11-17); the items above not yet ticked | |
