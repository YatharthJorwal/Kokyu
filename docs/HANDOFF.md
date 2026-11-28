# HANDOFF — Kōkyū

**Read this at the start of every session; rewrite it at the end.** Short by design (D-076): status is in `STATE.md`, the plan in `TODO.md`, decisions in `DECISIONS.md`. If the date is old, trust `git log` and ask the user.

- **Last updated:** 2026-11-24, session 8 (end)
- **Written by:** Claude (desktop app, with the user)

## 1. How the user works

A solo developer who wants direct commands, no manual file shuffling, and honesty about what was verified. They send short UI notes mid-task, often with screenshots (c.ai is their model for roleplay UX), and usually end a batch with "push after this". They test builds on their own PC. Kōkyū is primarily a **roleplay character app** to them (D-079).

## 2. What happened in session 8

1. The user's UI notes, one batch at a time, each pushed: the pet's second round, sizes by head matching, the cat button and Pet settings (D-105..D-110); the Stage caption from Yuri with a Caption glow (D-111); readable accent text and the voice's start and fail notes (D-112); round swatches, five theme presets, the Stage speaking by default with paced fading captions (D-113); the sidebar badge following a switch (`783e39b`). All pushed up to `783e39b`.
2. `/ponytail-audit` of the whole repo (four read-only reviewers, findings checked against the code), then "check rest of the stuff and fix current bugs": two more reviewers read what the first pass had skipped, and every bug was fixed in four commits, `781cd84`, `af5b98a`, `62ec66f`, `38768de`, plus the offline note going away on reconnect (`80ed917`). D-114 lists what a user can notice. Pushed on the user's word.
3. "do the todo cleanup" (AUD-03, `684eb1d`): unused helpers and the duplicate animation folder deleted. The user chose to **keep the voice input code** (voice.py, vad.py, mic-stream.ts) for K2. Pushed.
4. The user's answers to the open questions, recorded as D-115..D-118: the voice (GPT-SoVITS on the PC, or ElevenLabs with the user's own key and an in-app voice picker), explicit premades (payment provider deferred), a ComfyUI-like setup screen with cards and no accounts, the packs' text in git with VRM and WAV checksummed beside it. They asked what "UK and California" meant; explained in chat (Ofcom's age-assurance rule for porn-capable chatbots; SB 243 and New York's companion-chatbot duties). Checkpoint UI-1 ticked on their word. AUD-02's checks run in the desktop app, all passed.
5. The AI note under the message box in every mode (D-119, FR-C-11), checked in the desktop app. The legal stance for launch (D-120): sold as software on the user's PC, not an online service; UK sales held back until Ofcom answers; complying with SB 243 as if an operator; options weighed and nothing built for sale yet (B-13).
6. The self-harm detector (D-121, FR-C-12, SAFE-01): `KASANE/safety.py`, a turn-level stop in `turns.py`, the help card in `ThreadView.tsx`. A labelled set in `tests/test_safety.py` caught six false alarms in the first patterns ("burning myself out", "5 kms", "my brother overdosed" …), fixed. Checked live on scratch data. Then, on the user's yes, SAFE-02 (`35453c2`): the meaning check calibrated on the real embedder with `scripts/calibrate_safety.py` (0.80 / 0.10). All pushed up to `f247309`.
7. The second audit, on the user's ask ("running a proper frontend and security audit … make sure a user can only access what they are supposed to"): read-only reviewers, findings checked against the code. The key is safe (only `.env`; nothing in git or history). Fixed: D-122 (the VRM route, the persona recital, origins, llama-server's key, Vite's deny list), D-123 (every input's limit, refused sends, hidden upload errors, long words, IME), unused packages (`@pixiv/three-vrm-animation`, `three-mesh-bvh`, Rust `serde`; the animation notes moved out of `public/`, where they shipped in every build). UI-2 closed (D-124): `DESIGN.md`, the top bar, no text under 12 px.
8. The user's notes on the API path: a fallback model, Ask me or Answer by itself (D-125; the user chose both, default ask), the Stage now shows a failed reply, the cap message names the cap and the cost (Fable 5.2 was blocked by the $0.25 hourly cap: its worst case, thinking included, is about $0.30; nothing was spent); the picker lists the API models chosen in Settings, with popular sets and a checklist with Select all (D-126); a theme pick drops an old accent (`69ec49e`). Checked in a page-only preview only: the user's app held port 8780.
9. Before the push, on the user's ask: the picker sorts (company, A–Z, cheapest, priciest), filters by company and can show every model ("My list / All models"; search always does), kept in `localStorage`; the popular sets became family rules that take each family's newest model, so they follow new releases on any endpoint (D-127, `416d84c`).
10. The user's test round in the desktop app passed 1-4 and 9-14. Fixed from it and from a review the user asked for ("go through the bugs, hunt more and run /anthropic-frontend-design"; a workflow, six reviewers, three skeptics per finding, 34 of 37 upheld): D-128, `a4eadaf`. The one privacy bug: an auto fallback from a local model to an API model sent Task Guide / OCR remarks.

## 3. Where we stopped

Pushed up to `b741df7`. **Not pushed:** `a4eadaf` (D-128) and its docs commit. `npm run check` green (frontend 225, pytest 1479). The family rules in `provider_presets.POPULAR_FAMILIES` are Claude's choice of which lines count as Popular, Budget and Strongest: the user may want to change them, and a brand-new model line needs a rule. The VRM and WAV are backed up to `D:\AI\Kokyu-premade-backup`. Untracked and staying so: the packs' VRM and WAV, `.claude/`.

## 4. Next session: start here

1. `git status`, `git log -8 --oneline`, `npm run check`. Ask whether to push.
1b. Ask the user to re-run test items 5-8 in the desktop app (the Stage card, the set preview, typing in the chooser, Defaults and Clear), and to try Answer by itself with Ollama stopped (the card should name both models).
2. The user reads `docs/DESIGN.md` (D-124) and picks the next phase: K1b (installer) is next in order.
3. SEC-01 (D-057's token) needs a plan the user approves: it touches the shell, the kernel and the window.
4. Ask before any live API call with the new key: it spends money.

## 5. Traps

- **A test run of the app starts Ollama** and loads the chat model (D-105); quit through `/shutdown`, then check `tasklist` for `ollama.exe`.
- **Vite reloads itself when `vite.config.ts` changes**; a second Vite on the same port fails `strictPort` while the first keeps serving.
- **Kernel tests that send a message without Temp Chat reach the real Ollama** for memory recall (an embed). Turn Temp Chat on (`_temp_on`) in any new turn test.
- **Write and Edit refuse paths under `D:\AI\Kokyu.ai`** from this worktree session (a hook): write the file or an edit script in the scratchpad, then copy it in or run the script.
- **Live checks on scratch data:** `KOKYU_DATA_DIR=<scratch>/live` (with `config/config.yaml` copied in) before `npm run tauri dev` keeps test lines out of the user's threads; the kernel inherits it. Shut down with `POST /shutdown`, then stop the task, `kokyu.exe` and the node process on 1420.
- **The detector runs in every turn test:** conftest makes its embedder unreachable (patterns only). A test line that matches a pattern ("kill myself") gets no reply; a test that needs the meaning check patches `safety._embed_many`.
- **The Bash tool mangles `\\n` and some quotes in heredocs** (it rewrote `"\\n"` as a real newline twice this session). Write edit scripts with the Write tool into the scratchpad and run them; `edit.py` there asserts each replacement's count.
- **Computer use sees a blank screen on this PC** (even unlocked). To drive the real desktop window, start it with `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333 npm run tauri dev` and use the Chrome DevTools Protocol (page at `http://127.0.0.1:9333/json`): `Input.dispatchKeyEvent` and `Input.dispatchMouseEvent` act like the user; `Input.insertText` does not (it typed into the message box while Settings had focus); scroll an element into view before clicking it. `open_link` returns true or false, not an error.
- **`/shutdown` now deletes `logs/kernel.pid`:** a test calling `app.shutdown_endpoint` must set `KOKYU_DATA_DIR` to a temp folder, or it removes the real one.
- **The TrustedHost check allows `testserver`** for FastAPI's TestClient; a test that sets another Host gets 400.
- **A send that arrives while a turn is finishing** (turn_done sent, a companion switch still applying) waits in `Session.settled()`; a test that sends right after a mid-reply switch no longer needs to wait for anything, but a handler added with `if self.busy:` should use `settled()` instead.
- **`set_story` writes only when `through_message_id` is 0 or a message of that thread:** a test summary needs real message ids.
- **Fact decay reads `decayed_at`:** a test that backdates a fact must backdate `decayed_at` too.
- **A socket test waiting on a frame that never comes hangs the suite** (no pytest timeout): run suspects as `timeout 120 .venv/Scripts/python.exe -m pytest … -o faulthandler_timeout=30`.
- **A zustand selector must not build a new array or object**: it re-renders forever.
- **Bare class names collide** (`.waking`, `.warn`): `grep -n '^\\.name' src/app/*.css` first.
