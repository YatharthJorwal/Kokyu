# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** If the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-17 (session 5 close: phase K1c, conversation modes, D-074, D-075)
- **Session:** 5 (17 November): "continue next step. when i return, it must be complete till as far as you can work … and then i will push". The next step was the modes plan; its six questions were unanswered, so Claude took the recommended answers (D-074, reversible) and built phase K1c with workflows (build, adversarial review, fixes). **Nothing is pushed: the user pushes.** Session 4 (15 November) finished K1 and the review notes (D-060 to D-073).
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
10. Plan: `TODO.md`. K1 and K1c are code-complete; both gates are the user's (`STATE.md` §6). Next phase after the gates: K1b (installer walking skeleton).
11. **Modes (D-074):** each thread is Chat or Roleplay, fixed at its start. The system message is persona + mode layer (+ scenario card) + shared addendum (+ tool guidance in chat) from `prompting.py`; the persona is only who she is.

## 2. How the user works

Solo developer, casual, wants direct commands and no manual file shuffling, phases with gates, honesty about verified vs not. They want a **clean, fast, flexible** codebase and an uncluttered tree. They watch the browser pane and send short UI notes mid-task ("left side looks kinda blank below input, suggestions?", "move the bot's message box closer to heart"); do them, then say what was done and what else could be done. They run other Claude sessions in parallel; relayed answers arrive from them. They sometimes toggle a "ponytail" mode (smallest complete change); it was off this session.

## 3. What happened

### Session 5 (17 November 2026): phase K1c, conversation modes

The user asked to "continue next step" and to have it as complete as possible when they return; they push. The six questions in `docs/notes/modes-plan.md` §9 were never answered, so Claude took the recommended answer to each and wrote them into D-074 as **assumed and reversible**: (1) mode fixed per thread; (2) chat about 3 to 4 lines, longer when the task needs it; (3) no tools in roleplay; (4) voice speaks only dialogue in roleplay; (5) no premade per-companion cards, cards are the user's and app-level in `threads.db`; (6) persona-only `persona.md` drafts for Luna and Yuri, `waifu.yaml` pointed at them, `prompt.md` kept.

- **`470a05e` docs:** SPEC §2.18 FR-MODE-1..10, Appendix A rules 3 and 6, D-074, TODO phase K1c.
- **`b1cd674` K1c-01, 02:** `threads.mode` and `scenario` (schema 3); `prompting.build_system_prompt(persona, mode=, scenario=)`; one builder `Session.system_prompt()` for every history[0] and the llama.cpp warm-up.
- **`d7021f8` K1c-03, 07:** roleplay turns (no forget, Task Guide, look intent or tools; profile-only recall framed as the real person; no `transcript_log`), `dispatch_tool_call(..., offered=)` refuses tools not offered, delivery layer per mode while voice is on, raw reply text kept (Markdown and line breaks survive), screen companions quiet in roleplay.
- **`cbfe424` K1c-05:** `speech.DialogueFilter`, a streaming cut on the speech side only; the chunker holds back a trailing `[tag]`.
- **`38e5f34` K1c-04:** `KASANE/story.py` (`StoryKeeper`, `story_memory`, schema 4): batched folds by the local memory writer, never the newest lines, fed per turn as "The story so far…".
- **`b080b2b` K1c-06:** saved cards (`scenarios`, schema 5) with `scenario_list` / `scenario_save` / `scenario_delete`; the opening line stored as her first message with `meta.opening` and written into the scenario block.
- **`c9dbf95` K1c-08:** the New roleplay dialog, the Roleplay badge, the roleplay renderer in `markdown.ts` (`rp-action`, `rp-ooc`), placeholder.
- **Review, then `4e698f9`, `5a1d972`, `c83f054`:** an adversarial review found real bugs, all fixed (D-075 lists them): a screen remark landing in a roleplay opened mid-check, a partial `[hap` kept on Stop, a cubic chunker regex, curly-quote direction, the fold's 512-token cap, a catch-up fold during boot, the save stuck on "Saving…", Start closing the dialog early, Escape in the delete confirm, bold inside an action.
- **`97de53a`:** the roleplay layer keeps her own personality inside a scenario; the chat voice note keeps the emotion tag; *New roleplay…* stacked under *New chat* (it wrapped and truncated beside it).
- **`2b99262`:** a log line per story fold (`story memory: folded N lines of thread …`), so the gate can see folds.
- **K1c-09 (no commit):** `assets/premade/{luna,yuri}/persona.md`, about 440 words each, who she is and nothing about format; `waifu.yaml` line 9 `prompt: persona.md  # … the original is prompt.md`. Both packs load.

Verified: `npm run check` green after `97de53a` (pytest 1209, frontend 140); the client in the browser pane on port **1421** (kernel offline, state injected). Not verified: any real model, voice, story folds on real Ollama, the Tauri window.

### Session 4, part 5 (15 November 2026, night): the user's review notes

The user sent screenshots (the effort thumb off the track at "No thinking") and c.ai references (grey bubbles, italic actions, avatars) with: "fix the slider, also only load the model that is selected. when selecting other one, unload rest. fix the colors too. add a theme selector …", "fix the core model persona (these are like c.ai characters …)" and "asterisk quoted words are an action so italic. double asterisk means bold. brackets are parenthesis". Answers given: helpers run on **the selected model**; embeddings **stay loaded**; themes get **presets, accent, message style and text size**; and a long note on modes (summarized in `docs/notes/modes-plan.md`).

- **`ea67e85`:** the slider's spring easing overshot by ~50 px with two stops; now a plain ease-out.
- **`c3a65a6` (D-072):** `llm.ACTIVE_MODEL` holds the picked Ollama model (`""` for llama.cpp/API, `None` before any load). `model_for` gives it to classifier, memory_writer and vision; `keep_alive_for` sends the configured 30m for it and the embedding model, 0 for anything else. `boot.load_chat_model` unloads every other Ollama model (`free_ollama`) and, for an API pick, stops llama-server; the loader runs the warm for instant (API) refs after READY. `helper_models` is now only the embedding model; `can_unload` may offer the classifier. **Trap found:** the first test run reached the user's real Ollama through `boot.unload_ollama` (tests in `test_warm_up.py` call the real `load_chat_model`); the run was stopped and `conftest.py` now stubs `boot.unload_ollama` for every test. Ollama's `/api/ps` was empty afterwards; whether the run unloaded something is not known.
- **`89bdb95` (D-073):** Settings → Appearance (`src/app/theme.ts`), localStorage `kokyu.theme`, applied in `main.tsx` before render and synced through the `storage` event. Seen in the browser pane (port 1421, kernel offline, messages injected through the store module).
- **Modes plan** (`docs/notes/modes-plan.md`, not built): mode per thread (Chat or Roleplay) and Live (Stage + voice) per window, three prompt layers (persona, mode, delivery), dialogue-only speech in Roleplay, story memory per roleplay, scenario cards. Six questions in its §9.

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

All code is committed through `2b99262`, plus this docs commit, **not pushed** (the user said they would push). `npm run check` green after `97de53a` (pytest 1209, frontend 140). **K1 and K1c are code-complete.** Left: **C-1b** (the user deletes `KASANE/vrm/`), the **K1 gate** and the **K1c gate** (the user, `STATE.md` §6), and K1c-10 (small review follow-ups, none blocking).

Nothing is half-done in the tree. Untracked and to stay so: `assets/premade/` (now with the `persona.md` drafts), `.claude/` (its `launch.json` runs the `ui` preview on 1421 so it never collides with the user's 1420); `package-lock.json` has an unrelated change.

## 5. Next session: start here

1. `git status`, `git log -5 --oneline`, `git log origin/main..HEAD` (empty if the user pushed). Then `npm run check`.
2. Ask the user to confirm or reverse the **six assumed answers in D-074** and to read Luna's and Yuri's `persona.md`. A reversal is a new decision superseding D-074 and a small change (most are one switch: tools in roleplay is the turn's tool list; voice of narration is the `DialogueFilter` call; mode change per thread is the store and the dialog).
3. Ask the user to run `npm run tauri dev` and walk the **K1c gate** and the **K1 gate** in `STATE.md` §6, and the open K0 items (voice per companion). Read the kernel log with them for a story fold and for D-072's unloads.
4. Fix what the gates find. K1c-10 follow-ups only if the user wants them.
5. Once the user signs K1 and K1c, phase K1b (installer walking skeleton). Read its TODO section and PRODUCT.md first; plan before code (R-46).

## 6. Open questions for the user

- **The six assumed answers (D-074):** mode fixed per thread; chat about 3 to 4 lines; no tools in roleplay; voice speaks only dialogue; no premade scenario cards (cards are yours, app-level); persona-only `persona.md` drafts. Keep or reverse each?
- **The persona drafts:** keep `persona.md` as written, edit it, or go back to `prompt.md`? Luna's text still mentions intimate roleplay from the original pack; your call.
- **`KASANE/vrm/`:** delete it (duplicates of the pack VRMs)?
- **D-058:** unpriced models (DeepSeek, and now any custom endpoint from Settings) blocked while a cap is on: keep, or allow with a warning?
- **D-057:** move the websocket token check earlier?
- **Premade packs:** commit `assets/premade/` (large VRM/WAV) or keep them local?
- **Reference items left out (D-068):** VR space and the 2D pet switch wait for their phases; say if you want them shown disabled instead.

## 7. Traps and gotchas

- **Modes (D-074):** the mode comes from the thread, never a companion; `run_turn` must not mention a waifu and the router role stays `chat` in both modes (a new role would silently route an API pick to the local default). Per-turn text (recall, story summary, delivery layer) goes into the ephemeral note, never history[0], or llama-server's cached prefix breaks.
- **`conftest.py` puts in a story keeper that always finds the model busy**, so no test reaches a real model through story memory; story tests build their own keeper. With `boot.unload_ollama` stubbed too, the suite never touches the user's Ollama.
- **Prompt tests join the constants** (`prompting.ROLEPLAY_LAYER` etc.), so prompt wording can be changed without touching tests.
- **`build_premade.py --force` rewrites the packs' `waifu.yaml`**, which would drop the `prompt: persona.md` pointer (the `persona.md` files themselves survive).
- **Preview port:** `.claude/launch.json`'s `ui` runs on **1421** so it never fights the user's `tauri dev` on 1420. With the kernel offline, state can be injected through the store module for UI checks.
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
- *Unload* for the embedding model (D-071); the TTS backend as a named resident. Editing the default model and the llama.cpp presets in the app (they stay in config.yaml, D-070); voice settings (K2).
- TTS backend and renderer as named VRAM residents (they show as "other programs"); several NVIDIA GPUs read as unknown.
- Paging in the memory viewer (newest 500 live facts).
- First-token latency not re-measured after the kernel split.
- Yuri's old memory is not imported into the new `memory.db`.

## 9. Update checklist (end of every session)

- [x] Date, session, author (2026-11-17, session 5)
- [x] §3 new entry; §4 exact stopping point; §5 first actions; §6 open questions only
- [x] §7 new traps; §8 skipped items
