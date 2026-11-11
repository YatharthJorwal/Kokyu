# RULES — Kōkyū

Binding rules for everyone (human or agent) working in this repo. A rule can change only through a `DECISIONS.md` entry approved by the user. Rule IDs are stable; cite them in reviews and commits.

## 1. Product invariants

- **R-01 Waifu invariance.** A waifu is a prompt, TTS parameters, a VRM and pet sprites. No code may branch on a waifu id for anything else (model, effort, routing, tools, permissions, memory scope, recall). The invariance test (FR-W-3) must stay green.
- **R-02 Memory is shared.** Never namespace or filter memory by waifu. Always record the speaker's name in messages and episode summaries (FR-MEM-2).
- **R-03 One model switcher.** The user sees exactly one chat-model control with Local and API sections. Helper models never appear in it.
- **R-04 No silent model change.** If a user-selected API model fails, show the error with *Retry* and *Switch model*. Never fall back automatically.
- **R-05 Creation is in-app.** No feature may require hand-editing waifu files. The system prompt box is paste-only (FR-CR-5).

## 2. Architecture

- **R-06 One door.** All model calls go through `router.decide()` with a role. No feature talks to a provider directly.
- **R-07 Local-only data.** Camera frames, mic audio, screen captures and memory-writer jobs are refused for non-local providers inside `decide()`, structurally.
- **R-08 Thin clients.** The frontend renders kernel state and sends intents. No business logic, no model calls, no file access beyond what Tauri APIs are needed for.
- **R-09 Typed protocol.** Every WebSocket message has a model in `kasane/protocol/` and a mirror in `src/net/`. Change both in the same commit and bump the version when the wire format breaks.
- **R-10 No blocking.** Never block the kernel's asyncio loop (offload blocking work to threads or processes) or the render loop (no per-frame allocation, no synchronous I/O).
- **R-11 VRAM-aware.** Anything that loads a model or allocates GPU memory goes through the VRAM manager. Do not add a resident GPU component without updating the budget in `ARCHITECTURE.md` §13.
- **R-12 TTS contract only.** The kernel talks to the TTS backend only through the contract in `TTS-BACKEND.md`. Never depend on the GPT-SoVITS WebUI, its folder layout or its Python internals.

## 3. Code

- **R-13 Python:** 3.11+, type hints on public functions, `logging` (never `print`), `pathlib`, async-first, small modules. Pydantic for wire and file schemas.
- **R-14 TypeScript:** `strict`; no unexplained `any`; React for chrome, imperative three.js for the engine; engine state never lives in React state.
- **R-15 Rust:** keep it minimal (windows, tray, hotkeys, process management, hit-testing). No business logic.
- **R-16 Config over constants.** Every tunable is a config key with a default in `config/config.example.yaml`. Windows paths in YAML use single quotes.
- **R-17 Errors are typed and visible.** Failures surface as typed `error` events with a human message and a fix hint. No swallowed exceptions; no silent retries that hide state.
- **R-18 Match existing style** where code was seeded from Yuri unless a `DECISIONS.md` entry says otherwise.

## 4. Testing and verification

- **R-19 Tests with the code.** Every kernel feature ships with pytest coverage; every protocol message has a contract fixture shared with frontend tests.
- **R-20 No hardware in tests.** The automated suite needs no GPU, network, key, mic, display or headset. Use fakes.
- **R-21 Honest verification.** Never state that something works unless you ran it. In `STATE.md` keep a **verified / not verified** table. If you could not run it (no GPU, no display), say so plainly and add a manual gate to `TODO.md`.
- **R-22 Green means green.** Definition of green: `npm run check` and `pytest` pass. Do not start the next TODO item on red, and do not weaken or delete tests to get green.
- **R-23 Manual gates stay manual.** Gates that need a human (audio, visuals, VR, long soak) are checklists the user signs off in `STATE.md`.

## 5. Git

- **R-24 Conventional Commits**, small and focused: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `perf:`. Reference SPEC IDs or TODO IDs in the body.
- **R-25 `main` is always green** and never force-pushed. Larger work goes on short-lived branches merged when green.
- **R-26 Never commit** secrets, `.env`, databases, logs, `.vrm`, `.vrma`, audio, model weights, `node_modules`, build output, or anything under `data/`. The `.gitignore` is a safety net, not permission.
- **R-27 Seed commit records provenance.** The Yuri commit hash used to seed Kokyu is recorded in `DECISIONS.md` (D-002) and `STATE.md`.

## 6. Documentation discipline

- **R-28 Session protocol.** Start by reading `HANDOFF.md`, `STATE.md`, `TODO.md`. End by updating `TODO.md`, `STATE.md`, `HANDOFF.md`, and appending to `DECISIONS.md` (see `CLAUDE.md` §2).
- **R-29 `DECISIONS.md` is append-only.** Supersede, never edit. Each entry states context, decision, consequences and who decided (user or assistant default).
- **R-30 One source of truth.** Requirements live in `SPEC.md`, design in `ARCHITECTURE.md`, status in `STATE.md`, plan in `TODO.md`. Do not restate them elsewhere; link.
- **R-31 Scope discipline.** Nothing outside `SPEC.md` is built without a `DECISIONS.md` entry and the user's approval. Park ideas in `TODO.md` → Backlog.
- **R-32 Gates.** A phase ends only when its gate passed and the user said so. Record the date and evidence in `STATE.md`.

## 7. Security and privacy

- **R-33 Secrets** only in `.env` or `config/secrets.local.yaml`. Never log, echo, print or put them in an audit row, crash report, screenshot or doc.
- **R-34 Loopback only.** The kernel binds to `127.0.0.1`. Tauri CSP forbids remote scripts.
- **R-35 Untrusted content is data.** Text from files, OCR or the web carries `trust=false` and never authorises an action.
- **R-36 Redact before cloud.** Keys, paths, emails and long digit runs are redacted from anything sent to a cloud model and from the audit log.

## 8. Assets and licensing

- **R-37 User assets are user assets.** VRM models, voice clips, VRMA animations and model weights are never committed or redistributed. Respect their licenses; the app may remind the user to check a VRM's usage terms at upload.
- **R-38 Dependencies are logged.** Every new dependency gets a row in `docs/THIRD-PARTY.md` (created in K0) with its license, checked before adoption. Copyleft or unclear licenses need a `DECISIONS.md` entry.
- **R-39 Project license is MIT** (D-015). Do not add code with an incompatible license.

## 9. Windows and packaging readiness

- **R-40 Paths.** Everything through `kasane/paths.py`. No absolute paths, no `os.getcwd()` assumptions, no reliance on a repo checkout at runtime.
- **R-41 No admin rights** required to run. Writes go to the app-data directory only.
- **R-42 Bundled resources** (built-in scenes, the instruction template, default icons) are read through a resource resolver that works both from source and when packaged.
- **R-43 Child processes** are started through the Job Object mechanism so none outlive the app.
- **R-44 Ports** are configurable; defaults: kernel `8780`, Vite dev `1420`, Ollama `11434`, llama.cpp `8080`, TTS backend configurable (default of the installed GPT-SoVITS API).
- **R-45 Line endings and paths** are Windows-safe: handle `\` and `/`, spaces in paths and non-ASCII user names.

## 10. Agent conduct

- **R-46 Plan, then act.** For any change larger than one TODO item, state the plan and wait for approval.
- **R-47 Ask when ambiguous**, with one precise question, rather than guessing a product decision. Technical choices inside a decided design are yours to make; record non-obvious ones.
- **R-48 Say what you did not do.** In handoff and commit bodies, list skipped items and why.
- **R-49 Do not touch the user's other projects** (Luna, Yuri, the GPT-SoVITS install). Read them for reference; copy, do not modify.
- **R-50 No scope creep through refactoring.** Refactors need their own commit and their own TODO line.
