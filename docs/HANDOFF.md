# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** It is the narrative: what happened, why, where we stopped, what to do first. It goes stale fast; if the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-11
- **Session:** 0 (planning and documentation; no code written)
- **Written by:** Claude, with the user (Yatharth)

## 1. The project in ten lines

1. Kōkyū is a Windows desktop chat app for a roster of AI waifus; KASANE is its Python kernel.
2. Looks like a normal chatbot: sidebar (waifus on top, history, settings at the bottom), centered input box, `＋` tray, heart animation, one model chip, one waifu chip.
3. **A waifu is a voice and a persona only.** She never affects the model, its intelligence or capabilities. Memory is shared by all waifus.
4. Stage view: her VRM stands in front of you, Ani-style. 2D desktop pets. 3D WASD mode with one or two waifus.
5. Voices are zero-shot GPT-SoVITS clips (about 8 s WAV + transcript) sent on every request; no weight swapping.
6. The model switcher is one control with Local and API sections; thinking effort is an animated slider.
7. Waifus are created only in the app; the system-prompt box is paste-only, fed by a generated instruction.
8. Agent mode and VR are deferred; the core app comes first.
9. Windows packaging comes later (installer, or portable bundle with setup instructions in the README) but constrains design now.
10. Seeded from Yuri (successor of Luna), which are the user's existing waifu projects.

## 2. How the user works (working agreements)

- Solo developer; casual tone; gets to the point. Likes decisive proposals with clear structure.
- Works in **phases with gates**. Review plans before big changes; approve gates explicitly.
- Cares about honesty: label what is verified and what is not.
- Wants to commit to GitHub regularly (the first commit is the doc set).
- Confirms or corrects assumptions in a numbered list: put open assumptions in lists the user can answer quickly.
- Delegates self-contained side jobs (the TTS backend) to a separate CLI agent: give those a standalone brief.

## 3. What happened

### Session 0 (2026-11-11): scoping and docs

- Read the READMEs of Luna and Yuri. The Kokyu repo was empty.
- Agreed the product: see §1 and `SCOPE.md`. Decisions are in `DECISIONS.md` D-001 to D-023.
- User decisions worth remembering:
  - Name **Kōkyū** (picked over Ōoku/Seraglio/Hanazono). Kernel stays **KASANE**.
  - One model switcher with a clear Local / API split (not a toggle), searchable, plus a **separate waifu switcher box**; effort is an animated **slider**.
  - Waifus switch only voice and persona; memory stays **consistent (shared)**.
  - TTS: zero-shot clips uploaded per waifu; the user dislikes their cluttered, Chinese-UI GPT-SoVITS folder, so a **CLI agent** will build a clean headless backend (Track T).
  - Creator: VRM upload, 8 s WAV, personality adjectives, paste-only system-prompt box with a generated instruction. (The user accepted that a **transcript** field is needed.)
  - Stage reference: Ani from xAI (bust-up, dark backdrop). "Plane" means the 3D space.
  - No VR headset; VR deferred. Agent mode deferred.
  - Hardware: RAM is DDR5-**4800**, so no RAM-speed concern for CPU-offloaded MoE.
- Assistant defaults the user has not explicitly confirmed (marked Provisional in `DECISIONS.md`): React + Zustand frontend (D-013), single pet overlay window (D-014), MIT license (D-015), `kasane/` naming and port 8780 (D-017), helper models hidden (D-018), model_ref scheme (D-019).
- Produced: `README.md`, `LICENSE`, `.gitignore`, `.env.example`, `CLAUDE.md` and `docs/` (SCOPE, SPEC, ARCHITECTURE, RULES, DECISIONS, TODO, STATE, HANDOFF, TTS-BACKEND).
- Nothing was run, built or committed. No code exists.

## 4. Where we stopped

The doc set is written and delivered to the user as files. The user has not yet reviewed it or committed it. K0 has **not** started.

## 5. Next session: start here

1. Ask whether the user reviewed the docs and whether DOC-1 produced corrections. Apply them (docs only) and update `DECISIONS.md` if any default changed.
2. Confirm the first commit exists (`git log`); if not, remind the user (DOC-2).
3. Run K0-00 (environment check) and report results; update `STATE.md` §2.
4. Do K0-02 **before** touching code: read Yuri's `docs/` and source; write `docs/notes/yuri-inventory.md`; fix `ARCHITECTURE.md` §5 where the real protocol differs. Present a short K0 plan and wait for approval.
5. Only then K0-03 onward.
6. In parallel, remind the user that Track T needs a separate CLI agent run with `docs/TTS-BACKEND.md`.

## 6. Open questions for the user

- Which Yuri commit to seed from (or latest `main`)?
- Where are the Luna and Yuri VRM files and reference voice clips (needed for K0-08)? They must stay out of git.
- Where should the new GPT-SoVITS backend folder live (outside the repo)?
- Do they want the MIT license, or another one, before the repo is shared?
- Which idle/sit/walk VRMA clips exist (K4), or should the baker use the procedural fallback only?

## 7. Traps and gotchas

- The Yuri and Luna READMEs were read; their **code and docs/ were not**. Do not assume names (events, modules, configs) in `ARCHITECTURE.md` match Yuri until K0-02 is done.
- The GPT-SoVITS API parameter list in `TTS-BACKEND.md` is from memory: verify against the installed version.
- Port clashes: Vite 1420 (tauri dev vs dev), Luna 8765; Kokyu uses 8780.
- Quit via the tray, not by killing, or memory consolidation is lost.
- STT on CPU (CUDA DLL problem inherited from Luna).
- YAML with Windows paths needs single quotes.
- Never commit VRMs, WAVs, weights, databases or `.env` (`.gitignore` is a net, not permission).

## 8. Deliberately not done

- No code, no repo scaffolding, no dependency installs.
- No `THIRD-PARTY.md` yet (K0-08).
- No decision on code signing, auto-update or multi-monitor pets.
- Agent mode and VR are designed on paper only.

## 9. Update checklist (end of every session)

- [ ] Date, session number, author updated
- [ ] §3 has a new entry for this session (what, why, results)
- [ ] §4 states exactly where work stopped (branch, file, step)
- [ ] §5 lists the first actions for next time, in order
- [ ] §6 holds only still-open questions
- [ ] §7 includes any new trap you hit
- [ ] §8 lists what you skipped and why
