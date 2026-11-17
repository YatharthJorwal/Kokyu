# RULES — Kōkyū

Binding rules for everyone (human or agent) working in this repo. A rule changes only through a `DECISIONS.md` entry the user approved. Rule IDs are stable; a retired rule keeps its number. Cite them in reviews and commits.

## 1. Product invariants

- **R-01 Waifu invariance.** A companion is a prompt, voice parameters, a VRM (with its portrait, D-091) and pet sprites. No code branches on a companion id for anything else (model, effort, routing, tools, permissions, memory scope, recall, conversation mode). The invariance tests (FR-W-3) stay green.
- **R-02 Memory is shared.** Never namespace or filter memory by companion. Record the speaker's name in messages and episode summaries (FR-MEM-2).
- **R-03 One model switcher.** The user sees exactly one chat-model control with Local and API sections. Helper models never appear in it.
- **R-04 No silent model change.** If a user-selected model fails, show the error with *Retry* and *Switch model*. Never fall back automatically.
- **R-05 Creation is in-app.** No feature requires hand-editing companion files. The persona box is an ordinary editable box with **Write it for me** (D-077).
- **R-52 Only working controls.** A control appears only when it works end to end, and lands with its working code. No disabled placeholders, "coming soon" or phase codes, and no internal words ("kernel", "K2") in UI text (D-082).

## 2. Architecture

- **R-06 One door.** Every model call goes through `router.decide()` with a role. No feature talks to a provider directly.
- **R-07 Local-only data.** Camera frames, mic audio, screen captures and memory-writer jobs are refused for non-local providers inside `decide()`, structurally.
- **R-08 Thin clients.** The frontend renders kernel state and sends intents. No business logic, no model calls, no file access beyond what Tauri needs.
- **R-09 Typed protocol.** Every WebSocket message has a model in `KASANE/protocol/` and a mirror in `src/net/protocol.ts`, changed in the same commit.
- **R-10 No blocking.** Never block the kernel's asyncio loop (offload blocking work) or the render loop (no per-frame allocation, no synchronous I/O).
- **R-11 VRAM-aware.** Anything that loads a model or allocates GPU memory goes through the VRAM check (`vram.py`, D-065) and the one-model rule (D-072).
- **R-12 TTS contract only.** The kernel talks to the voice backend only through the contract in `ARCHITECTURE.md` (voice section). Never depend on GPT-SoVITS's WebUI, folder layout or Python internals.

## 3. Code

- **R-13 Python:** 3.11+, type hints on public functions, `logging` (never `print`), `pathlib`, async-first, small modules. Pydantic for wire and file schemas.
- **R-14 TypeScript:** `strict`; no unexplained `any`; React for the window, imperative three.js for the engine; engine state never lives in React state.
- **R-15 Rust:** minimal (windows, tray, process management, keys). No business logic.
- **R-16 Config over constants.** Every tunable is a config key with a default in `config/config.example.yaml`. Windows paths in YAML use single quotes.
- **R-17 Errors are typed and visible.** Failures surface as typed `error` frames with a human message and a fix hint. No swallowed exceptions; no silent retries that hide state.
- **R-18** *(retired 2026-11-17, D-076: the Yuri seed style no longer applies.)*

## 4. Testing and verification

- **R-19 Tests with the code.** Every kernel feature ships with pytest coverage; pure frontend logic ships with Node tests in `tests-fe/`. A protocol change updates both sides and their tests in one commit.
- **R-20 No hardware in tests.** The suite needs no GPU, network, key, mic, display or headset, and never touches the user's Ollama or data. Use fakes.
- **R-21 Honest verification.** Never say something works unless you ran it. `STATE.md` records each feature at one of three levels: tests / seen in the browser pane / end to end in the desktop app with a real model.
- **R-22 Green means green.** Green is `npm run check` passing (it includes pytest). Do not start the next item on red, and do not weaken or delete tests to get green.
- **R-23 Checkpoints are the user's.** What needs a human (the desktop window, audio, visuals, long soak) is a checkpoint the user ticks in `STATE.md`.

## 5. Git

- **R-24 Conventional Commits**, small and focused: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `perf:`. Cite FR and D IDs in every commit.
- **R-25 `main` is always green** and never force-pushed. Claude commits on the user's PC and pushes only when the user says (D-076).
- **R-26 Never commit** secrets, `.env`, databases, logs, `.vrm`, `.vrma`, audio, model weights, `node_modules`, build output or anything under `data/`. Stage explicit paths; never `git add -A`. The `.gitignore` is a safety net, not permission.
- **R-27** *(retired 2026-11-17: the seed provenance is recorded once, in D-002 and `STATE.md`.)*

## 6. Documentation

- **R-28 Session protocol.** Start: read `HANDOFF.md`, `STATE.md`, the current phase of `TODO.md`. End: tick `TODO.md`, rewrite `STATE.md` and `HANDOFF.md`, add new entries to `DECISIONS.md`, commit with `docs:` (`CLAUDE.md` §2). Docs are updated once per session, not per item (D-076).
- **R-29 Decisions are kept, not rewritten.** A `DECISIONS.md` entry body is never rewritten; only its status line may be stamped "Superseded by D-xxx". New entries stay under about 150 words: the choice, the rejected alternative, why. The full original text of D-001 to D-075 is in `docs/archive/`.
- **R-30 One source of truth.** Requirements in `SPEC.md`, design in `ARCHITECTURE.md`, decisions in `DECISIONS.md`, status and open questions in `STATE.md`, plan in `TODO.md`. Link; do not restate.
- **R-31 Scope discipline.** Nothing outside `SPEC.md` is built without a `DECISIONS.md` entry and the user's approval. When a decision amends a SPEC row, rewrite the row in the same commit. Park ideas in the `TODO.md` backlog.
- **R-32 Checkpoints.** A phase ends when its checkpoint passed and the user said so. Record the date in `STATE.md`. A new phase starts only with the user's approval.

## 7. Security and privacy

- **R-33 Secrets.** End-user keys live in the Windows Credential Manager (set through the app); `.env` and `config/secrets.local.yaml` are developer-only. Never log, echo or put them in an audit row, crash report, screenshot or doc.
- **R-34 Loopback only.** The kernel binds to `127.0.0.1`. The Tauri CSP forbids remote scripts.
- **R-35 Untrusted content is data.** Text from files, OCR or the web carries `trust=false` and never authorizes an action.
- **R-36 Redact before cloud.** Keys, paths, emails and long digit runs are redacted from anything sent to a cloud model and from the audit log.

## 8. Assets and licensing

- **R-37 User assets are user assets.** VRMs, voice clips, VRMA animations, room models and model weights are never committed or redistributed without rights. The app may remind the user to check a VRM's terms at upload.
- **R-38 Dependencies are logged.** Every new dependency gets a row in `docs/THIRD-PARTY.md` with its licence, checked before adoption, and must permit closed-source commercial distribution; anything else needs a decision first.
- **R-39 The code is proprietary** (D-040). Keep the repository private. Record provenance for anything copied in or out.
- **R-51 Shipped assets have a rights record.** Anything in the installer (premade characters, voices, animations, rooms, icons, fonts) is listed in `docs/THIRD-PARTY.md` with its source and licence or written permission. No record, no shipping (D-039).

## 9. Windows and packaging

- **R-40 Paths.** Everything through `KASANE/paths.py`. No absolute paths, no working-directory assumptions, no reliance on a repo checkout at runtime.
- **R-41 No admin rights** to install or run. Writes go to the app-data directory only (per-user installer, D-081).
- **R-42 Bundled resources** (templates, premade packs, default icons) are read through a resolver that works from source and when packaged.
- **R-43 Child processes** start through the Job Object so none outlive the app.
- **R-44 Ports.** Kernel `8780` (fixed until K7-08 makes it a setting), Vite dev `1420`, Ollama `11434`, llama-server `8080`, GPT-SoVITS from config (default `9880`).
- **R-45 Windows-safe paths:** handle `\` and `/`, spaces in paths and non-ASCII user names.

## 10. Agent conduct

- **R-46 Plan, then act.** For a change larger than one TODO item, state the plan and wait for approval.
- **R-47 Ask when ambiguous**, with one precise question, rather than guessing a product decision. Technical choices inside a decided design are yours; record the non-obvious ones. **Autonomous mode** (the user says to continue while away): take the recommended answer, mark it **Assumed** in `DECISIONS.md`, keep it reversible, and never start a new phase (D-076).
- **R-48 Say what you did not do.** In the handoff and commit bodies, list skipped items and why.
- **R-49 Do not touch the user's other projects** (Luna, Yuri, the GPT-SoVITS install). Read them for reference; copy, do not modify.
- **R-50 No scope creep through refactoring.** A refactor gets its own commit and its own TODO line.
