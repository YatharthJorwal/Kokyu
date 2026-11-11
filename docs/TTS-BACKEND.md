# TTS-BACKEND — brief for the setup agent

This is a **self-contained task brief** for a CLI agent. Goal: a clean, headless GPT-SoVITS API server on the user's Windows machine that Kōkyū can drive per request with a different zero-shot reference clip. Kokyu's repo contains only an adapter; **this install lives outside the repo**.

## Why

The user's existing GPT-SoVITS folder is cluttered and the WebUI is in Chinese. They want a clean install, English documentation and no WebUI. Do **not** modify or delete the old folder.

## Machine

Windows 10/11, PowerShell, RTX 3060 12 GB, i5-14400F, 32 GB RAM. NVIDIA driver and CUDA runtime as installed; pick a PyTorch CUDA build that matches. Another process (the LLM, via Ollama or llama.cpp) shares the GPU, so VRAM use matters.

## Requirements

1. **Location:** a new folder outside any Git repo (ask the user for the path; suggest a short one such as `D:\tts\gpt-sovits-api`).
2. **Version:** the newest stable GPT-SoVITS release that supports **zero-shot voice cloning** (reference audio + its transcript, no fine-tuning). Record the version or commit hash.
3. **Isolation:** its own virtual environment. Do not touch global Python.
4. **Headless:** run the API server only (the project's `api_v2`-style entry point). No WebUI is started or installed as a dependency of the run path.
5. **Binding:** `127.0.0.1` only, port configurable (the upstream API default is believed to be 9880: verify).
6. **GPU:** CUDA enabled; half precision if supported, to save VRAM.
7. **Behaviour that Kōkyū depends on:**
   - Every request supplies its own `ref_audio_path`, `prompt_text` and `prompt_lang`; **no restart and no weight swap** between different clips.
   - One fixed base model for everybody.
   - Audio returned as WAV, either whole or streamed/chunked per request.
   - A health check endpoint or a documented way to test readiness.
8. **Scripts** in the backend folder:
   - `start.ps1 [-Port N]`: starts the server, waits until ready, prints the URL.
   - `stop.ps1`: stops it cleanly.
   - `smoke_test.py` (or `.ps1`): synthesizes **the same sentence with two different reference clips back-to-back** against the running server, saves two WAVs, prints the latency of each call and fails loudly on any error. Accept clip paths and transcripts as arguments.
9. **Docs** in English, in the backend folder: `INSTALL.md` (exact steps to rebuild from scratch), `README.md` (how to start/stop/test), and the **actual list of request parameters** the installed API accepts.
10. **Measure** VRAM idle and while synthesizing (for example with `nvidia-smi`) and report both numbers.

## API shape Kōkyū expects (verify against the installed version)

Believed `api_v2` interface: `POST /tts` (and `GET`) with fields:

| Field | Meaning |
|---|---|
| `text` | Text to speak |
| `text_lang` | Language of `text` (for example `en`) |
| `ref_audio_path` | Absolute path to the reference WAV (3 to 10 s) |
| `prompt_text` | Exact transcript of the reference clip |
| `prompt_lang` | Language of the reference clip |
| `streaming_mode` / `media_type` | Chunked output / `wav` |
| optional | `speed_factor`, `top_k`, `top_p`, `temperature`, `text_split_method`, `seed` |

If the installed version differs, document the real parameters in the README; Kōkyū's adapter will be adjusted to match what you record. If a different headless server works better for zero-shot, say so and explain before switching.

## Constraints

- Do **not** touch the Kokyu, Luna or Yuri repos, and do not put model weights or audio in any Git repo.
- Do not expose the server to the network.
- Do not start the WebUI, and do not leave background processes running at the end.
- Do not claim success without running `smoke_test` and showing its output.

## Done when (Gate T)

- [ ] `start.ps1` starts the server; `stop.ps1` stops it
- [ ] `smoke_test` passes with two different clips, no restart between them; latencies printed
- [ ] `INSTALL.md` and `README.md` written; real API parameters recorded
- [ ] VRAM idle and under load reported
- [ ] Version/commit and the final backend path reported to the user for `STATE.md`
