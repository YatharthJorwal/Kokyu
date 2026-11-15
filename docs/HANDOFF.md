# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** If the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-15, about 14:05
- **Session:** 4 (15 November): lazy boot (D-060), app icon, voice on demand (D-061), Yuri reduced to a character and the kernel split by job (D-062), heart and thinking lines (D-063)
- **Written by:** Claude, with the user (Yatharth)

## 1. The project in ten lines

1. Kōkyū: a Windows chat app for a roster of AI companions; KASANE (`KASANE/`) is the Python kernel; Tauri + React client (three.js avatar code waits in `src/engine/` for K2).
2. A waifu is a **voice and a persona only**; she never changes the model, intelligence or capabilities. Memory is shared. (D-003, D-005)
3. **Luna and Yuri are the two premade companions**, packs in `assets/premade/` with the user's own assets (D-041). **Yuri is only a character** (D-062): no code path names her.
4. The code is **proprietary** (D-040); keep the repo private.
5. Zero-shot voices through the existing GPT-SoVITS at `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (D-042), started only when voice mode is on (D-061).
6. Kernel on 127.0.0.1:8780; llama-server 8080; GPT-SoVITS 9880; Vite 1420.
7. Default chat model on this PC: **`qwen3.5:9b` on Ollama** (D-060). The 35B on llama.cpp starts only when picked or messaged (about 2 minutes).
8. Spec v1.0 is the baseline (D-044); changes go through new decisions, and **every commit and decision cites its FR/D IDs** (the user checks this).
9. Claude works **directly on the user's Windows PC** (`D:\AI\Kokyu.ai`, Claude desktop app), often while the user is away, and commits item by item after a green `npm run check`. Claude cannot see the Tauri window or hear audio: those stay "not verified" until the user looks.
10. Plan: `TODO.md`, K1 (§4 below).

## 2. How the user works

Solo developer, casual, wants direct commands and no manual file shuffling, phases with gates, honesty about verified vs not. They want a **clean, fast, flexible** codebase, not a Yuri copy ("Yuri is supposed to be a reference"), and an uncluttered tree ("i am counting on you"). They send short UI suggestions mid-task (for example "the messages should start at bottom not top") and expect them done. They run other Claude sessions in parallel; relayed answers arrive from them. The user sometimes toggles a "ponytail" mode (smallest complete change; end replies with what was skipped and the risks); it was off for most of this session.

## 3. What happened

### Session 4 (15 November 2026)

- **The user's request:** `npm run tauri dev` barely loads, lags the PC, sometimes crashes File Explorer; the code "feels slow"; the tree is cluttered; finish K1 and the UI, place the icon, and build a cleaner, faster, flexible kernel than the Yuri copy. Then: "code still mentions Yuri all the time. fix it. make it a flexible orchestrator, yuri must only be a character."
- **Lazy boot (`9a667ba`, D-060):** the cause was the boot, not a package (everything loaded at once). Port first; the chat model after the first window connects; llama.cpp only on a pick. Live verified.
- **Icon (`d89c094`).**
- **Voice on demand (`2a31515`, D-061, relayed from a peer session):** nothing voice-related at launch; a Voice switch in the `＋` tray starts GPT-SoVITS (47 s) and faster-whisper.
- **Yuri only a character, in three commits (D-062):**
  1. `038ad7e` naming: module loggers instead of 121 `print("[yuri] …")` lines, `kernel.log`, crate `kokyu`, a neutral fallback persona, tool instructions moved into the shared addendum (Luna never had them), the tray's click-through, "Use API model" and the F9 hotkey removed. `lib.rs` from 688 to about 330 lines.
  2. `d512ac9` protocol v1 only; Yuri's widget deleted, the avatar code moved to `src/engine/`; screen companion remarks stored in the thread (ambient, never sent to a model); a send_file the vision model cannot see now ends the turn.
  3. `d5da9f8` `app.py` (2,097 lines) split into `app.py` (server, 177), `session.py` (one `Session` per window, `on_<type>` per message), `turns.py`, `ambient.py`, `companions.py`, `boot.py`, `hub.py`; faster-whisper and sqlite-vec import lazily (`import app` 750 → 615 ms). Comments across the kernel that named `_run_turn`, `ws_endpoint` or "orchestrator" now name the new modules.
- **Fix found during the split (`8e4997b`, SPEC §4.2):** tray Quit waited only until windows left `hub.connections`, which happens before their memory pass; Quit could exit mid-pass. A leaving window now counts in `hub.closing` until done.
- **UI (`fb804a1`, D-063, the user's two requests):** the heart sits above the input, traces while thinking beside rotating "<name> is …" lines, and beats once when the reply starts; short threads sit on the input box and grow upwards.
- **Live checks** (browser pane, real kernel, Ollama `qwen3.5:9b`): send, stream, Stop, switch Luna ↔ Yuri with dividers, the thinking row; after the split again: a reply streamed and the switch worked, with no errors in the kernel log.
- **Observed:** one cold 9B load took 104.6 s while the 4B classifier and the 9B swapped in VRAM (input for K1-09).
- **Refused by auto mode:** `git push`; moving `KASANE/vrm/` (duplicate VRMs) to the Recycle Bin.

### Session 3 (14 to 15 November 2026)

K1-00 to K1-08b (threads, typed protocol, per-thread model, window, llama.cpp 35B, React chat window, model picker and loader, sidebar, Markdown, tray, screen companions, companion chip, AI Router billing, one API endpoint at a time with keys in the Credential Manager). Review rounds fixed real bugs each time. Peers built the premade packs and wrote untracked `vram.py` (K1-09) and the effort slider files (K1-11). See `git log` up to `5b04a30`.

## 4. Where we stopped

Everything up to `8e4997b` plus this session's docs commit is on `main`, **not pushed** (10 commits ahead of `origin/main`). `npm run check` was green after `d5da9f8`; pytest 945 after `8e4997b`. The session 4 plan in `TODO.md` is done up to C-2 and K1-15a. **Next in order:** K1-04b (token counts), K1-07b with K1-11 (capabilities in `config/models.yaml`, then integrate the peer's effort slider files and add "max"), K1-09 (integrate the peer's `vram.py`), K1-12, K1-13, K1-15 (UI to `docs/reference-images/chat-ui.webp`), K1-14, the K1 gate.

## 5. Next session: start here

1. `git log -5 --oneline`, `git status`; ask the user to push if `origin/main` is behind. Then `KOKYU_PYTHON="$PWD/.venv/Scripts/python.exe" npm run check`.
2. Ask the user to run `npm run tauri dev` once and report: how fast the window appears, whether the tray menu looks right (Show/Hide Kōkyū, Quit), whether the 9B answers, and whether a voice line plays after turning Voice on in the `＋` tray.
3. Ask the user to delete `KASANE/vrm/` (TODO C-1b) or allow Claude to.
4. Then K1-04b, and the K1 items in the order of §4.

## 6. Open questions for the user

- **`KASANE/vrm/`:** delete it (duplicates of the pack VRMs)?
- **Reference items outside K1** ("VR space", "Enable 2D pet", "Enter 3D Space"): the default is to leave them out until their phases (D2, K4, K5).
- **D-058:** unpriced models (DeepSeek) blocked while a cap is on: keep, or allow with a warning?
- **D-055:** relax the persona's "no markdown" rule?
- **D-057:** move the websocket token check earlier?
- **Premade packs:** commit `assets/premade/` (large VRM/WAV) or keep them local?
- **Page file:** setting it to system-managed is the user's call (a Windows setting).

## 7. Traps and gotchas

- **Where things live now (D-062):** a message handler is `Session.on_<type>` in `session.py`; the turn is `turns.run_turn`; who drives is `hub.driver`; the shutdown event is `hub.shutdown_event`. Adding a message type = `protocol/` model + `CLIENT_TYPES` entry + `src/net/protocol.ts` + one `on_<type>` (a test checks the handler exists).
- **Tests patch the module that owns the name:** `turns.send_speak`, `turns.log_transcript_turn`, `companions.system_message`, `boot.check_chat_model`, `hub.connections`, `hub.driver`, `hub.shutdown_event`, `conversation._manager`. To change `CONFIG` for a test use `kernel_fixtures.set_config(monkeypatch, cfg)`: several modules bind `CONFIG` at import.
- **Call through the module** (`turns.send_speak(...)`, `llm.stream_reply(...)`), never `from x import fn`, or monkeypatching misses.
- **A pytest fixture or a local variable named like a module shadows it** (a fixture called `boot` hid the `boot` module; a local `tools = …` hid `tools`). Name them otherwise.
- **TestClient** opens each socket on its own loop. For WebSocket tests, patch `hub.shutdown_event` with a fresh `asyncio.Event()`, `hub.driver` with None, and set `KOKYU_DATA_DIR` to tmp (conftest does).
- **The Bash tool mangles backslashes**, even inside quoted heredocs. For text with backslashes use the Edit tool. For multi-file edits, a Python script with `assert s.count(old) == 1` per replacement works well.
- **`sed -i` over many files rewrites line endings** of files it did not change; restore those with `git checkout --`. Python's `Path.write_text` on Windows writes CRLF, which `core.autocrlf=true` normalizes, so that is fine.
- **Stage explicit paths.** Untracked peer files (`vram.py`, `test_vram.py`, effort-slider files, `assets/premade/` with VRM/WAV, `.claude/`) sit in the tree, and `package-lock.json` has an unrelated change; `git add -A` would commit them.
- **Auto mode refuses** `git push` and deleting user files (even to the Recycle Bin): ask the user.
- **No bulk string replacement** in source; single-match edits only.
- Kernel modules are **flat** (`import paths`, `from audio import tts`); tests have **no `__init__.py`**.
- `turns.run_turn` must never mention a waifu (a test enforces it).
- **Keys:** `shell_keys` holds at most one app key; conftest clears it. Live Credential Manager tests: `cd src-tauri && cargo test --offline --lib -- --ignored --test-threads=1`, then `cmdkey /list:Kokyu/*` must show NONE.
- **Router billing:** a call captures `catalog` and `api_id` when it starts; `_bill`, `_record` and `_settle` take them as arguments.
- **Ports:** 8780 kernel, 8080 llama-server (Ollama's runners are also `llama-server.exe`: check the port, not the name), 1420 Vite, 9880 GPT-SoVITS.
- **`KOKYU_DATA_DIR`** also moves where `config.yaml` is read. For live tests in a scratch folder, copy the config in.
- **Tests read the user's `config/config.yaml`** when it exists; keep new tests independent of it.
- **Quit via the tray** (or `POST /shutdown`). Killing loses the memory pass until the next start and can leave `llama-server` running.
- **Live UI checks:** run the kernel (`cd KASANE && ../.venv/Scripts/python.exe app.py`), the page with the `ui` preview (Vite on 1420), and drive it in the built-in browser. Stop the kernel with `curl -X POST http://127.0.0.1:8780/shutdown`.

## 8. Deliberately not done

- Real-window, tray, audio, API and visual verification (needs the user or a key).
- First-token latency was not re-measured after the split (behaviour is unchanged; boot import was measured).
- `KASANE/voice_files/` stays: `scripts/build_premade.py` reads the voice clips from it.
- Custom API endpoint UI (K1-13); per-provider headings in the picker.
- A pinned llama.cpp download (W-03); a `kernel.port` config key.
- Yuri's old memory is not imported into the new `memory.db`.

## 9. Update checklist (end of every session)

- [x] Date, session, author
- [x] §3 new entry; §4 exact stopping point; §5 first actions; §6 open questions only
- [x] §7 new traps; §8 skipped items
