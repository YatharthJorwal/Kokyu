# HANDOFF — Kōkyū

**Read this at the start of every session; rewrite it at the end.** Short by design (D-076): status is in `STATE.md`, the plan in `TODO.md`, decisions in `DECISIONS.md`. If the date is old, trust `git log` and ask the user.

- **Last updated:** 2026-11-17, session 5
- **Written by:** Claude, with the user (Yatharth)

## 1. How the user works

A solo developer who wants direct commands, no manual file shuffling, phases with checkpoints, and honesty about what was verified. They want a clean, fast, flexible codebase and an uncluttered tree. They watch the browser pane, send short UI notes mid-task, and often say "continue while I'm away" (that is autonomous mode: CLAUDE.md §2). They run other Claude sessions in parallel and test builds on their own PC. They push, or tell Claude to push. Kōkyū is primarily a **roleplay character app** to them (D-079).

## 2. What happened in session 5

1. **K1c, conversation modes** (`470a05e..2b99262`): Chat and Roleplay per thread, layered prompts, story memory, scenario cards, dialogue-only voice. Built on six assumed answers (D-074), reviewed adversarially, and fixed (D-075). The user then ran and tested the build on their PC and asked for the push (done: `8c204e7..7c16e95`).
2. **Review of all docs and the frontend** (the user asked "whats genuinely a trash idea"). Saved at `docs/archive/refinement-proposal-2026-11-17.md`. The user's answers became D-076 to D-085:
   - **Creator:** traits in, the model writes the persona, the user edits it (D-077).
   - **3D apartment:** stays planned for 1.1, from Luna's apartment code; two-companion turn-taking is to be designed later (D-078).
   - **Agent mode** is not planned and **VR** is deferred long term (D-079).
   - **Voice setup:** automatic at first run, with no separate agent (D-080).
   - **Distribution:** one per-user NSIS `.exe` (D-081).
   - **UI controls:** only working ones (D-082).
   - **Pricing:** unpriced models are allowed under the cap (D-083).
   - **Model names:** short names, with details muted on hover (D-084).
   - **Phase order:** proposed UI-1 → K1b → K2 → K3 → W (D-085, provisional).
3. **Docs reset** (D-076):
   - Rewrote SCOPE, PRODUCT, README, THIRD-PARTY, SPEC v1.1, ARCHITECTURE, CLAUDE.md, RULES, TODO, STATE and this file.
   - Compacted `DECISIONS.md` into an index; its full original text is in `docs/archive/decisions-log-2026-11-17.md`.
   - Archived the vision handoff, yuri-inventory, the modes plan and the TTS brief.
   - Replaced the three stacked manual gates with one checkpoint list (`STATE.md` §5).

4. **UI1-01 model names** (`883f4f7`, D-084, FR-M-12): the user said "Yes, start model names", which also starts the D-085 order. `router/names.py` names every model in the kernel (override, preset label, derivation; 26 cases from the proposal's table pass); the chip has a muted hover/focus card with the full id and facts; the picker has a muted strip for the hovered or highlighted row. Rows use the existing `detail` for the facts rather than a new `facts` field (SPEC FR-M-12 rewritten to match).

5. **UI1-02 only working controls** (`a412120`, `c575b72`, D-082): the mic, the "soon" attach items and New waifu are gone; no "kernel", "waifu" or phase codes in UI text. The sidebar status line became a banner shown after 6 s offline; its Reconnect calls a new shell command, `restart_kernel`, that starts the engine again only if it exited.
6. **The user's notes, recorded:** the design standard is its own phase UI-2, planned from real references before building (D-086); Luna and Yuri are paid content shipped complete inside the app, never exported or open-sourced, and users' own characters come from a step-by-step creator with their own assets (D-087); the audience was 16+ pending research (D-088).
7. **KASANE as a quiet credit** (`d765a4e`, D-089): the Doctor row "Engine (KASANE)", About, `logs/kasane.log`.
8. **Age research** (a side session, TODO B-9): the report is `docs/research-age-content-2026-11.md`. The user chose 18+ (`a9ab16d`, D-090, FR-WIZ-8); explicit premades and the payment provider stay open (TODO B-10..12).
9. **UI1-03 unpriced models** (`3e552e7`, D-083, FR-R-2): a model with no catalog price runs while a cap is on and is not counted against it. The picker shows "price unknown"; a notice comes once per model per run (an error frame with the non-ending code `price_unknown`, styled as info). A reached cap still stops it; helper roles stay local without a price. `budget.on_exhausted` is gone.
10. **Her face** (`04e0296`, D-091, FR-W-8): the user's answer to open question 6 was "just a vrm face", with a way to change it in her profile. Both VRMs carry a VRoid face shot as `meta.thumbnailImage`; the engine reads only that image, cuts a 512 px square and caches it in `data/portraits/cache`. `GET /waifus/<id>/portrait?v=` serves it; the roster carries a version stamp. Shown in the companion chip, the conversation list, her messages and the companion menu; her initial without one.
11. **Her profile** (`e62374f`, D-091, FR-W-9): About, traits, Chat (a new chat with her, no divider in the open one), Change picture and Use the model's face. Opens from Profile in the companion menu or her face beside a message. Packs gain `about`; Claude drafted Luna's and Yuri's in the untracked packs for the user to edit. `build_premade.py --force` used to delete `persona.md` too; it now keeps it and `about`.

## 3. Where we stopped

Everything is committed; pushed through `0a6cdb8`. `a9ab16d`, the UI1-03 commits, D-091 (`8ca5b1d`) and UI1-06 (`04e0296`, `e62374f`) wait for the user's word to push. Nothing is half-done. Untracked and staying so: `assets/premade/` (with the `persona.md` drafts), `.claude/`. `package-lock.json` has an unrelated change.

## 4. Next session: start here

1. `git status`, `git log -5 --oneline`, `npm run check`.
2. Ask the user to look in the desktop app: the model names (hover the chip, open the picker), Reconnect (end the engine's `python.exe` in Task Manager, wait for the banner, click Reconnect), and, if they have an unpriced endpoint, its "price unknown" row and notice.
3. Ask the user to read Luna's and Yuri's About drafts (`assets/premade/<id>/waifu.yaml`) and to try her profile in the desktop app: Chat, Change picture, Use the model's face.
4. Next item: **UI1-07**, the message list. Also open: question 3 (explicit premades, D-090).
5. Their `config/config.yaml` still has `on_exhausted`: harmless, can go.

**KASANE: decided, option B** (D-089): the Doctor row, About, `logs/kasane.log`; `kasane.exe` waits for packaging (K1b-02). The options were: It stands for *Kernel for Adaptive Synthetic Agents, Networks and Embodiments* (D-001); as a word, *kasane* (重ね) is the Heian court's layered robes, which suits both Kōkyū and an engine that layers persona, mode and voice.
- A. Internal only: folder, logs, code. The UI keeps "Kōkyū's engine" (today).
- B. A quiet credit (Claude's recommendation): the sidecar is `kasane.exe` (Task Manager shows something better than `python.exe`), the Doctor row reads "Engine (KASANE)", About shows "Engine: KASANE 1.0" with one line on the name, logs are `kasane.log`. Banners still say "Kōkyū's engine".
- C. A visible brand ("powered by KASANE", the banner naming it): a second name buyers must learn; not for 1.0.

## 5. Traps found this session

- The HMR-stamped module URL matters when injecting state in the browser pane (CLAUDE.md §7).
- The Workflow tool's script must be plain JS; an escaped `\\'` inside a single-quoted string fails to parse.
- Luna's apartment GLB is a Sketchfab download, gitignored there. A shipped room needs its own rights record (R-51).
- A `disabled` button gets no mouse events in Chrome, not even its parent's `mouseenter`; the picker's `<li>` is `display: contents` (subgrid) and has no box either. Rows that cannot be picked are `aria-disabled` with a guarded click.
- Chrome and React: a `disabled` button inside the picker's subgrid rows is unhoverable (above); the banner's grace timer depends on the online boolean, so connecting/offline flapping does not reset it.
- An injected `notice` needs every `Notice` field (`code`, `text`, `actions`); a missing `actions` blanks the page.
- The 1421 preview can stall at "starting" with nothing listening: stop it and start it again.
- The 1421 preview never connects to a kernel: `/ws` accepts only 1420 origins (403). Its failed reconnects still wipe injected state; inject with a `useChat.subscribe` that re-applies it. HTTP GETs (portraits) do reach a scratch kernel.
- A scratch kernel's `thread_new` loads the thread's model, which would touch the user's Ollama: live checks avoid it.
- Two `websocket_connect` contexts in one TestClient test break on `hub.shutdown_event`'s loop; fake the second window in `hub.connections` instead.
- The Windows console is cp1252: a Python script printing "Kōkyū" needs `PYTHONIOENCODING=utf-8`.
