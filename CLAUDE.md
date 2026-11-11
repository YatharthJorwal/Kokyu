# CLAUDE.md — Kōkyū (Kokyu)

Instructions for any AI coding agent working in this repository. **Read this file fully at the start of every session**, then follow the session protocol below.

## 1. What this project is

Kōkyū is a Windows desktop chat app for a roster of AI companions ("waifus"). It looks like a normal chatbot UI (sidebar, one input box, one model switcher) and adds a VRM **stage view**, 2D **desktop pets**, a walkable **3D mode**, per-waifu **zero-shot voices** and an in-app **waifu creator**.

- **A waifu is a voice and a persona, nothing more.** Switching her never changes the model, intelligence, tools, permissions or memory scope.
- **KASANE** is the kernel (Python, `kasane/`). Clients are Tauri 2 + TypeScript + three.js / `@pixiv/three-vrm` (`src/`, `src-tauri/`).
- Seeded from the author's earlier project **Yuri** (which succeeded **Luna**). Both live at `github.com/YatharthJorwal/Yuri` and `.../Luna`.
- Single user, single Windows PC, local-first. Target machine: RTX 3060 12 GB, i5-14400F, 32 GB DDR5-4800.
- Windows packaging comes later (phase K7) but constrains design from day one (RULES §9).

Current status and plan: `docs/STATE.md`, `docs/TODO.md`.

## 2. Session protocol

### At the start (mandatory, in order)

1. Read `docs/HANDOFF.md` completely. It is the narrative from the last session.
2. Read `docs/STATE.md` (current state, known issues, what is verified).
3. Read `docs/TODO.md`, at least the current phase.
4. Skim `docs/RULES.md`. Read the `docs/SPEC.md` and `docs/ARCHITECTURE.md` sections relevant to the task. Search `docs/DECISIONS.md` before changing anything that looks settled.
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
6. **No hard-coded paths.** Use `kasane/paths.py` (dev: `./data`; packaged: `%APPDATA%\Kokyu`).
7. **Never block** the kernel's asyncio loop or the render loop.
8. **Honest verification.** No claim without running it.

## 4. Repository map

```
CLAUDE.md             this file
README.md  LICENSE    public face (MIT)
kasane/               Python kernel: app.py, bus.py, config, paths, router/, models/, memory/,
                      audio/, waifus/, threads/, scenes/, senses/, tests/
src/                  frontend: React UI chrome + imperative three.js engine (stage, pets, 3D)
src-tauri/            Rust: windows, tray, hotkeys, child processes (Job Object)
config/               config.example.yaml, models.example.yaml, secrets.example.yaml
scripts/              seed_waifus.py, doctor, packaging
tests-fe/             frontend tests
docs/                 SCOPE, SPEC, ARCHITECTURE, RULES, DECISIONS, TODO, STATE, HANDOFF, TTS-BACKEND
data/                 runtime data (gitignored)
```

The tree above is the **target**. Phase K0 creates it by seeding from Yuri; until then only `docs/` exists. Check `STATE.md` for what actually exists.

## 5. Commands

Inherited from Yuri; **confirm each works during K0** and fix this list.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r kasane\requirements-dev.txt
npm install

npm run tauri dev                         # desktop shell; starts the kernel itself
npm run dev                               # browser tab at http://localhost:1420 (do NOT run alongside tauri dev: same port)
npm run doctor                            # why a window does not load
npm run check                             # tsc --noEmit + frontend tests + vite build + cargo check (K0 creates this)
.\.venv\Scripts\python.exe -m pytest kasane -q
.\.venv\Scripts\python.exe kasane\check.py [--refresh]   # config, keys, model catalog, spend
```

`npm run check` plus `pytest` is the **definition of green**.

## 6. Conventions (short)

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`), small and focused. Never force-push `main`.
- **Python:** 3.11+, type hints on public functions, `logging` not `print`, `pathlib` for paths, async-first.
- **TypeScript:** `strict`, no unexplained `any`. UI chrome in React; the three.js engine is an imperative module outside React state. Clients hold **no business logic**: they render kernel state.
- **Config:** every tunable is a config key with a default in `config/config.example.yaml`. Windows paths in YAML use **single quotes**.
- **Tests:** every kernel feature gets pytest coverage; tests that touch models use fakes. No GPU, network or key may be required for the suite.
- **Docs:** spec IDs (`FR-…`) are referenced from TODO items, tests and commits.

## 7. Things that bite on this machine

- Two dev servers share **port 1420**: run `npm run tauri dev` *or* `npm run dev`, never both.
- Kokyu's kernel defaults to **127.0.0.1:8780**. Do not reuse 8765 (Luna's port; Yuri may use it too).
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
| What exactly must it do? | `docs/SPEC.md` |
| How is it put together? | `docs/ARCHITECTURE.md` |
| What must I never do? | `docs/RULES.md` |
| Why was X decided? | `docs/DECISIONS.md` |
| What is next? | `docs/TODO.md` |
| What is true right now? | `docs/STATE.md` |
| What happened last time? | `docs/HANDOFF.md` |
| How do I set up voice? | `docs/TTS-BACKEND.md` |
