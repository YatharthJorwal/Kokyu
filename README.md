# Kōkyū

> A desktop chat app for a roster of AI waifus. Local-first, built for Windows.

**Status: pre-alpha.** Phase 0 (skeleton) is code-complete: the kernel, shell and waifu packs exist; the chat UI, installer and the rest follow the plan in [`docs/TODO.md`](docs/TODO.md). Runs from source only.

Kōkyū (後宮, "the inner palace") is the app. **KASANE** (*Kernel for Adaptive Synthetic Agents, Networks and Embodiments*) is the kernel inside it.

**Direction:** a one-time-purchase Windows app where you bring your own models, keys and voices. A first-run wizard is meant to set up the plumbing so no terminal is needed. See [`docs/PRODUCT.md`](docs/PRODUCT.md).

## What it will be

A normal-looking chatbot UI with a roster of companions. A waifu is **a voice and a persona, nothing more**: switching her never changes the model, its intelligence or its capabilities.

- **Chat** with a history sidebar, one centered input box, a `+` tray (files, camera, voice) and a heart animation while she thinks and replies.
- **One model switcher** with a clear split between **Local** models (Ollama, llama.cpp) and **API** models (via AI Router), plus an animated thinking-effort slider.
- **Waifu switcher** next to it: change persona and voice mid-chat.
- **Stage view:** her VRM stands in front of you, with lip-sync, eye contact and idle motion.
- **Voice:** per-waifu zero-shot GPT-SoVITS voices, speech input, barge-in.
- **Create a waifu in the app:** upload a VRM and an ~8 s voice clip, pick personality traits, paste a system prompt.
- **Desktop pets:** 2D sprites that sit, walk and idle on your desktop.
- **3D mode:** walk around with WASD in scenes like an apartment or a garden, with one or two waifus.
- *Later:* agent mode (file access, Codex-style), VR, Windows installer.

## Requirements (target)

| | |
|---|---|
| OS | Windows 10/11 with WebView2 |
| GPU | NVIDIA, 12 GB VRAM recommended (developed on an RTX 3060 12 GB) |
| RAM | 32 GB recommended (large local models use system RAM) |
| Tools (from source) | Node.js 18+, Rust (stable), Python 3.11+ |
| Model runtime | [Ollama](https://ollama.com/download/windows) and/or a llama.cpp server |
| Voice (optional) | A headless GPT-SoVITS API server, see [`docs/TTS-BACKEND.md`](docs/TTS-BACKEND.md) |
| Avatars | Your own `.vrm` files, for example from [VRoid Studio](https://vroid.com/en/studio) |

## Install

> None of these paths exist yet. They are documented now so the project is built to support them.

**A. Windows installer** *(planned, phase K7).* Download the installer, run it, then complete the **Welcome to Kōkyū** wizard. Large components (model weights, local runtimes, the GPT-SoVITS backend) are not bundled; the wizard detects what is missing and installs it with your confirmation.

**B. Portable bundle** *(planned, phase K7).* Unzip, run `setup.ps1` once to create the Python environment and verify the machine, then launch `Kokyu.exe`.

**C. From source** *(works today).*

```powershell
git clone https://github.com/YatharthJorwal/Kokyu.git
cd Kokyu

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r KASANE\requirements-dev.txt

npm install
Copy-Item .env.example .env        # optional: add AIROUTER_API_KEY
npm run tauri dev
```

`npm run check` runs the whole test suite (`-- --skip-cargo` without a Rust toolchain). `npm run doctor` explains why a window does not load. `python KASANE\check.py` checks config, models and keys without starting the app.

## Premade companions

Luna and Yuri ship as built-in packs in `assets/premade/`. Build them from your own files with `python scripts/build_premade.py --help` (voice clip + transcript in `KASANE/voice_files/<Name>/`, your VRMs, the persona prompts), then commit `assets/premade/`.

## Your waifus

No characters, voices or model weights are included, and none may be committed. Everything personal lives in the app-data folder (`.\data` in development, `%APPDATA%\Kokyu` once packaged). Create waifus from inside the app (**＋ New waifu**).

## Documentation

| Doc | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Entry point and rules for AI coding agents |
| [`docs/SCOPE.md`](docs/SCOPE.md) | One-page overview of what is being built |
| [`docs/PRODUCT.md`](docs/PRODUCT.md) | Product direction, release boundaries, commercial and asset checklist |
| [`docs/SPEC.md`](docs/SPEC.md) | Requirements with IDs and acceptance criteria |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How it is built |
| [`docs/RULES.md`](docs/RULES.md) | Engineering and process rules |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Decision log (append-only) |
| [`docs/TODO.md`](docs/TODO.md) | Phased plan and gates |
| [`docs/STATE.md`](docs/STATE.md) | Current state and recent issues (living) |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Session-to-session narrative (living) |
| [`docs/TTS-BACKEND.md`](docs/TTS-BACKEND.md) | Brief for setting up the voice backend |

## Repository layout (target)

```
KASANE/        Python kernel (FastAPI/WebSocket, router, memory, audio, waifus)
src/           Frontend: React UI chrome + three.js / three-vrm engine
src-tauri/     Rust shell: windows, tray, hotkeys, child-process management
config/        config.example.yaml, models.example.yaml, secrets.example.yaml
scripts/       dev helpers (seed waifus, doctor, packaging)
docs/          the documents above
tests-fe/      frontend tests
data/          runtime data (gitignored)
```

## Lineage and credits

Kōkyū is the successor to two earlier projects by the same author, [Luna](https://github.com/YatharthJorwal/Luna) and [Yuri](https://github.com/YatharthJorwal/Yuri), and is seeded from Yuri's shell and kernel. It builds on [three.js](https://threejs.org), [`@pixiv/three-vrm`](https://github.com/pixiv/three-vrm), [Tauri](https://tauri.app), [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Ollama](https://ollama.com) and [llama.cpp](https://github.com/ggml-org/llama.cpp). Third-party licenses are tracked in `docs/THIRD-PARTY.md` (created in Phase 0).

## License

**Proprietary. All rights reserved.** Kōkyū is not open source; see [`LICENSE`](LICENSE). The documentation-only history up to commit `346f0c3` was published under MIT and stays MIT for those versions only.

The premade companions (Luna and Yuri: models, voices, prompts) are part of the proprietary software. Avatars, voice clips and animation files that *users* add keep their own licenses and stay on the user's machine.
