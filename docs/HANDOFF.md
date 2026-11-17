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

## 3. Where we stopped

The docs reset is pushed (`5e82558`). UI1-01 (`883f4f7`) and its docs commit are **local, not pushed**: the user had not said to push this one. Nothing is half-done. Untracked and staying so: `assets/premade/` (with the `persona.md` drafts), `.claude/`. `package-lock.json` has an unrelated change.

## 4. Next session: start here

1. `git status`, `git log -5 --oneline`, `npm run check`. Ask whether to push `883f4f7` and the docs commit.
2. Ask the user to look at the model names in the desktop app with their real list (hover the chip; open the picker).
3. Confirm D-085's phase order with the user. The user said they "have stuff planned" for the open questions in `STATE.md` §3; ask which they want to settle first.
4. Ask the user to tick what they already saw in the `STATE.md` §5 checkpoint.
5. Next item: **UI1-02**, only working controls and plain words (D-082).

## 5. Traps found this session

- The HMR-stamped module URL matters when injecting state in the browser pane (CLAUDE.md §7).
- The Workflow tool's script must be plain JS; an escaped `\\'` inside a single-quoted string fails to parse.
- Luna's apartment GLB is a Sketchfab download, gitignored there. A shipped room needs its own rights record (R-51).
- A `disabled` button gets no mouse events in Chrome, not even its parent's `mouseenter`; the picker's `<li>` is `display: contents` (subgrid) and has no box either. Rows that cannot be picked are `aria-disabled` with a guarded click.
- With a kernel running on 8780, the 1421 preview connects to it and its reconnects wipe injected store state; inject with a `useChat.subscribe` that re-applies it. Never pick a model there: it is the user's kernel.
