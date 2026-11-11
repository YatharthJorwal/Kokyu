# DECISIONS — Kōkyū

Append-only decision log. Never edit an old entry: add a new one that supersedes it.

**Source** says who decided: **User** (explicit instruction in conversation) or **Default** (assistant proposal accepted as the working default; revisit freely).
**Status:** Accepted, Provisional (accepted but to be validated in a named phase), Superseded.

Template:

```
## D-0XX Title
Status · Source · Date
Context: ...
Decision: ...
Consequences: ...
```

---

## D-001 Name: Kōkyū, kernel: KASANE
Accepted · User · 2026-11-11
**Context:** A name was needed for the multi-waifu app; "Ōoku", "Seraglio", "Kōkyū" and "Hanazono" were proposed. KASANE (*Kernel for Adaptive Synthetic Agents, Networks and Embodiments*) was already the project codename.
**Decision:** The app is **Kōkyū** (ASCII `Kokyu` for paths and identifiers). The kernel is **KASANE**, Python package `kasane/`.
**Consequences:** Repo `YatharthJorwal/Kokyu`; app identifier `io.github.yatharthjorwal.kokyu` (D-021).

## D-002 Seed from Yuri by copy, not by git fork
Provisional · Default · 2026-11-11
**Context:** Yuri already has the role router, event bus, audio arbiter and VAD, memory v2, heart animation, tray shell and 600+ tests. Luna's `sandbox.html` is the seed for 3D scenes.
**Decision:** Kokyu starts from a **copy** of Yuri at a recorded commit (hash to be filled in at K0-03: `____`), renamed and reshaped. Git history starts fresh. Luna's sandbox is ported in K5. Luna and Yuri become the first two waifus.
**Consequences:** Yuri and Luna remain untouched (R-49). Their `docs/DECISIONS.md` must be read in K0-02 before porting.

## D-003 A waifu is a voice and a persona only
Accepted · User · 2026-11-11
**Context:** Waifus must not change model, intelligence or capabilities.
**Decision:** Waifu = prompt + TTS parameters + VRM + pet sprites. No `models`, `tools`, `permissions`, `memory` or `scene` keys in her pack.
**Consequences:** Invariance test (FR-W-3); R-01; creator never asks for capability settings.

## D-004 One model switcher with a Local / API split, plus an animated effort slider
Accepted · User · 2026-11-11
**Context:** Reference screenshot (a Codex-style harness): one chip, searchable grouped popover. The user wants a clear split between API and local models, not a toggle, and an effort *slider* with animation.
**Decision:** One chip in the input row; popover has search, **Local** and **API** sections; effort slider inside the popover, detents limited to model capability (FR-M-8..10). A separate **waifu switcher** chip sits beside it.
**Consequences:** Helper models are not user-facing (D-018). Capability registry required (`config/models.yaml`).

## D-005 Memory is shared across all waifus
Accepted · User · 2026-11-11
**Context:** The user wants memory to "stay consistent"; waifus only change voice and persona.
**Decision:** One app-level memory. Not namespaced by waifu. Messages and episode summaries name the speaking waifu so recall stays unambiguous (FR-MEM-2).
**Consequences:** Yuri's memory v2 is reused as is; R-02. Per-waifu private memory is a possible future option, not planned.

## D-006 Zero-shot voice per waifu, no weight swapping
Accepted · User · 2026-11-11
**Context:** Each waifu uploads her own voice clip; switching must be seamless. Swapping fine-tuned weights costs seconds.
**Decision:** One GPT-SoVITS base model for everyone; every request carries the speaking waifu's reference clip (about 8 s WAV), its exact transcript and language. Pre-warm on waifu select. Fine-tuned weights are out of v1.
**Consequences:** The creator auto-transcribes the clip (FR-CR-3) because the transcript is required on every call.

## D-007 TTS backend is delegated to a CLI agent and set up outside the repo
Accepted · User · 2026-11-11
**Context:** The user's GPT-SoVITS folder is cluttered and they dislike its Chinese-language WebUI.
**Decision:** A separate agent builds a **clean headless GPT-SoVITS API server** to the contract in `docs/TTS-BACKEND.md`. The repo contains only the adapter. No WebUI integration.
**Consequences:** Track T runs in parallel with K0 to K2; the smoke test is its gate; R-12.

## D-008 Waifu creation happens only in the app; the prompt box is paste-only
Accepted · User · 2026-11-11
**Context:** The user wants the app to ask for everything: VRM, 8 s WAV, personality adjectives, and a system prompt the user does not write by hand.
**Decision:** One in-app form (FR-CR). The app generates an **instruction** from name and traits; the user pastes it into any LLM and pastes the resulting system prompt into the box. Typing in the box is disabled. A transcript field was added because TTS needs it.
**Consequences:** Appendix A of `SPEC.md` is the canonical instruction template. No folder-drop import.

## D-009 Stage view is Ani-style
Accepted · User · 2026-11-11
**Decision:** Selecting a waifu shows her VRM in front of the user, bust-up on a dark backdrop, with lip-sync, eye contact and idle motion; Chat | Stage toggles the same thread. Sidebar waifu click opens Stage; history click opens Chat (FR-S-4).
**Consequences:** Auto-framing from bones, no hand-tuned camera constants (FR-ST-2).

## D-010 Desktop pets are 2D sprites baked from the VRM
Provisional · Default (user asked for 2D sitting/walking/idling) · 2026-11-11
**Context:** Live 3D pets cost GPU while an LLM and TTS are resident.
**Decision:** Bake orthographic transparent sprite atlases from the VRM through VRMA clips; play them as 2D animation.
**Consequences:** Needs idle/sit/walk VRMA clips or procedural fallback; baker lives in the engine (K4).

## D-011 3D mode uses WASD first-person; VR is deferred
Accepted · User · 2026-11-11
**Context:** The user does not own a headset.
**Decision:** v1 3D mode is WASD with pointer lock and 1 to 2 waifus. The renderer stays XR-compatible; no XR work until a headset exists.
**Consequences:** The K0.5 WebXR spike from earlier drafts is removed; VR is item D2.

## D-012 Agent mode is deferred until after the core app
Accepted · User · 2026-11-11
**Decision:** Agent mode (Codex/DeepSeek-style harness, file permissions) is designed (`SCOPE.md` §12) but not scheduled. No shell execution in its first version.
**Consequences:** `trust` flag and bus design keep it addable without rework (`ARCHITECTURE.md` §14).

## D-013 Frontend stack
Provisional · Default · 2026-11-11
**Decision:** Tauri 2, Vite, TypeScript (strict), `three` + `@pixiv/three-vrm`, **React** for UI chrome, **Zustand** for the client store, plain CSS with CSS variables (no heavy UI kit). The three.js engine is imperative and outside React state.
**Consequences:** Yuri's shell is vanilla TS; K1 introduces React around the existing engine code. Revisit at K1 start if it proves awkward.

## D-014 Pets render in one overlay window per monitor
Provisional · Default · 2026-11-11
**Context:** One WebView2 window per pet costs memory and moving OS windows every frame is jittery.
**Decision:** One transparent, undecorated, always-on-top overlay per monitor (primary only in v1) hosting all pets on a canvas, with alpha hit-testing for click-through. K4 begins with a spike; if it fails (fullscreen games, focus stealing), fall back to one window per pet.
**Consequences:** Supersedes the "window per pet" wording in `SCOPE.md` v0.2.

## D-015 License: MIT
Provisional · Default · 2026-11-11
**Context:** Public repository; the user asked for a license. Core dependencies are permissive.
**Decision:** MIT, copyright "Yatharth Jorwal". Assets (VRM, audio, weights) are excluded and keep their own licenses.
**Consequences:** R-37 to R-39. Revisit before the first public release if the user prefers another license.

## D-016 Living docs: HANDOFF and STATE
Accepted · User · 2026-11-11
**Decision:** `HANDOFF.md` is read at every session start and **thoroughly rewritten** at every session end; it is trusted only when fresh. `STATE.md` is the current state and recent issues, updated the same way. Both are listed in the session protocol (`CLAUDE.md` §2).
**Consequences:** R-28; stale living docs are a bug.

## D-017 Repository layout and naming
Provisional · Default · 2026-11-11
**Decision:** Python package `kasane/` (replaces Yuri's `orchestrator/`), frontend `src/`, Rust `src-tauri/`, config in `config/`, runtime data in `data/` (dev) or `%APPDATA%\Kokyu` (packaged), docs in `docs/`. Kernel port **8780**.
**Consequences:** 8780 avoids clashing with Luna's 8765.

## D-018 Helper models are not user-facing
Provisional · Default · 2026-11-11
**Decision:** Classifier, memory writer, embeddings and vision are configured in Settings → Advanced, always local (vision: local by default), never shown in the switcher.
**Consequences:** The user sees one chat model per thread.

## D-019 Model reference scheme and per-thread selection
Provisional · Default · 2026-11-11
**Decision:** `model_ref = <kind>:<backend>/<id>`; selection and effort are stored per thread; new threads inherit the last choice.

## D-020 No silent fallback for user-selected API models
Accepted · Default · 2026-11-11
**Context:** The reference screenshot shows an API failure ("Request quota exhausted") inline in a harness.
**Decision:** Failed API turns show the error with *Retry* and *Switch model*; the router never swaps models on its own for a user-selected model.

## D-021 App identifier and data location
Provisional · Default · 2026-11-11
**Decision:** Bundle identifier `io.github.yatharthjorwal.kokyu`; one `paths.py` resolves dev (`./data`) and packaged (`%APPDATA%\Kokyu`) locations.

## D-022 Windows distribution plan
Accepted (direction) · User · 2026-11-11
**Context:** "Later, this is to be packaged as a Windows app, or a software file with packages and setup instructions in the README."
**Decision:** Plan both: an NSIS installer via the Tauri bundler with the kernel as a sidecar, and a portable bundle with `setup.ps1` plus README instructions. Models and the TTS backend are not bundled. Implementation is phase K7; design constraints apply from K0 (RULES §9).

## D-023 Provisional engineering defaults
Provisional · Default · 2026-11-11
- Kernel deps: FastAPI, uvicorn, pydantic, httpx, PyYAML, sqlite-vec, faster-whisper, `nvidia-ml-py`, pytest.
- Dev tooling: add `ruff` for lint/format at K0 if Yuri has no equivalent.
- Chat uses Markdown rendering with a sanitizing renderer.
- Conventional Commits.
- Latency and VRAM numbers in the docs are **targets/estimates**, replaced by measurements as they exist.

---

## Session 1 entries (2026-11-11, after reading Yuri and Luna: `notes/yuri-inventory.md`)

## D-024 The kernel folder is `KASANE/` (uppercase), with Yuri's flat module layout
Accepted · User (the local folder stays `KASANE` and cannot be renamed) + Default (layout) · 2026-11-11
**Context:** D-017 assumed an importable Python package `kasane/`. Reading Yuri showed there is no package: `orchestrator/` is put on `sys.path` and modules import each other by top-level name (`import llm`, `from audio import tts`, `from router import ...`). The user's Windows folder is named `KASANE` and cannot be changed to lowercase.
**Decision:** Rename `orchestrator/` to **`KASANE/`** and keep the flat layout. No `import kasane` exists anywhere. Tests, scripts and docs say `KASANE\` / `KASANE/`.
**Consequences:** Supersedes the naming part of D-017 (`kasane/` package). Case does not matter for imports. Generic top-level module names (`memory`, `router`, `audio`, `config`) stay as in Yuri; turning the kernel into a real package is a separate refactor (R-50), not planned.

## D-025 Router front end and egress policy for a user-selected chat model
Provisional · Default · needs the user's OK before K1 · 2026-11-11
**Context:** Yuri's router is rule-based escalation: `reflex` is pinned local, `mind` is the only cloud-eligible role and nothing calls it; "untrusted context blocks cloud" (D-012) stops *all* cloud egress for any turn touching screen, file or web content; budget exhaustion and offline silently fall back to local. Kōkyū lets the user pick any model per thread.
**Decision:**
1. Add a `chat` role (K1) executed on the thread's `model_ref`; selecting an API model is the user's consent for that thread's text.
2. Local-only roles stay pinned local (rule 1 unchanged); secret-class content stays local.
3. **Ambient** untrusted content (camera, screen capture, OCR watch) still blocks cloud for that turn, shown as a visible message, never a silent reroute.
4. **User-attached** files and images may go to the chosen API model with a visible badge; they stay `trust=untrusted` for authorising actions.
5. Budget exhaustion, offline and API errors on a user-selected model produce an error with *Retry* / *Switch model* (D-020), not a fallback.
6. `shadow`/`enforce` mode (D-014) does not apply to `chat`: the user's selection is enforced.
**Consequences:** Edits `router/decision.py` rules 3 and 5 to 6 semantics for the `chat` role only, plus tests; FR-R-4, FR-R-5, FR-R-7 in `SPEC.md`.

## D-026 K0 is re-scoped: threads, typed protocol and model plumbing move to K1
Provisional · Default · 2026-11-11
**Context:** `ws_endpoint` is about 580 lines and owns a per-connection `history`; `_run_turn` is about 280 lines; there is no thread concept and no token events. Extracting a conversation manager is a large refactor that belongs with the UI that needs it.
**Decision:** K0 delivers only: seed and rename, paths module, config v3, waifu pack and registry, persona as data, shared prompt addendum, per-waifu TTS parameters, speaker-tagged memory, a waifu switch message and temporary dropdown, invariance tests, `npm run check`. The SQLite thread store, conversation manager, typed protocol, token streaming, `llm.py` model/effort parameters and the `chat` role move to K1.
**Consequences:** `TODO.md` K0 and K1 rewritten; the K0 gate no longer requires threads.

## D-027 Process ownership and ports
Provisional · Default · 2026-11-11
**Context:** Yuri's shell starts the orchestrator and GPT-SoVITS **in parallel** (its D-027, boot speed) and sets an environment variable so Python never launches TTS; ports 8765 and 9880 are hard-coded in Rust and Python.
**Decision:** Keep that model. Tauri owns both children through the Job Object; env var renamed `KOKYU_SHELL_STARTS_TTS`; kernel port **8780**; TTS port from config (default 9880); no hard-coded ports in Rust (read from `launcher.local.txt` or config). `llama-server` is spawned by the kernel on demand.
**Consequences:** Supersedes "kernel starts TTS lazily" in the first `ARCHITECTURE.md` draft (now corrected). Machine-specific paths stay in gitignored `launcher.local.txt`.

## D-028 Seed commit and provenance
Provisional · Default · 2026-11-11
**Decision:** Seed from Yuri `e32af4f710cdf4e8c141df667a18c53046557ea3` (`main` HEAD on 2026-11-11). Copy it **verbatim in its own commit** (K0-03) before any rename so the diff to Yuri is reviewable. Excluded: `.git`, Yuri's `docs/` and `README.md`, user assets, generated `src-tauri/gen/`, and Yuri's config examples containing machine paths (rewritten in K0-06). Lock files (`package-lock.json`, `Cargo.lock`) are kept.
**Consequences:** Fills in the blank in D-002.

## D-029 Inherited Yuri features not in the SPEC
Provisional · Default · awaiting the user's answer on the parked items · 2026-11-11
**Decision:** **Keep:** Temp Chat (FR-MEM-5), camera and screen look-intent as the `＋` tray camera/screenshot, emotion tags and expression life, `scene_state`. **Park:** Task Guide and OCR watch (ambient screen commentary): code kept, disabled by config, hidden in the v1 UI, no tests removed.
**Consequences:** Nothing is deleted in K0. If the user wants them in v1 they need SPEC entries first (R-31).

## D-030 Work is delivered as a git bundle
Accepted (carried from Luna's workflow) · Default · 2026-11-11
**Context:** Claude has no push access to the repository; each session starts in a fresh sandbox.
**Decision:** Claude clones the repo, commits with real messages, and hands over a `git bundle`; the user merges it and pushes. Claude re-pulls `origin/main` before starting. The sandbox cannot run Rust, a GPU, Windows, audio, Ollama or GPT-SoVITS, so anything depending on them stays an explicit **manual gate**.
**Consequences:** Commit history is preserved; `STATE.md` records what was verified where.

## D-031 Emotion tag and speech rules live in the app addendum
Provisional · Default · 2026-11-11
**Context:** In Yuri the emotion-tag convention and speech rules are entangled with the persona prompt. The creator's instruction template (SPEC Appendix A) tells the user's LLM only about personality and speech style.
**Decision:** The shared **app addendum** (identical for every waifu) carries the emotion-tag convention, speech rules and output cleanup. Waifu prompts contain personality only.
**Consequences:** K0-08 splits Yuri's `SYSTEM_PROMPT` when seeding; `ARCHITECTURE.md` §4.1.
