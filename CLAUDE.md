# CLAUDE.md — Kōkyū (Kokyu)

Instructions for any AI coding agent working in this repository. **Read this file fully at the start of every session**, then follow the session protocol below.

## 1. What this project is

Kōkyū is a Windows desktop app for AI companions, **primarily a roleplay character app** (D-079). It looks like a normal chatbot (sidebar, one input box, one model switcher), and each thread is either a **Chat** or a **Roleplay** (D-074). Planned on top: a VRM **stage view** with voice (K2), an in-app **companion creator** (K3), **desktop pets** and a walkable **3D apartment** (1.1).

- **A companion ("waifu") is a voice and a persona, nothing more.** Switching her never changes the model, intelligence, tools, permissions, memory scope or conversation mode.
- **KASANE** is the kernel (Python, `KASANE/`); users meet the name only as a quiet credit (D-089), and UI text says "Kōkyū's engine". The client is Tauri 2 + React + TypeScript (`src/`, `src-tauri/`), with three.js / `@pixiv/three-vrm` waiting in `src/engine/` for K2.
- Seeded from the author's earlier projects **Yuri** and **Luna** (`github.com/YatharthJorwal/Yuri`, `.../Luna`); Yuri and Luna are now only premade characters. Luna's apartment code is the base for the 3D apartment (D-078).
- One user per install, one Windows PC, local-first. Development machine: RTX 3060 12 GB, i5-14400F, 32 GB DDR5-4800.
- Commercial direction: a paid, one-time-purchase app where users bring their own models and keys (`docs/PRODUCT.md`). Ordinary users and a clean-machine install shape priorities.

Current status: `docs/STATE.md`. Plan: `docs/TODO.md`.

## 2. Session protocol (D-076)

### At the start

1. Read `docs/HANDOFF.md` (short: last session, stopping point, first actions).
2. Read `docs/STATE.md` (what is true now, open questions, issues).
3. Read the current phase in `docs/TODO.md`.
4. Read the `docs/SPEC.md` and `docs/ARCHITECTURE.md` sections the task touches. Check `docs/DECISIONS.md` (compact, with an index) before changing anything that looks settled. Read `docs/PRODUCT.md` when a task touches onboarding, packaging, assets or providers.
5. Run `git status`, `git log -5 --oneline` and `npm run check`. If reality disagrees with `STATE.md`, **tell the user before doing anything else**.

### During the session

- One TODO item at a time, in order, inside the current phase. A new phase starts only with the user's approval.
- Before a large change, **state the plan and wait for approval**.
- Anything not in `SPEC.md` needs a `DECISIONS.md` entry and the user's approval first. When a decision amends a SPEC row, rewrite the row in the same commit.
- **Autonomous mode** (the user says to continue while they are away): take the recommended answer to an open question, record it as **Assumed** in `DECISIONS.md`, keep it reversible, and do not start a new phase.
- Never claim something works that you did not run (RULES R-21).
- Commit on the user's PC after a green `npm run check`. **Push only when the user says.**

### At the end (once per session)

1. `docs/TODO.md`: tick finished items with their commit hash; add new tasks.
2. `docs/STATE.md`: rewrite it so it is true *now*.
3. `docs/HANDOFF.md`: rewrite it: what happened, where you stopped, the first actions next time, new traps, questions for the user.
4. `docs/DECISIONS.md`: add new entries (short; old bodies are never rewritten, only status-stamped).
5. Check that this file is still true. Commit the docs with a `docs:` message.

## 3. Hard invariants

Never traded away for convenience. Full list: `docs/RULES.md`.

1. **Waifu invariance.** No code branches on a companion id except to pick her prompt, voice parameters, VRM and pet sprites. Tests enforce this.
2. **One model entry point.** Every model call goes through `router.decide()` with a role.
3. **Local-only data.** Camera frames, mic audio, screen captures and memory-writer jobs never leave the machine. Roleplay fiction never reaches `memory.db`.
4. **No silent fallback.** A failed user-chosen model shows the error with *Retry* and *Switch model*.
5. **No secrets or assets in git.** Keys, `.vrm`, `.wav`, model weights, databases and logs are never committed. Stage explicit paths; never `git add -A`.
6. **No hard-coded paths.** Use `KASANE/paths.py` (dev: `./data`; packaged: `%APPDATA%\Kokyu`).
7. **Never block** the kernel's asyncio loop or the render loop.
8. **Only working controls.** No disabled placeholders, phase codes or internal words in the UI (D-082).
9. **Honest verification.** No claim without running it.
10. **The code is proprietary** (D-040): keep the repo private; record provenance for anything copied in or out.

## 4. Repository map

```
CLAUDE.md  README.md  LICENSE
KASANE/               Python kernel. Flat modules; the folder is on sys.path (`import llm`,
                      `from audio import tts`); there is NO `kasane` package.
  app.py              the server: routes, lifespan, entry point (port 8780)
  session.py          one Session per window; `on_<type>` per protocol message
  turns.py            one model turn: recall, prompt, router, stream, speech
  prompting.py        system prompt layers per mode (D-074)
  story.py            roleplay story memory (D-074)
  conversation.py     threads and history for a window
  companions.py       the active companion's persona and voice, nothing more
  ambient.py          screen companions (Task Guide, OCR watch)
  safety.py           the self-harm detector: patterns, a meaning check, the reply guard (D-121)
  boot.py  hub.py     start-up order (D-060, D-097); open windows and the driver
  model_loader.py  vram.py   loading the chat model; GPU memory and the check before a load (D-065, D-072)
  doctor.py           Settings → Doctor checks (D-067)
  settings_file.py    settings.json over config.yaml, applied live (D-070)
  llm.py  config.py  paths.py  persona.py  bus.py  context_budget.py  context_fit.py  provider_presets.py  shell_keys.py  check.py
  router/             decide(), roles, providers, catalog, budget, audit, redaction, listing for the picker
  memory/             shared facts, recall, writer, consolidation, the viewer's backend
  audio/              speech (speakable, DialogueFilter), read_aloud, tts, stt (dictation), arbiter, vad
  senses/             camera, look intent, OCR watch, Task Guide
  tools/  waifus/  threads/  protocol/
  tests/              pytest (fakes only; conftest stubs Ollama unloads and story memory)
  voice_files/        build_premade.py's input (voice clips; .wav gitignored)
  vrm/                duplicate VRMs, to be deleted by the user (C-1b)
src/app/              React window: store.ts, chat-state.ts, ui/ components, theme.ts, markdown.ts, scenario.ts
src/net/              typed socket (kernel.ts, protocol.ts)
src/engine/           three.js avatar code for K2
src-tauri/            Rust: window, tray, child processes (Job Object), API keys (Credential Manager)
assets/premade/       Luna and Yuri packs: text in git; VRM and WAV out of git, listed in ASSETS.sha256 (D-118)
assets/vrm-animations/ the animation pack's notes and licences for K2 (not served: `public/` ships in every build)
config/               config.example.yaml, models.example.yaml, secrets.example.yaml
scripts/              dev, doctor, check, clean, test-frontend, build_premade.py, calibrate_safety.py (needs Ollama)
tests-fe/             frontend pure-logic tests (Node test runner)
docs/                 SCOPE, PRODUCT, SPEC, ARCHITECTURE, RULES, DECISIONS, TODO, STATE, HANDOFF, THIRD-PARTY,
                      reference-images/, archive/ (frozen old notes and the full decision log)
data/                 runtime data (gitignored)
```

## 5. Commands

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r KASANE\requirements-dev.txt
npm install

npm run tauri dev       # desktop app; starts the kernel, which starts her voice only while Read aloud is on (D-097)
npm run dev             # kernel + page for a plain browser tab (reuses a kernel already running)
npm run dev:ui          # page only. Never together with `npm run dev` or `tauri dev`: port 1420
npm run doctor          # why a window does not load
npm run build           # tsc + vite build
npm run test:fe         # frontend pure-logic tests
npm run clean           # dist, test caches, __pycache__ (`clean:all` adds src-tauri/target)
npm run check           # tsc --noEmit + test:fe + build + cargo check + pytest (`-- --skip-cargo` without Rust; KOKYU_PYTHON overrides the interpreter)
.\.venv\Scripts\python.exe -m pytest KASANE -q
.\.venv\Scripts\python.exe KASANE\check.py --refresh   # config, key, catalog, spend
```

`npm run check` is the **definition of green**.

## 6. Conventions (short)

- **Commits:** Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`), small and focused, citing FR and D IDs. Never force-push `main`.
- **Python:** 3.11+, type hints on public functions, `logging` not `print`, `pathlib`, async-first.
- **TypeScript:** `strict`, no unexplained `any`. React for the window; the three.js engine is an imperative module outside React state. Clients hold **no business logic**: they render kernel state.
- **Config:** every tunable is a config key with a default in `config/config.example.yaml`. Windows paths in YAML use **single quotes**.
- **Tests:** every kernel feature gets pytest coverage with fakes. No GPU, network or key may be required, and no test may touch the user's Ollama or data.
- **Docs:** cite SPEC (`FR-…`) and decision (`D-…`) IDs in TODO items, tests and commits.

## 7. Things that bite on this machine

- **The user may be running the app** (`npm run tauri dev`: the kernel on 8780, Vite on 1420). Never start a kernel on 8780 or a page on 1420 then. Claude's browser preview runs on **1421** (`.claude/launch.json`). The kernel only accepts window origins on 1420, so the preview never connects to one (the socket gets 403; its plain HTTP GETs, such as portraits, still work). State is injected through the store module: `import('/src/app/store.ts')`, using the URL the page actually loaded (check `performance.getEntriesByType('resource')`, since HMR adds `?t=`).
- **A scratch kernel for live checks:** `KOKYU_DATA_DIR=<scratch>/live .venv/Scripts/python.exe KASANE/app.py` in the background, only when 8780 is free. Copy `config/config.yaml` into the scratch dir first (`KOKYU_DATA_DIR` moves where config is read). Stop it with `curl -X POST http://127.0.0.1:8780/shutdown`.
- **Never touch the user's Ollama service** beyond read-only GETs. `conftest.py` stubs `boot.unload_ollama`, and gives story memory a keeper that always finds the model busy.
- **Two config files (D-070):** `settings.json` (app data folder) wins over `config/config.yaml`. Read `CONFIG` at call time; `config.install` swaps it live.
- **Tests patch the module that owns the name** (`turns.send_speak`, `companions.system_message`, `boot.check_chat_model`, `hub.driver`, `vram.gpu_memory`, `llm.<fn>`). Call through the module; never `from llm import x`. A fixture or local named like a module (`boot`, `tools`) shadows it.
- **Where things live:** a message handler is `Session.on_<type>`; adding a message type means a `protocol/` model, a `CLIENT_TYPES` entry, `src/net/protocol.ts` and one `on_<type>` (a test checks the handler exists). `turns.run_turn` must never mention a waifu (a test enforces it).
- **Edits:** single-match replacements in a Python script (`assert s.count(old) == 1`, normalize CRLF). **Never bulk-replace** (it once replaced every "a" with "w" in five files). The Bash tool refuses some heredocs with `${…}` or triple quotes: write the script to a file, then run it.
- **Computer use sees a blank screen here.** Drive the desktop window through WebView2's debugging port instead (`HANDOFF.md` traps).
- **Vite can keep a stale transform** of a briefly empty file: restart the preview.
- **Bare CSS class names collide:** `.waking` is the loading strip and `.warn` the model chip's round badge, so a modifier with either name on another element inherits their size and colour. Check `grep -n '^\.name' src/app/*.css` before naming one.
- **The model popover's lists are CSS grids with subgrid rows** (check, name, meta, fit, badges); a new row element must keep the five cells.
- **`build_premade.py --force` rebuilds a pack from its sources**; it carries over only the hand-written `about` and `persona.md` (with its pointer). Anything else edited by hand in `waifu.yaml` is lost.
- `WinError 10048` on startup: a leftover `python.exe` holds the port.
- Quit through the **tray Quit item** (or `POST /shutdown`); killing the process skips the memory pass.
- faster-whisper on CUDA failed here (missing `cublas64_12.dll`); **STT runs on CPU**.
- Ports: 8780 kernel, 8080 llama-server (Ollama's runners are also `llama-server.exe`: check the port, not the name), 1420 Vite, 9880 GPT-SoVITS (dev install at `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228`, a space in the path).
- Live Credential Manager tests: `cd src-tauri && cargo test --offline --lib -- --ignored --test-threads=1`, then `cmdkey /list:Kokyu/*` must show NONE.

## 8. Definition of done (for any TODO item)

1. Code and tests written; `npm run check` green (or the failure is explained in `STATE.md`).
2. The SPEC rows it touches are satisfied, or the gap is recorded.
3. Verified vs not verified stated honestly in the commit body.
4. TODO ticked with the commit hash at the session's end.

## 9. Where to look

| Question | Doc |
|---|---|
| What are we building, what is cut, what ships when? | `docs/SCOPE.md` |
| Product, buyers, distribution, business questions | `docs/PRODUCT.md` |
| What exactly must it do? | `docs/SPEC.md` |
| How is it put together (incl. the voice backend contract)? | `docs/ARCHITECTURE.md` |
| What must I never do? | `docs/RULES.md` |
| Why was X decided? What is still open? | `docs/DECISIONS.md` (full old text: `docs/archive/`) |
| What is next? | `docs/TODO.md` |
| What is true right now? | `docs/STATE.md` |
| What happened last time? | `docs/HANDOFF.md` |
