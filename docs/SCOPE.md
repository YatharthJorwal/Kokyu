# Kōkyū: Scope

> **Kōkyū** (後宮; ASCII *Kokyu* for paths and identifiers) is the app. **KASANE** is the kernel inside it (Python, `KASANE/`).
> Scope v1.0, 2026-11-17 (docs reset, D-076). One page. Requirements: `SPEC.md`. Design: `ARCHITECTURE.md`. Direction and business: `PRODUCT.md`. Decisions: `DECISIONS.md`.

## 1. What Kōkyū is

A Windows desktop app for roleplay and conversation with AI characters ("companions"; the code says "waifu"). It is a roleplay character app first (D-079). It looks like an ordinary chatbot: a history sidebar, one input box, one model picker. Around that sit a VRM stage, per-companion voices, an in-app companion creator and, later, desktop pets and a 3D apartment.

- **Bring your own model and key.** Local models through Ollama or llama.cpp, or one OpenAI-compatible API endpoint (presets: AI Router, OpenRouter, DeepSeek; or a custom one). We sell no model access (D-033, D-037).
- **Local-first.** One user, one Windows PC. Threads, memory and settings stay on the machine.
- **Lineage:** seeded from the author's Yuri (which succeeded Luna); Luna and Yuri are now the two premade companions (D-041).

## 2. Invariants

Tested in code; full list and rationale in `RULES.md`.

1. **A companion is a voice and a persona, nothing more** (D-003, D-038). Switching her never changes the model, effort, tools, permissions, mode or memory scope. Those belong to the app and the thread.
2. **One model entry point.** Every model call goes through `router.decide()` with a role.
3. **Local-only captures.** Camera frames, mic audio, screen captures and memory-writer jobs never leave the machine (D-025).
4. **No silent fallback.** If the picked model fails, the turn shows why, with *Retry* and *Switch model* (D-020, D-066).

## 3. Differentiators

- One model picker and one companion switcher that stay independent.
- Roleplay as a first-class mode: per-thread mode, scenario cards and story memory that never leaks fiction into real memory (D-074).
- Shared long-term memory the user can see and correct (D-005).
- Each companion has her own zero-shot voice (planned, K2; D-006).
- Embodiment: a VRM stage first (1.0), then desktop pets and a 3D apartment (1.1).
- No terminal: the first run sets up voice by itself (planned, W; D-080).

## 4. What exists today

K0, K1 and K1c are code-complete. `docs/STATE.md` holds what is verified and how.

- **Chat window:** frameless window, history sidebar (grouped, search, rename, delete), companion chip with switch dividers, Temp Chat, Markdown replies, Copy, Regenerate, Retry, inline failure cards (D-066, D-068).
- **Modes (K1c):** Chat and Roleplay, fixed per thread; layered system prompt; saved scenario cards with an opening line; dialogue-only speech in Roleplay; story memory folded by the local memory writer (D-074, D-075).
- **Model picker:** Local and API sections, fits / won't-fit hints from the VRAM manager, capability badges, an effort slider where the model supports one, a "waking up" card; picking a model unloads the rest (D-054, D-064, D-065, D-072).
- **Settings:** Models (Ollama address, API endpoint and key in the Windows Credential Manager, spending caps), Screen, Memory (correct, forget, restore), Appearance (themes), Doctor, About; `settings.json` applied live (D-059, D-067, D-070, D-073).
- **Voice (development only):** Read aloud speaks each finished reply with GPT-SoVITS, started only while it is on; dictation (mic button or F9) writes into the input box with faster-whisper on the CPU (D-097). No stage, no live voice yet.
- **Screen companions:** Task Guide and OCR watch (D-048). Off by default; they need a local vision model, so they are a GPU-only extra, not a 1.0 headline.

## 5. Release train

Order per D-085, amended by D-086 (provisional). Each phase ends with one checkpoint in the desktop app with a real model, ticked by the user (D-076).

**Release 1.0**

| Phase | Delivers |
|---|---|
| **UI-1** Chat app polish | Model names: a short name shown, the full id and details muted on hover (D-084, done); only working controls and a disconnect banner (D-082, done); unpriced models (D-083, done); companion portrait, message list, Markdown and keyboard behaviour |
| **UI-2** Design standard | Planned from real references before it is built: `DESIGN.md`, tokens, primitives and icons, applied to every surface (D-086) |
| **K1b** Installer skeleton | A thin per-user NSIS installer with the kernel sidecar, tested on a clean machine (time-boxed) |
| **K2** Stage and voice | The Ani-style VRM stage with lip-sync and idle life; per-companion voice (the voice a 1.0 buyer gets is still open: D-036, `PRODUCT.md` §9); speech input with barge-in; the mic button appears only when it works (D-082) |
| **K3** Creator | Name and traits in; **Write it for me** runs the persona instruction through the picked model; the box stays editable; VRM and voice-clip upload with checks (D-077) |
| **W** First run | Model or key, then companion; voice set up automatically with progress: GPT-SoVITS and the speech-to-text model, through small setup modules with pinned manifests; Ollama via its official installer; Doctor fix actions for the rest (D-080) |
| **K6** Hardening | Evals, performance budgets, crash recovery, a soak test |
| **K7** Release | The NSIS `.exe` from a tagged build (D-081), updater, diagnostics export; signing and licence keys wait on D-043 |

**Release 1.1**

- **K4 Desktop pets:** 2D sprites baked from the VRM, one overlay window per monitor, click-through except over her pixels (D-010, D-014).
- **K5 3D apartment** (D-078), built from what Luna already proved: a prebuilt GLB apartment supplied as a user asset, BVH collision, a spectator camera and a first-person visitor camera (WASD, pointer lock), her wandering with walk clips, time-of-day lighting.
  - Open, to design later: real room and anchor data; the rights to a shipped room asset; VRAM beside the LLM and TTS; two-companion scenes (who speaks next, and both reacting to what the user says).

## 6. Not planned / cut

- **Agent mode** (file read and write): not planned. Kōkyū is a roleplay character app (D-079).
- **VR:** deferred long term; there is no headset to build or test with (D-079).
- **The paste-only creator box** with typing disabled: replaced by Write it for me and an editable box (D-077).
- **A portable zip and `setup.ps1`:** one installer only (D-081).
- **Disabled placeholder controls**, "coming soon" and phase codes in UI text: a control ships with its working code (D-082).
- **A separate agent for the voice backend** (Track T): the app sets voice up itself (D-080).
- Also out: mobile, web-hosted, multi-user or cloud sync; a per-companion model (D-038); fine-tuned voice weights; Live2D; a marketplace.

## 7. Where to look

| Question | Doc |
|---|---|
| Product direction, open business questions | `PRODUCT.md` |
| Exact requirements; the persona-writing instruction (Appendix A) | `SPEC.md` |
| How it is built today | `ARCHITECTURE.md` |
| Rules that never bend | `RULES.md` |
| Why something was decided; open questions | `DECISIONS.md` |
| What is next | `TODO.md` |
| What is true now | `STATE.md` |
| Last session | `HANDOFF.md` |
| Old material (frozen) | `docs/archive/` |
