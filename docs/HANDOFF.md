# HANDOFF — Kōkyū

**Read this at the start of every session; rewrite it at the end.** Short by design (D-076): status is in `STATE.md`, the plan in `TODO.md`, decisions in `DECISIONS.md`. If the date is old, trust `git log` and ask the user.

- **Last updated:** 2026-11-18, session 6
- **Written by:** Claude (a cloud session, autonomous mode, the user asleep)

## 1. How the user works

A solo developer who wants direct commands, no manual file shuffling, phases with checkpoints, and honesty about what was verified. They want a clean, fast, flexible codebase and an uncluttered tree. They watch the browser pane, send short UI notes mid-task, and often say "continue while I'm away" (that is autonomous mode: CLAUDE.md §2). They run other Claude sessions in parallel and test builds on their own PC. They push, or tell Claude to push. Kōkyū is primarily a **roleplay character app** to them (D-079).

## 2. What happened in session 6

The user tested UI-1 on their PC (2026-11-18): everything passed. They asked for polish items and a voice rework; the earlier session agreed the shape with them (D-097). This session built it on the branch `claude/trusting-galileo-6hmr3x` (cut from `main` at `ac987e1`, since merged into `main`), one commit per item (TODO UI1-12):

1. `88ae626` "Waifu-mode-engaging" back (the one approved exception to D-082); the thinking word's letters now share one slow ease-in-out lift (their two animations fought over `transform`, and the word's 2.4 s remount cut late letters mid-lift); the effort slider's end dots gone (6 px `.effort-stop` circles in near-black ink, half outside the track's caps); the ⋯ hover in the conversation list no longer a hard square (the row lit on `.thread-item:hover`, which ends on the sibling button).
2. `510d629` Her `[emotion]` tags shown muted and italic like `*actions*`, in Chat and Roleplay; never links, `[1]`, `[x]`, `items[index]` or code.
3. `1562135` `speech.speakable(text, mode)`: fixed rules over the whole finished reply before TTS (blocks, lines, inline, the roleplay dialogue cut, the shared rules, a punctuation tidy). Pytest on the user's own example.
4. `c29500e` **Read aloud** replaces voice mode: the `＋` menu item with a speaker icon, kept in settings.json, her voice (GPT-SoVITS) only while on, a chip counting to about 47 s. The turn streams text only; the session speaks the finished reply as its own task, in the voice of who wrote it. The spoken-delivery prompt layer is gone. Also fixed: the voice chip shared the bare class `waking` with D-096's loading strip.
5. `6a254cf` **Dictation**: a mic button beside Send and F9 (changeable in Settings → Voice) record; faster-whisper on the CPU writes it down; the words go in at the caret, never sent. `requirements.txt` caps PyAV below 19 (PyAV 19 breaks faster-whisper 1.2.1; found when this machine's fresh install picked 19.0.2).
6. `b6e97c8`, `f9648b0` **Chat memory** (UI1-13, D-098): the user's task 10, relayed by a sibling session ("a memory configurator … a slider for tokens 8k till however far it goes … a brief warning when exceeding hardware limit"). A context-length slider per model under Effort; `context_fit.context_for(ref)` is the one value every Ollama request for the model, the history budget and llama.cpp's `-c` use; the fit point comes from Ollama's `model_info` (or the GGUF header) and the room on the GPU; past it a one-line warning, never a block (Ollama loads anyway, llama.cpp's refusal stands).
7. `d65feec` **A message read aloud on request** (UI1-14, D-099, FR-V-10), on `main`: "add a speaker icon next to each of her message bubble so selected message can be read aloud even when automatic mode is off". A speaker after Copy in her messages' hover bar reads that message through `speakable` (the thread's mode), in the voice of who wrote it; clicked again it stops. With Read aloud off her voice starts just for it (`ReadAloud.ready(once)`, the tooltip says about 47 s) and idles afterwards. Protocol: `speak_message`, `speak_stop` (never stops a reply being written), `spoken`. One reading at a time.

## 3. Where we stopped

UI1-12, UI1-13 and UI1-14 are committed with their docs (D-097, D-098, D-099, SPEC, TODO, STATE). The branch is merged and **everything is pushed: `main` = `origin/main` at `40f3fa9`**. The bundle and the 403 workaround of the cloud session are no longer needed. UI-1 is code-complete; nothing is half-done in the code. Last check (`d65feec`): `npm run check -- --skip-cargo` green except the Windows-only `test_vram` test on Linux; audio and the desktop app not run. Untracked and staying so: `assets/premade/`, `.claude/`.

## 4. Next session: start here

1. `git pull` if needed (`main` at `40f3fa9` or later).
2. `git status`, `git log -8 --oneline`, then `.\.venv\Scripts\python.exe -m pip install -r KASANE\requirements-dev.txt` (the PyAV cap) and `npm run check`.
3. With the user, in the desktop app (`STATE.md` §5): Read aloud with Luna and Yuri, in a chat and a roleplay (the 47 s start, code and tables never spoken, only dialogue in a roleplay, Stop silences her, still on after a restart); the speaker on one of her messages with Read aloud off (her voice starts first, her own voice, a second click stops it); F9 dictation (Windows may ask for the microphone); Chat memory on the 9B (drag it, the reload, the warning past the mark, a reply at a large value); the tags' style; the letter animation; the slider's ends; the ⋯ hover.
4. Ask the user to confirm or reverse the assumed parts of D-097, D-098 and D-092..D-095 (open question 10).
5. Checkpoint UI-1 (the user signs off), then UI-2 or K1b (D-085); a new phase only on their word.

## 5. Traps

- **Bare class names collide:** `.waking` is the model loading strip's (D-096) and `.warn` the model chip's round badge; a modifier named the same on another element takes their size and colour (it happened twice this session). Check `grep -n '^\.name' src/app/*.css` first (CLAUDE.md §7).
- Chat memory: every Ollama request must build its options with its model (`llm._ollama_options(model)`); a test fails on a bare `_ollama_options()`. A model's measured VRAM is forgotten when its context changes.
- `test_vram`'s Windows-path test fails on Linux (backlog); `npm run check -- --skip-cargo` is red there for that alone.
- In a cloud session the venv is not `.venv\Scripts`: set `KOKYU_PYTHON` to the interpreter, and keep it in the same shell command (environment variables do not carry between tool calls).
- `ReadAloud.on` reads `CONFIG` at call time and `set()` rebuilds the config from the files: a test that installs a config by hand loses it at the next `set()`; put overrides in settings.json (`settings_file.write` + `apply_saved`). The conftest's `read_aloud_on` fixture turns it on for one test.
- `run_turn` returns the reply to speak and sends no `speak` frames; tests that want speech call `turns.speak_reply` after it.
- A headless Chromium has a fake microphone: `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`.
- The HMR-stamped module URL matters when injecting state in the browser pane (CLAUDE.md §7); the 1421 preview never connects to a kernel; inject with a fake socket or `useChat.setState`.
- A `disabled` button gets no mouse events in Chrome; the picker's `<li>` is `display: contents`.
- An injected `notice` needs every `Notice` field (`code`, `text`, `actions`).
- Two `websocket_connect` contexts in one TestClient test break on `hub.shutdown_event`'s loop.
- A menu's `onClose` passed inline re-runs its effect on every render: keep it in a ref (`Menu.tsx`).
- Shortcuts listen on `document`; a dialog that consumes Escape calls `preventDefault`. Settings' key capture listens in the capture phase and stops propagation, so neither the dialog nor a shortcut sees that press.
- The Windows console is cp1252: a Python script printing "Kōkyū" needs `PYTHONIOENCODING=utf-8`.
