# HANDOFF — Kōkyū

**Read this at the start of every session; rewrite it at the end.** Short by design (D-076): status is in `STATE.md`, the plan in `TODO.md`, decisions in `DECISIONS.md`. If the date is old, trust `git log` and ask the user.

- **Last updated:** 2026-11-24, session 8
- **Written by:** Claude (desktop app, with the user)

## 1. How the user works

A solo developer who wants direct commands, no manual file shuffling, and honesty about what was verified. They send short UI notes mid-task, often with screenshots (c.ai is their model for roleplay UX), and usually end a batch with "push after this". They test builds on their own PC. Kōkyū is primarily a **roleplay character app** to them (D-079).

## 2. What happened in session 8

1. The user's UI notes, one batch at a time, each pushed: the pet's second round, sizes by head matching, the cat button and Pet settings (D-105..D-110); the Stage caption from Yuri with a Caption glow (D-111); readable accent text and the voice's start and fail notes (D-112); round swatches, five theme presets, the Stage speaking by default with paced fading captions (D-113); the sidebar badge following a switch (`783e39b`). All pushed up to `783e39b`.
2. `/ponytail-audit` of the whole repo (four read-only reviewers, findings checked against the code), then "check rest of the stuff and fix current bugs": two more reviewers read what the first pass had skipped, and every bug was fixed in four commits, `781cd84`, `af5b98a`, `62ec66f`, `38768de`, plus the offline note going away on reconnect (`80ed917`). D-114 lists what a user can notice. Pushed on the user's word.
3. "do the todo cleanup" (AUD-03, `684eb1d`): unused helpers and the duplicate animation folder deleted. The user chose to **keep the voice input code** (voice.py, vad.py, mic-stream.ts) for K2. Not pushed.

## 3. Where we stopped

`npm run check` green on this PC (tsc, frontend 219, build, cargo, pytest 1380). Browser pane, injected state: Settings takes and returns focus; the offline note; the Stage's silent pacing. **Nothing from the audit was run in the desktop app.** Untracked and staying so: `assets/premade/`, `.claude/`.

## 4. Next session: start here

1. `git status`, `git log -8 --oneline`, `npm run check`. Ask whether to push `684eb1d` and its docs commit if they are not on origin.
2. With the user, in the desktop app: `STATE.md` §5's new D-114 and Stage lines, then the older unchecked ones.
3. Checkpoint UI-1 is still open; UI-2's references (UI2-01) come next on the user's word.

## 5. Traps

- **The Bash tool mangles `\\n` and some quotes in heredocs** (it rewrote `"\\n"` as a real newline twice this session). Write edit scripts with the Write tool into the scratchpad and run them; `edit.py` there asserts each replacement's count.
- **`/shutdown` now deletes `logs/kernel.pid`:** a test calling `app.shutdown_endpoint` must set `KOKYU_DATA_DIR` to a temp folder, or it removes the real one.
- **The TrustedHost check allows `testserver`** for FastAPI's TestClient; a test that sets another Host gets 400.
- **A send that arrives while a turn is finishing** (turn_done sent, a companion switch still applying) waits in `Session.settled()`; a test that sends right after a mid-reply switch no longer needs to wait for anything, but a handler added with `if self.busy:` should use `settled()` instead.
- **`set_story` writes only when `through_message_id` is 0 or a message of that thread:** a test summary needs real message ids.
- **Fact decay reads `decayed_at`:** a test that backdates a fact must backdate `decayed_at` too.
- **A socket test waiting on a frame that never comes hangs the suite** (no pytest timeout): run suspects as `timeout 120 .venv/Scripts/python.exe -m pytest … -o faulthandler_timeout=30`.
- **A zustand selector must not build a new array or object**: it re-renders forever.
- **Bare class names collide** (`.waking`, `.warn`): `grep -n '^\\.name' src/app/*.css` first.
