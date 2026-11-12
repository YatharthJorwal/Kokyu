# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** It is the narrative: what happened, why, where we stopped, what to do first. It goes stale fast; if the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-11
- **Session:** 1 (inventory and doc corrections; no product code written)
- **Written by:** Claude, with the user (Yatharth)

## 1. The project in ten lines

1. Kōkyū is a Windows desktop chat app for a roster of AI waifus; KASANE (folder `KASANE/`) is its Python kernel.
2. Normal chatbot UI: sidebar (waifus on top, history, settings at the bottom), centered input, `＋` tray, heart animation, one model chip (Local / API sections, effort slider) and one waifu chip.
3. **A waifu is a voice and a persona only.** She never affects the model, intelligence or capabilities. Memory is shared by all waifus (user-confirmed).
4. Stage view (Ani-style), 2D desktop pets, 3D WASD mode with one or two waifus.
5. Voices are zero-shot GPT-SoVITS clips (about 8 s WAV plus transcript) sent on every request; no weight swapping.
6. Waifus are created only in the app; the prompt box is paste-only, fed by a generated instruction.
7. Agent mode and VR are deferred. Windows packaging is phase K7 but constrains design now.
8. Seeded from Yuri (successor of Luna). `docs/notes/yuri-inventory.md` is the map of what that means.
9. The TTS backend is built by a separate CLI agent from `docs/TTS-BACKEND.md` (Track T).
10. Work is delivered as a **git bundle** (D-030): commit in the sandbox, user merges and pushes.

## 2. How the user works

- Solo developer; casual tone; wants decisive proposals and direct commands (not manual file shuffling).
- Phases with gates; reviews the plan before code lands; approves gates explicitly.
- Cares about honesty: label verified vs not verified (the sandbox cannot run Rust, GPU, audio, Windows).
- Delivery: PowerShell merge of a bundle, then `git push`. Machine: Windows, local folder `Kokyu.ai`.
- Wants to commit to GitHub regularly.

## 3. What happened

### Session 0 (2026-11-11): scoping and docs
Scoped the product, wrote the full doc set and pushed it (`704c05d`). Decisions D-001 to D-023.

### Session 1 (2026-11-11): reading Yuri and Luna
- User confirmed shared memory ("memory should stay consistent"), the name Kōkyū, that `KASANE` stays uppercase locally (cannot be renamed), and asked me to pull the repo and start Phase 0.
- Cloned Kokyu, Yuri (`e32af4f`) and Luna (`2015462`). Ran Yuri's suites in the sandbox: **641 pytest, 65 frontend, tsc and vite build all pass** (Linux only; Rust not checked).
- Wrote `docs/notes/yuri-inventory.md` (K0-02). Biggest findings:
  - Yuri's backend is **flat modules on `sys.path`**, not a package, so the uppercase `KASANE/` folder is harmless (D-024).
  - The WebSocket protocol is untyped JSON, clause-level `speak` audio, **no token events, no threads, no waifu concept**.
  - The router is rule-based escalation (reflex pinned local, only `mind` may use cloud, nothing calls `mind`); **untrusted content blocks all cloud egress**, which conflicts with attaching files to a chosen API model (D-025). The local provider **ignores the model argument**.
  - Persona is a code constant (with emotion tags); TTS takes no voice argument and **silently falls back to pyttsx3**; memory has no speaker column.
  - The UI is a **stage-first 340×480 widget**, very close to the Stage view; the sidebar/Chat view do not exist. Rust already has Job Object, tray, F9 push-to-talk, a `toggle_click_through` command (useful for pets), parallel spawn of kernel and TTS.
  - Luna's `sandbox.ts` (1641 lines) is the seed for pets and 3D; Luna tracks a licensed VRMA pack.
- Corrected the docs against reality (ARCHITECTURE §2, 3, 4.1, 5, 7.1, 9.1, 11; SPEC FR-R-7, FR-MEM-5, FR-V-7, FR-ST-7; CLAUDE.md commands and repo map; README; TTS-BACKEND; RULES paths).
- Recorded decisions D-024 to D-031. **Rescoped K0** (D-026): threads, typed protocol, token streaming and model plumbing moved to K1.
- Delivered as a git bundle of docs-only commits on top of `704c05d`. **No product code was written** and nothing was copied from Yuri yet.

### Session 1 (continued): product direction
- The user supplied a product-vision handoff made with ChatGPT (kept verbatim in `docs/notes/product-vision-handoff-2026-11-11.md`) and asked me to weigh it. Result: `docs/PRODUCT.md`, decisions D-032 to D-039, TODO restructured, SPEC gains FR-COMP, FR-WIZ, FR-VP.
- Key points: the project is now a **paid one-time-purchase product** (direction), which makes the **license** an urgent decision (MIT code would be free to redistribute; hold code pushes until LIC-1). The handoff's per-companion model selection was **rejected** (D-003/D-038). Added: component manager, early installer skeleton (K1b), voice tiers with a built-in default, Credential Manager key storage, release train 1.0 / 1.1 / 2.x (pets and 3D after 1.0).
- Everything is docs-only and in one cumulative bundle (it contains the earlier session-1 commits; applying it alone is enough).

## 4. Where we stopped

K0-00 to K0-02 are done. **K0-03 (the seed commit) has not started.** The K0 plan is in `TODO.md` §K0 and is waiting for the user's approval, plus one product answer (Task Guide / OCR watch, D-029).

## 5. Next session: start here

1. `git log` and `git status`; confirm the session-1 bundle was merged and pushed. If not, remind the user (commands below). Also ask whether LIC-1 (the license) is decided: **no product code may be pushed to the public repo before it is** (D-032).
2. Ask for the user's approval of the K0 plan, the answer on parking Task Guide and OCR watch, and the output of this block (fills `STATE.md` §2):

```powershell
node -v; npm -v; rustc -V; cargo -V; python --version
ollama list
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv
```

3. Ask where the Luna and Yuri VRMs, reference clips and persona sources are (needed by `seed_waifus.py`; they must stay out of git), and where their existing GPT-SoVITS install lives (for the K0 voice gate).
4. Re-pull Yuri `main`; if it moved past `e32af4f`, ask whether to seed from the newer commit (D-028).
5. Do K0-03 (verbatim seed commit), then K0-04 onward in order, one reviewed step at a time, tests after each. **No bulk string replacement.**
6. Remind the user that Track T (TTS backend) can start in parallel with `docs/TTS-BACKEND.md`.

Merge routine for a bundle (PowerShell, in the repo folder):

```powershell
git pull --ff-only "C:\Users\User\Downloads\kokyu.bundle" main
git push
```

## 6. Open questions for the user

- Approve the K0 plan (`TODO.md` §K0)?
- **Keep or park Task Guide and OCR watch** (D-029 proposes park: code kept, disabled, hidden)?
- OK with D-025 (egress policy for user-selected API models)? Needed before K1, not K0.
- Track the licensed VRMA pack in git (Luna does, Yuri does not)? Needed at K4.
- Seed from `e32af4f` or a newer Yuri commit?
- **LIC-1:** which license path (keep MIT and sell convenience, source-available, or private source)? Needed before any code push.
- Approve the release boundaries (1.0 without pets and 3D) and the voice tiers (built-in default voice)?
- Where will the 2 to 3 premade companions (VRMs and voices with redistribution rights) come from?
- Has the Dodo Payments acceptable-use policy been checked against a companion product?

## 7. Traps and gotchas

- **Do not bulk-edit source with naive string replacement** (Yuri once replaced every "a" with "w" in five files). Targeted edits, tests after each.
- Tests stub `llm.<fn>` by module attribute and the router calls through the module; keep that pattern.
- `_send_speak` / `speech.prepare()` is the only text-to-audio path.
- VAD frames must be exactly 640 bytes (20 ms at 16 kHz).
- Port 1420 is shared by `dev:ui` and `tauri dev`; Yuri's kernel is on 8765, TTS on 9880 (hard-coded in Rust and Python until K0-04).
- Quit via the tray (graceful shutdown); killing the process loses memory consolidation.
- STT stays on CPU (CUDA DLL issue).
- Yuri's example config contains machine-specific paths: do not copy them into this public repo.
- Never commit VRMs, WAVs, weights, databases, `.env`, persona prompts under `data/`.
- The sandbox cannot verify Rust, windows, audio, GPU, Ollama or GPT-SoVITS; those are manual gates.

## 8. Deliberately not done

- No code, no copy of Yuri, no renames, no dependency changes in the repo.
- Yuri's `ROUTING.md`, `PHASES.md`, `phases/*` and the bodies of `memory/*`, `senses/*`, most of `src/*.ts` were not read in depth (do it when touching them).
- No decision on code signing, auto-update, multi-monitor pets.

## 9. Update checklist (end of every session)

- [ ] Date, session number, author updated
- [ ] §3 has a new entry for this session (what, why, results)
- [ ] §4 states exactly where work stopped (branch, file, step)
- [ ] §5 lists the first actions for next time, in order
- [ ] §6 holds only still-open questions
- [ ] §7 includes any new trap you hit
- [ ] §8 lists what you skipped and why
