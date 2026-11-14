# CLAUDE.md — Kōkyū (Kokyu)

Instructions for any AI coding agent working in this repository. **Read this file fully at the start of every session**, then follow the session protocol below.

## 1. What this project is

Kōkyū is a Windows desktop chat app for a roster of AI companions ("waifus"). It looks like a normal chatbot UI (sidebar, one input box, one model switcher) and adds a VRM **stage view**, 2D **desktop pets**, a walkable **3D mode**, per-waifu **zero-shot voices** and an in-app **waifu creator**.

- **A waifu is a voice and a persona, nothing more.** Switching her never changes the model, intelligence, tools, permissions or memory scope.
- **KASANE** is the kernel (Python, in the `KASANE/` folder). Clients are Tauri 2 + TypeScript + three.js / `@pixiv/three-vrm` (`src/`, `src-tauri/`).
- Seeded from the author's earlier project **Yuri** (which succeeded **Luna**). Both live at `github.com/YatharthJorwal/Yuri` and `.../Luna`.
- One user per install, one Windows PC, local-first. Development machine: RTX 3060 12 GB, i5-14400F, 32 GB DDR5-4800.
- Commercial direction: a paid, one-time-purchase app where users bring their own models and keys (`docs/PRODUCT.md`). Ordinary users and a clean-machine install shape priorities.
- Windows packaging comes later (phase K7) but constrains design from day one (RULES §9).

Current status and plan: `docs/STATE.md`, `docs/TODO.md`.

## 2. Session protocol

### At the start (mandatory, in order)

1. Read `docs/HANDOFF.md` completely. It is the narrative from the last session.
2. Read `docs/STATE.md` (current state, known issues, what is verified).
3. Read `docs/TODO.md`, at least the current phase.
4. Skim `docs/RULES.md`. Read the `docs/SPEC.md` and `docs/ARCHITECTURE.md` sections relevant to the task. Search `docs/DECISIONS.md` before changing anything that looks settled. Read `docs/PRODUCT.md` when a task touches onboarding, packaging, licensing, assets or providers.
5. Run `git status`, `git log -5 --oneline` and the check command (§5). If reality disagrees with `STATE.md`, **tell the user before doing anything else**.

### During the session

- Work on **one TODO item at a time**, in order, inside the current phase. Do not start the next phase until its gate passed and the user approved.
- Before a large change, **state the plan and wait for approval**. The user reviews plans before code lands.
- Anything not in `docs/SPEC.md` needs a `docs/DECISIONS.md` entry and the user's approval first.
- Record every decision that is not obvious in `docs/DECISIONS.md` (append only).
- Never claim something works that you did not run. Label results **verified** or **not verified** (RULES §4).

### At the end (mandatory, even if the session was short)

1. `docs/TODO.md`: tick finished items and add the commit hash; add newly discovered tasks.
2. `docs/STATE.md`: rewrite the snapshot, the verification table and the issues list so it is true *now*.
3. `docs/HANDOFF.md`: rewrite thoroughly: what happened, exactly where you stopped, what to do first next time, traps you found, questions for the user. Assume the next reader remembers nothing.
4. `docs/DECISIONS.md`: append new entries; never edit old ones (supersede them with a new entry).
5. Commit the docs with a `docs:` message.

`HANDOFF.md` and `STATE.md` are **living documents**: they go stale within a session and are only trustworthy if updated at every session end.

## 3. Hard invariants

These are never traded away for convenience. Full list with rationale: `docs/RULES.md`.

1. **Waifu invariance.** No code path may branch on a waifu id except to pick her prompt, voice parameters, VRM and pet sprites. Model choice, effort, routing, tools, permissions and memory scope are independent of the waifu. Tests enforce this.
2. **One model entry point.** Every model call goes through `router.decide()` with a role. No direct provider calls from features.
3. **Local-only data.** Camera frames, mic audio, screen captures and memory-writer jobs never leave the machine.
4. **No silent fallback.** If the user's chosen API model fails, show the error with *Retry* and *Switch model*. Do not quietly change models.
5. **No secrets or assets in git.** Keys, `.vrm`, `.wav`, model weights, databases and logs are gitignored and must never be committed.
6. **No hard-coded paths.** Use `KASANE/paths.py` (dev: `./data`; packaged: `%APPDATA%\Kokyu`).
7. **Never block** the kernel's asyncio loop or the render loop.
8. **Honest verification.** No claim without running it.
9. **The code is proprietary** (D-040): keep the repo private; record provenance for anything copied in or out.

## 4. Repository map

```
CLAUDE.md             this file
README.md  LICENSE    public face (MIT)
KASANE/               Python kernel (flat modules, folder on sys.path: `import llm`, `from audio import tts`;
                      there is NO `kasane` package). app.py, bus.py, config.py, paths.py, router/, memory/, audio/ ...
src/                  frontend: Yuri's engine and widget UI (K0); React chrome + engine/ + net/ (K1+)
src-tauri/            Rust: windows, tray, hotkeys, child processes (Job Object)
config/               config.example.yaml, models.example.yaml, secrets.example.yaml
scripts/              dev.mjs, doctor.mjs, check.mjs, seed_waifus.py, packaging
tests-fe/             frontend tests (pure logic; Node test runner)
docs/                 SCOPE, SPEC, ARCHITECTURE, RULES, DECISIONS, TODO, STATE, HANDOFF, TTS-BACKEND, notes/
data/                 runtime data (gitignored)
```

The tree is real as of K0 (seeded from Yuri, renamed, reshaped). Yuri's layout and findings: `docs/notes/yuri-inventory.md`. Check `STATE.md` for what actually exists.

## 5. Commands

Taken from Yuri's `package.json` and handoff; **confirm each after the seed (K0-03/04)** and fix this list.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r KASANE\requirements-dev.txt
npm install

npm run tauri dev       # desktop shell; starts the kernel and the TTS backend itself (runs `npm run dev:ui` first)
npm run dev             # kernel + page for a plain browser tab (reuses a kernel already running)
npm run dev:ui          # page only (what tauri dev uses). Never run it together with `npm run dev` or `tauri dev`: port 1420
npm run doctor          # why a window does not load
npm run build           # tsc + vite build
npm run test:fe         # frontend pure-logic tests
npm run check           # tsc --noEmit + test:fe + build + cargo check + pytest (add `-- --skip-cargo` without a Rust toolchain; KOKYU_PYTHON overrides the interpreter)
.\.venv\Scripts\python.exe -m pytest KASANE -q
.\.venv\Scripts\python.exe KASANE\check.py --refresh   # config, key, catalog, spend
```

`npm run check` (which includes `pytest`) is the **definition of green**. Delivery is by git bundle (D-030).

## 6. Conventions (short)

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`), small and focused. Never force-push `main`.
- **Python:** 3.11+, type hints on public functions, `logging` not `print`, `pathlib` for paths, async-first.
- **TypeScript:** `strict`, no unexplained `any`. UI chrome in React; the three.js engine is an imperative module outside React state. Clients hold **no business logic**: they render kernel state.
- **Config:** every tunable is a config key with a default in `config/config.example.yaml`. Windows paths in YAML use **single quotes**.
- **Tests:** every kernel feature gets pytest coverage; tests that touch models use fakes. No GPU, network or key may be required for the suite.
- **Docs:** spec IDs (`FR-…`) are referenced from TODO items, tests and commits.

## 7. Things that bite on this machine

- Two dev servers share **port 1420**: run `npm run tauri dev` *or* `npm run dev`, never both.
- Yuri's kernel uses **8765** and its TTS backend **9880** (both hard-coded in Rust and Python). Kokyu's kernel uses **127.0.0.1:8780** (D-027); the TTS port comes from config and defaults to 9880.
- **Never bulk-edit source with naive string replacement** (it once replaced every "a" with "w" in five files). Rename with targeted edits and run the tests after each step.
- Tests stub `llm.<fn>` by module attribute and the router calls through the module; do not switch to `from llm import x`.
- `WinError 10048` on startup means a leftover `python.exe` holds the port: check Task Manager.
- Quit through the **tray Quit item**. Killing the process skips graceful shutdown, so that session's memory consolidation is lost.
- faster-whisper on CUDA failed on this machine with a missing `cublas64_12.dll`; **STT runs on CPU** by default (and that is also the right call for the VRAM budget).
- YAML with Windows paths: single quotes only (`'C:\Users\...'`).
- VRM, animation and voice files are user assets: gitignored, never committed.
- The GPT-SoVITS backend is **outside this repo**, set up by a separate agent from `docs/TTS-BACKEND.md`.

## 8. Definition of done (for any TODO item)

1. Code and tests written; `npm run check` and `pytest` green (or the failure is explained in `STATE.md`).
2. Matching SPEC requirement IDs satisfied, or the gap recorded.
3. Verified vs not-verified stated honestly in the commit body or `STATE.md`.
4. TODO ticked with commit hash; docs updated per the session protocol.

## 9. Where to look

| Question | Doc |
|---|---|
| What are we building and why? | `docs/SCOPE.md` |
| What is the product and what ships when? | `docs/PRODUCT.md` |
| What exactly must it do? | `docs/SPEC.md` |
| How is it put together? | `docs/ARCHITECTURE.md` |
| What must I never do? | `docs/RULES.md` |
| Why was X decided? | `docs/DECISIONS.md` |
| What is next? | `docs/TODO.md` |
| What is true right now? | `docs/STATE.md` |
| What happened last time? | `docs/HANDOFF.md` |
| How do I set up voice? | `docs/TTS-BACKEND.md` |
