# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** If the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-15, night (session 4 close, after K1-09b)
- **Session:** 4 (15 November): lazy boot, icon, voice on demand, Yuri only a character and the kernel split (D-060 to D-063); then "push it and finish the rest": K1-04b, K1-07b/K1-11, K1-09, K1-12, K1-13, K1-15 (D-064 to D-069); then, with the user's answer "Settings file wins", K1-13b (D-070); then "yeah finish up": K1-09b (D-071). K1 is code-complete.
- **Written by:** Claude, with the user (Yatharth)

## 1. The project in ten lines

1. Kōkyū: a Windows chat app for a roster of AI companions; KASANE (`KASANE/`) is the Python kernel; Tauri + React client (three.js avatar code waits in `src/engine/` for K2).
2. A waifu is a **voice and a persona only**; she never changes the model, intelligence or capabilities. Memory is shared. (D-003, D-005)
3. **Luna and Yuri are the two premade companions**, packs in `assets/premade/` with the user's own assets (D-041). **Yuri is only a character** (D-062).
4. The code is **proprietary** (D-040); keep the repo private.
5. Zero-shot voices through the existing GPT-SoVITS at `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (D-042), started only when voice mode is on (D-061).
6. Kernel on 127.0.0.1:8780; llama-server 8080; GPT-SoVITS 9880; Vite 1420.
7. Default chat model on this PC: **`qwen3.5:9b` on Ollama** (D-060). The 35B on llama.cpp starts only when picked (about 2 minutes).
8. Spec v1.0 is the baseline (D-044); changes go through new decisions, and **every commit and decision cites its FR/D IDs** (the user checks this). SPEC rows changed by a decision carry its ID inline (D-068 amended FR-C-4, FR-C-6, FR-S-1, FR-M-1).
9. Claude works **directly on the user's Windows PC** (`D:\AI\Kokyu.ai`, Claude desktop app), often while the user is away, and commits item by item after a green `npm run check`. Claude cannot see the Tauri window or hear audio: those stay "not verified" until the user looks.
10. Plan: `TODO.md`. K1 is code-complete; the K1 gate is the user's (`STATE.md` §6). Next phase after the gate: K1b (installer walking skeleton).

## 2. How the user works

Solo developer, casual, wants direct commands and no manual file shuffling, phases with gates, honesty about verified vs not. They want a **clean, fast, flexible** codebase and an uncluttered tree. They watch the browser pane and send short UI notes mid-task ("left side looks kinda blank below input, suggestions?", "move the bot's message box closer to heart"); do them, then say what was done and what else could be done. They run other Claude sessions in parallel; relayed answers arrive from them. They sometimes toggle a "ponytail" mode (smallest complete change); it was off this session.

## 3. What happened

### Session 4, part 4 (15 November 2026, night): K1-09b, "yeah finish up"

**`a5fbe72` (D-071):** the graphics-memory refusal card offers *Unload X* for a named Ollama model the kernel will not load again at once: in practice the previous chat model kept as the memory writer. Not the classifier or the embedding model: `warm_helpers` reloads them right after the chat model, so unloading them would only bring back the swap. One click unloads it (`keep_alive: 0`) and tries the load again; the kernel accepts only a model the failed status offers. Tested with fakes (pytest 997); **not seen in a window**: the user had `npm run tauri dev` running (its kernel on 8780, Vite on 1420), so Claude started no scratch kernel and sent nothing to Ollama.

### Session 4, part 3 (15 November 2026, night): K1-13b

The user answered the precedence question: "Settings file wins". **`0222d2e` (D-070):** `settings.json` in the app data folder holds what Settings edits, in config.yaml's layout, and wins key by key; it is laid over config.yaml at kernel start (lifespan, before boot) and after each change, and `config.install` rebinds every module's `CONFIG` so a change applies with no restart (`Router.reconfigure` follows). Settings → Models now edits the Ollama address (this PC only: what the companions see and hear must not leave it), a custom OpenAI-compatible endpoint (https; provider id from its host; never a developer key; listed in the picker's Key form) and the budget caps. A new **Screen** section has "On now" and "On at start" for Task Guide and OCR watch (FR-SC-1's Settings half, left open by D-056); at start a mode passes the same vision check as the ＋ tray. Found while checking live: the form fields stretched 220 px tall (fixed), and a hand-edited plain value for a section would have wiped that section (now dropped with a warning). Live check in the browser pane against a scratch kernel; `npm run check` green (pytest 992, frontend 121).

### Session 4, part 2 (15 November 2026): "push it and finish the rest"

`48851b2` (the part 1 docs commit) was pushed at the user's request. Then, one item per commit, each after a green `npm run check` and a live check in the browser pane against a scratch kernel (`KOKYU_DATA_DIR` in the session scratchpad, never the user's data):

- **`953b682` K1-04b:** each reply stores its token counts (Ollama, API; llama.cpp when its stream reports usage).
- **`f69b1f6` K1-07b + K1-11 (D-064):** effort data lives in `config/models.yaml` / `models.example.yaml`, read by `router/capabilities.py`; the peer's slider files integrated, "max" added, effort remembered per model per thread (`threads.efforts`, schema 2). Found live: on High the 9B thought through the whole 512-token cap and said nothing, so thinking now gets `llm.reasoning_tokens` (4096) of room and an empty reply is an error card.
- **`d7180b8` K1-09 (D-065):** the peer's `vram.py` wired in. NVML from the driver DLL (no new dependency), measured sizes cached, fits / won't fit in the picker, and a refusal *before* any unload that names what holds the memory.
- **`77c6c00` K1-12 (D-066):** a failed turn shows a card under the turn (Retry, Switch model, Details) with plain words per failure kind.
- **`3e62a27` K1-13 (D-067):** Settings dialog: Models (read-only), Memory (correct = a new fact superseding the old; forget; restore; nothing hard-deleted), Doctor (one row per component with a fix hint), About. Found live: the GPU row warned whenever Kōkyū's own models filled the card; it now splits Kōkyū's share from other programs'. Editable settings and `settings.json` (FR-SET-2) were split off as **K1-13b**: they need the user's precedence answer.
- **`b4f17b8` K1-15 (D-068):** the window laid out to `docs/reference-images/chat-ui.webp`: frameless window with its own buttons, top bar (companion chip, Temp Chat switch), sidebar (logo, pink New chat, search, gear), one-row input box (paperclip, disabled mic, round send), model chip under it, one-line popover rows with capability badges from Ollama's `/api/tags`, "Spent today" footer. SPEC FR-C-4, FR-C-6, FR-S-1, FR-M-1 amended. Left out: VR space, 2D pet switch (later phases).
- **`3d87f72` (D-069), the user's review of K1-15:** Copy / Regenerate moved onto the reply's name line so replies end right above the heart; one column width; a status line left of the model chip (voice and screen chips, else Temp Chat, else a keyboard hint).

### Session 4, part 1

Lazy boot (`9a667ba`, D-060), icon (`d89c094`), voice on demand (`2a31515`, D-061), Yuri reduced to a character and `app.py` split by job (`038ad7e`, `d512ac9`, `d5da9f8`, D-062), Quit waits for the memory pass (`8e4997b`), heart and thinking lines (`fb804a1`, D-063).

### Sessions 1 to 3

K0 (seed from Yuri, packs, invariance) and K1-00 to K1-08b. See `git log`.

## 4. Where we stopped

All code is committed through `a5fbe72` (K1-09b), plus this docs commit; both are pushed. `npm run check` green after `a5fbe72` (pytest 997, frontend 121). **K1 is code-complete.** Left in K1: **C-1b** (the user deletes `KASANE/vrm/`) and the **K1 gate** (the user, `STATE.md` §6).

Nothing is half-done in the tree. Untracked and to stay so: `assets/premade/`, `.claude/`; `package-lock.json` has an unrelated change.

## 5. Next session: start here

1. `git status`, `git log -5 --oneline`, `git log origin/main..HEAD` (should be empty). Then `npm run check`.
2. Ask the user to run `npm run tauri dev` and walk the **K1 gate** in `STATE.md` §6 (frameless window drag / resize / buttons, close to tray; a local and an API model; model, effort and companion changed mid-thread; a wrong key for the failure card; the layout vs the reference). Also the open K0 items (voice per companion).
3. Ask the §6 questions.
4. Once the user signs the K1 gate, phase K1b (installer walking skeleton). Read its TODO section and PRODUCT.md first; plan before code (R-46).

## 6. Open questions for the user

- **Classifier:** keep `qwen3.5:4b` resident beside the 9B (`models.local.classifier` in `config/config.yaml`)? Together they fill the 12 GB card; the shipped default is one model.
- **`KASANE/vrm/`:** delete it (duplicates of the pack VRMs)?
- **D-055:** relax the persona's "no markdown" rule? Live, Luna answered a request for a bullet list in prose.
- **D-058:** unpriced models (DeepSeek, and now any custom endpoint from Settings) blocked while a cap is on: keep, or allow with a warning?
- **D-057:** move the websocket token check earlier?
- **Premade packs:** commit `assets/premade/` (large VRM/WAV) or keep them local?
- **Reference items left out (D-068):** VR space and the 2D pet switch wait for their phases; say if you want them shown disabled instead.

## 7. Traps and gotchas

- **Two config files (D-070):** `settings.json` (app data folder; `data/` in a checkout, the scratch dir under `KOKYU_DATA_DIR`) wins over `config/config.yaml`. Code must read `CONFIG` at call time (as all modules do): `config.install` swaps the object live, so a value copied from `CONFIG` at import or in a constructor goes stale (llama.cpp's Ollama address was one; fixed). Tests that install a config must put the old one back (`running_config` fixture in `test_settings_file.py`).
- **The user may be running the app** (`npm run tauri dev`: a `python.exe app.py` from `src-tauri` on 8780 and Vite on 1420). Check `netstat -ano | grep -E ":(8780|1420) .*LISTEN"` before starting a scratch kernel; never stop theirs, and stop any preview that would connect to it (it reads their real data).
- **Live tests of a custom endpoint:** use a `.invalid` host (`https://lab.example.invalid/v1`), so nothing can leave the machine.
- **Where things live (D-062):** a message handler is `Session.on_<type>` in `session.py`; the turn is `turns.run_turn`; who drives is `hub.driver`. Adding a message type = `protocol/` model + `CLIENT_TYPES` entry + `src/net/protocol.ts` + one `on_<type>` (a test checks the handler exists).
- **Tests patch the module that owns the name** (`turns.send_speak`, `companions.system_message`, `boot.check_chat_model`, `hub.driver`, `doctor._get_json` for every Doctor HTTP call including `/api/ps`, `vram.gpu_memory`). `conftest.py` stubs `vram.gpu_memory` and gives each test a fresh measured cache. To change `CONFIG` for a test use `kernel_fixtures.set_config(monkeypatch, cfg)`.
- **Call through the module** (`turns.send_speak(...)`, `llm.stream_reply(...)`), never `from x import fn`.
- **A fixture or local named like a module shadows it** (`boot`, `tools`). Name them otherwise.
- **Edits:** single-match replacements in a Python script (`assert s.count(old) == 1`, normalize CRLF to LF). The Bash tool's safety check refuses some heredocs that contain `${…}` or backticks ("could not be checked for dangerous rm"): write the script with the Write tool, then run it. Never `cat > file` a source file while Vite runs (see below).
- **Vite can keep a stale transform** of a file that was briefly empty ("does not provide an export named App"): restart the `ui` preview.
- **The model popover's lists are CSS grids and each row a subgrid** (check, name, meta, fit, badges). A new row element must keep the five cells or the columns break.
- **Live UI checks:** scratch kernel `KOKYU_DATA_DIR=<scratch>/live .venv/Scripts/python.exe KASANE/app.py` in the background (copy `config/config.yaml` into the scratch dir; `KOKYU_DATA_DIR` moves where config is read), the `ui` preview on 1420, the built-in browser. Its screenshots are 800 px wide: a 1000×625 viewport shows detail. Stop with `curl -X POST http://127.0.0.1:8780/shutdown`, then `preview_stop`.
- **Stage explicit paths**, never `git add -A` (untracked packs and `.claude/`).
- `git push` worked this session once the user asked for it; deleting user files is still refused by auto mode.
- Kernel modules are **flat** (`import paths`, `from audio import tts`); tests have **no `__init__.py`**. `turns.run_turn` must never mention a waifu (a test enforces it).
- **Keys:** live Credential Manager tests: `cd src-tauri && cargo test --offline --lib -- --ignored --test-threads=1`, then `cmdkey /list:Kokyu/*` must show NONE.
- **Ports:** 8780 kernel, 8080 llama-server (Ollama's runners are also `llama-server.exe`: check the port, not the name), 1420 Vite, 9880 GPT-SoVITS. Never touch the user's Ollama service; read-only GETs only.
- **Quit via the tray** (or `POST /shutdown`). Killing loses the memory pass until the next start.

## 8. Deliberately not done

- Real-window, tray, audio, API and visual verification in Tauri (needs the user or a key).
- *Unload* for the classifier or the embedding model (D-071); the TTS backend as a named resident. Editing the default model and the llama.cpp presets in the app (they stay in config.yaml, D-070); voice settings (K2).
- TTS backend and renderer as named VRAM residents (they show as "other programs"); several NVIDIA GPUs read as unknown.
- Paging in the memory viewer (newest 500 live facts).
- First-token latency not re-measured after the kernel split.
- Yuri's old memory is not imported into the new `memory.db`.

## 9. Update checklist (end of every session)

- [x] Date, session, author
- [x] §3 new entry; §4 exact stopping point; §5 first actions; §6 open questions only
- [x] §7 new traps; §8 skipped items
