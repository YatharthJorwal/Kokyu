# Kōkyū

A roleplay character app for Windows: chat with AI companions on your own local models or API key. **KASANE** (`KASANE/`) is the Python kernel; the client is Tauri 2 + React + three.js (`src/`, `src-tauri/`). This repository is private and developer-facing; start with [`CLAUDE.md`](CLAUDE.md).

**Status:** see [`docs/STATE.md`](docs/STATE.md).

## Quickstart (PowerShell, from source)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r KASANE\requirements-dev.txt
npm install

npm run tauri dev       # desktop shell; starts the kernel (port 8780)
npm run dev             # kernel + page for a plain browser tab; never together with tauri dev (port 1420)
npm run doctor          # why a window does not load
npm run check           # definition of green: tsc, frontend tests, build, cargo check, pytest (`-- --skip-cargo` without Rust)
.\.venv\Scripts\python.exe KASANE\check.py --refresh   # config, key, catalog, spend
```

Needs Node.js, Rust (stable) and Python 3.11+. Optional for development: `.env` from `.env.example` for an API key (end users save keys in the app), Ollama or llama.cpp for local models, and a GPT-SoVITS install for voice (D-042). More commands: `CLAUDE.md` §5.

## Premade packs

Luna and Yuri live in `assets/premade/<id>/`. Their VRM, voice clip and persona files are local, **untracked** assets for now; what gets versioned is an open question (`docs/PRODUCT.md` §9). Build them from your own files:

```powershell
.\.venv\Scripts\python.exe scripts\build_premade.py --yuri-vrm C:\path\yuri.vrm --luna-vrm C:\path\luna.vrm
```

Voice clips and transcripts come from `KASANE/voice_files/<Name>/`, persona prompts from the Luna and Yuri repos (`--help` for the options; `--force` rebuilds). The script writes `prompt.md` and points `waifu.yaml` at it, so a `--force` rebuild undoes the hand-made `prompt: persona.md` line (D-074); set it back afterwards.

## Docs

| Doc | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Session rules, repo map, commands, traps |
| [`docs/SCOPE.md`](docs/SCOPE.md) | One page: product, invariants, cut list, release train |
| [`docs/PRODUCT.md`](docs/PRODUCT.md) | Direction and open business questions |
| [`docs/SPEC.md`](docs/SPEC.md) | Requirements with IDs |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How it is built today |
| [`docs/RULES.md`](docs/RULES.md) | Rules that never bend |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Decisions, open questions, superseded list |
| [`docs/TODO.md`](docs/TODO.md) | Forward plan |
| [`docs/STATE.md`](docs/STATE.md) | What is true and verified now |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Last session and first actions |
| [`docs/THIRD-PARTY.md`](docs/THIRD-PARTY.md) | Dependency licences and shipped assets |
| `docs/archive/` | Frozen older material |

## Licence

**Proprietary. All rights reserved** ([`LICENSE`](LICENSE), D-040). The documentation-only history up to commit `346f0c3` was published under MIT and stays MIT for those versions only.
