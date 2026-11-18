# HANDOFF — Kōkyū

**Read this at the start of every session; rewrite it at the end.** Short by design (D-076): status is in `STATE.md`, the plan in `TODO.md`, decisions in `DECISIONS.md`. If the date is old, trust `git log` and ask the user.

- **Last updated:** 2026-11-18, session 7
- **Written by:** Claude (desktop app, with the user)

## 1. How the user works

A solo developer who wants direct commands, no manual file shuffling, phases with checkpoints, and honesty about what was verified. They want a clean, fast, flexible codebase and an uncluttered tree. They watch the browser pane, send short UI notes mid-task (often with c.ai screenshots: c.ai is their model for roleplay UX, minus like/dislike/report), and often say "continue while I'm away" (that is autonomous mode: CLAUDE.md §2). They run other Claude sessions in parallel and test builds on their own PC. They push, or tell Claude to push. Kōkyū is primarily a **roleplay character app** to them (D-079).

## 2. What happened in session 7

Session 6's work (UI1-12..14) was already on `main` at `40f3fa9`; HANDOFF was brought up to date (`c7d0359`). Then two rounds of the user's notes:

1. `cd872b5` **A message's ⋯ card** (UI1-15, D-100): ⋯ beside every bubble (left of the user's, right of hers) opens a card with the time and model, Copy, Edit (last line), Rewind to here (not on the latest), Pin (roleplay only) and New chat from here (both modes, same mode). Regenerate sits under her latest reply with c.ai-style swipes (‹ n/m ›). The speaker moved next to her name. Pins (max `story.max_pins`, 10) go in her per-turn note and never reach `memory.db`. The sidebar got a hide button and an All / Chats / Roleplays filter. The engine now sends `exchange_saved` before `turn_done`, so a live message carries its stored id.
2. `9597652` **A roleplay keeps its character; the story tray** (UI1-16, D-101): in a roleplay her chip opens her profile and the engine refuses a switch ("start a new chat"). The paperclip becomes a book: History (a page of every roleplay with her), New chat (the story again from its card), Memory (a box she keeps in mind every turn, up to 1000 characters, a `threads.note` column, schema 7, with the story's pins listed and Unpin), then Upload file and Read aloud; no screen companions. Settings → Voice's switch now says Off or On. Also the D-100 review fixes: a pin carried by Regenerate quotes the new text at once; rewinding to a user line drops its transcript row; a chat swipe re-logs the shown reply for the memory writer; no pin during a turn.

## 3. Where we stopped

UI1-15 and UI1-16 are committed with their docs (D-100, D-101, SPEC, TODO, STATE) and **pushed: `main` = `origin/main`**. Last check: `npm run check` green on this PC (see the commit body for what ran). Verified in the browser pane with injected state (no kernel): the card on both sides, swipes, the pin mark, the filter, hide and show, the story tray, History, Memory with a pin, the locked chip. **Not run in the desktop app with a real model.** Untracked and staying so: `assets/premade/`, `.claude/`.

## 4. Next session: start here

1. `git status`, `git log -8 --oneline`, `npm run check`.
2. With the user, in the desktop app (`STATE.md` §5): the ⋯ card on both sides, Regenerate and swiping back, Rewind, New chat from here in a chat and a roleplay, pins reaching her (ask her about a pinned fact), the roleplay chip, the book tray's History / New chat / Memory (save a note, then see her follow it), the sidebar hide and filter, the Read aloud switch; plus session 6's list still unchecked there.
3. Ask the user to confirm or reverse the assumed parts of D-097, D-098, D-092..D-095 and Claude's parts of D-100 (10 pins) and D-101 (Memory per story, 1000 characters, Upload file and Read aloud kept in the tray).
4. Checkpoint UI-1 (the user signs off), then UI-2 or K1b (D-085); a new phase only on their word.

## 5. Traps

- **A socket test waiting on a frame that never comes hangs the whole suite** (there is no pytest timeout): when a handler starts refusing something (D-101's roleplay switch), find every test that sends it (`grep -rn switch_waifu KASANE/tests`). Run a suspect suite as `timeout 900 npm run check`.
- **A zustand selector must not build a new array or object** (`useChat((s) => s.messages.filter(...))`): it re-renders forever and blanks the page. Select the slice, then filter outside (StoryDialog's Memory page).
- **Stored message ids reach the window in `exchange_saved`**, sent before `turn_done`; a live message without it has only a local key, and the ⋯ card's actions need the id (D-100).
- A fake thread in a test (`SimpleNamespace(...)`) needs every field `start_turn` reads, now including `note`.
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
