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

---

## Session 1, product direction (2026-11-11, after weighing the external vision handoff: `PRODUCT.md`)

## D-032 License is undecided; no code goes public until it is decided
Accepted (direction) · User (the license is expected to change) + Default (hold rule) · 2026-11-11
**Context:** D-015 chose MIT provisionally. The product is now intended to be sold for about $15 to $20 (D-033). MIT lets anyone legally build and redistribute the code for free. Only documentation is published so far.
**Decision:** The license is **undecided**. MIT covers only the documentation-only history already public. **No product code is pushed to the public repository until the license is decided** (TODO LIC-1). Options (A keep MIT and sell convenience, B source-available, C private source) are in `PRODUCT.md` §5. Not legal advice.
**Consequences:** Supersedes D-015's direction. K0-03 is on hold for pushes (work can continue in the sandbox and be bundled). README's license section updated; `LICENSE` is left untouched until the user decides.

## D-033 Commercial direction: paid, one-time purchase, BYOK and BYOM
Accepted (direction) · User · 2026-11-11
**Decision:** Kōkyū is a paid desktop app: one-time purchase, no mandatory subscription, no hosted inference, users bring their own models, keys and voice providers. Sold from an official website with Dodo Payments; installer preferred over the Microsoft Store. Price undecided ($14.99 launch and $19.99 standard were discussed).
**Consequences:** `PRODUCT.md`; Track B (business, non-code) in `TODO.md`; K7 grows (signing, updater, license key, diagnostics).

## D-034 Release boundaries and phase order
Provisional · Default · 2026-11-11
**Decision:** **1.0** = T, K0, K1, K1b, K2, K3, W, K6, K7. **1.1** = K4 (pets) and K5 (3D). **2.x** = D1 (agent mode) and D2 (VR). Execution order: T (parallel), K0, K1, K1b, K2, K3, W, K6, K7, then K4, K5.
**Consequences:** Pets and 3D rooms stay in scope but ship after the first stable release; waifu packs and shared memory remain foundational from K0.

## D-035 Component manager, Welcome wizard and an early installer
Provisional · Default · 2026-11-11
**Decision:** One **component** interface (`detect`, `install`, `start`, `stop`, `health`, `repair`) behind the Doctor panel and the first-run **Welcome wizard** (new phase W). A thin **walking-skeleton installer** (K1b) is built right after K1 so the Python sidecar, antivirus behaviour and clean-machine install are tested early. GPT-SoVITS is treated as an advanced, hardware-gated component, not a default.
**Consequences:** FR-COMP, FR-WIZ, ARCHITECTURE §15; Track T's brief now asks for a reproducible component manifest.

## D-036 Voice providers
Provisional · Default · 2026-11-11
**Decision:** A voice provider interface with three providers: `gpt_sovits` (reference clip plus transcript, local, advanced), `builtin` (small local voices, the default so the first conversation never waits; model chosen in a K2 spike) and `elevenlabs` (hosted voice ID plus key; cloud, opt-in, badged). The waifu's `voice` block names its provider; nothing else about her changes.
**Consequences:** D-006 stays true for the `gpt_sovits` provider. FR-VP, FR-V-1 reworded. Choosing a cloud voice is consent for that spoken text to leave the machine.

## D-037 Model providers and key storage
Provisional · Default · 2026-11-11
**Decision:** A generic **`openai_compat`** provider (configurable base URL and key) replaces the hard-wired AI Router; AI Router, OpenRouter, DeepSeek and others are presets. End-user keys live in the **Windows Credential Manager**, set through the app; `.env` and `secrets.local.yaml` are developer-only.
**Consequences:** Yuri's `airouter` provider is the starting point (K1). FR-M-4, FR-R-6 and R-33 updated.

## D-038 D-003 stands: a companion does not carry its own model
Accepted · User (D-003) · 2026-11-11
**Context:** The external handoff lists "AI model selection" and "companion-specific intelligence" inside companion creation.
**Decision:** Rejected. "Choose her intelligence" is delivered by the single global model switcher. Waifus remain voice and persona only.

## D-039 Premade companions are built-in, read-only packs with a rights record
Provisional · Default · 2026-11-11
**Decision:** The 2 to 3 included companions ship as read-only packs resolved through the resource resolver; users duplicate them to edit. Every shipped asset (VRM, voice, animation, scene, icon) has a rights record in `docs/THIRD-PARTY.md`. Luna's and Yuri's current assets are not shipped unless their provenance is confirmed. Premade personas are conservative by default.
**Consequences:** RULES R-51; `PRODUCT.md` §6.

---

## Session 2 entries (2026-11-12: license decided, spec finalized, Phase 0 started)

## D-040 License: proprietary, not open source
Accepted · User · 2026-11-12
**Context:** D-032 held code pushes until the license was decided. The user decided the project is not open source.
**Decision:** `LICENSE` is a proprietary "all rights reserved" notice. Commits up to and including `346f0c3` (documentation only) were published under MIT; that grant applies only to those versions. The repository should be **private** (user setting; recommended) because it will contain the premade companions' assets. This is a plain notice, not legal advice; have it reviewed before a commercial release.
**Consequences:** Supersedes D-032 and D-015. The hold on code pushes is lifted. RULES R-39 and the README license section updated; THIRD-PARTY.md still tracks dependency licenses (R-38).

## D-041 The premade companions are Luna and Yuri, with the user's own assets
Accepted · User · 2026-11-12
**Context:** The user made the VRMs themselves and generated the reference voices on the ElevenLabs website; both are AI-generated, not taken from anywhere. Transcripts live in `KASANE/voice_files/{Luna,Yuri}/transcript.txt`; the `.wav` and `.vrm` files are on the user's disk and were gitignored.
**Decision:** Luna and Yuri ship as the two default companions, as built-in read-only packs under `assets/premade/<id>/` (D-039). The `.gitignore` allows committed assets only under `assets/premade/`. A script (`scripts/build_premade.py`) assembles each pack from the user's files and the existing persona prompts.
**Consequences:** Supersedes D-039's "not shipped unless provenance is confirmed" for these two (provenance confirmed by the user). **To verify before any release:** the ElevenLabs plan used when generating the clips determines commercial-use rights and any voice-library restrictions; record it in `docs/THIRD-PARTY.md`.

## D-042 GPT-SoVITS install for development
Accepted · User · 2026-11-12
**Decision:** Development uses the existing install at `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (note the **space** in `GPT SoVITS`: paths must be quoted). Track T (a clean reproducible install) continues in parallel but no longer blocks the K0 voice gate.
**Consequences:** `launcher.local.txt` (gitignored) holds the path; code never hard-codes it.

## D-043 Commercial and release work is deferred
Accepted · User · 2026-11-12
**Decision:** Dodo Payments, the website, pricing, signing, licensing keys and release engineering come **after** the product is developed. Engineering continues to follow the portability rules so packaging stays possible.
**Consequences:** `TODO.md` Track B and K7 are marked deferred; K1b (the early installer test) stays until the user says otherwise.

## D-044 Spec finalized as the baseline
Accepted · User ("finalize the spec and proceed") · 2026-11-12
**Decision:** `SPEC.md` is the **v1.0 baseline** for K0 to K3. Entries marked Provisional in this log are promoted to Accepted, except those that exist to be validated by a spike, which stay open until it runs: D-014 (pets overlay, K4), D-035 (K1b), D-036 (built-in voice, K2) and the egress rule in D-025 (confirmed at K1 start). Changes after this point go through new decisions.
**Consequences:** D-029 Task Guide and OCR watch are parked (not deleted). Yuri's config examples were included verbatim in the seed commit so the inherited tests stay green, then rewritten in K0-06 (a refinement of D-028).

## Session 2 implementation entries (2026-11-12)

## D-045 K0 implementation choices
Accepted · Default · 2026-11-12
- **Premade prompts are copied verbatim; the shared addendum adds the emotion-tag rule.** This refines D-031: splitting Yuri's long prompt automatically is brittle, and the addendum ("end with exactly one tag; if your instructions already say this, follow them") works for premade and user-created waifus alike.
- **A waifu with no pack installed does not break the app:** the kernel runs the legacy built-in persona unchanged, so a fresh checkout still talks.
- **A switch requested during a turn is applied between turns** (FR-S-2) by checking at the top of the message loop; the client sees `pending` in `waifu_state` meanwhile.
- **Voice backend down means a caption-only reply** (empty audio, the caption shows for about reading time); the pyttsx3 placeholder voice is opt-in (`tts.fallback_engine: pyttsx3`), default off (FR-V-7).
- **The kernel remembers the last companion** in `data/active_waifu.txt`; `memory.db` now lives in `<repo>/data/` with the other databases (it used to sit inside the kernel folder).
- **Cargo package/binary and log file names are unchanged** (`yuri`, `orchestrator.log`): renaming needs `cargo` to regenerate `Cargo.lock`, so it waits for K7.
- Memory schema is now **v3** (nullable `speaker` on `transcript_log`, idempotent migration).

## D-046 The avatar is swapped by a page reload (temporary)
Provisional · Default · 2026-11-12
**Context:** The seeded stage code binds lip-sync, eyes, idle motion and expression life to one VRM inside one long init function; hot-swapping the model needs the K2 stage rework and cannot be verified without a browser.
**Decision:** When the kernel names an active waifu different from the one on screen, the page stores the id in `localStorage` and reloads once; the avatar loads from `GET /waifus/{id}/vrm`. The kernel is authoritative and the rule is loop-safe (`needsAvatarReload`).
**Consequences:** A brief flash on switch. K2-01 replaces this with a real avatar swap inside the Stage view.

## Session 3 entries (2026-11-14)

## D-047 D-025 egress rule confirmed
Accepted · User · 2026-11-14
**Decision:** The user approved D-025 as written: selecting an API model for a thread is consent for that thread's text and for files the user explicitly attaches; ambient captures (camera, screen capture, OCR watch, Task Guide screenshots) never reach a non-local model; API failure, offline and budget exhaustion show *Retry* / *Switch model*, never a silent fallback.
**Consequences:** D-025 is Accepted. K1-00c may proceed.

## D-048 Task Guide and OCR watch become v1 features ("screen companions")
Accepted · User ("make some slight spec changes and actually add them as a feature") · 2026-11-14
**Context:** D-029 proposed parking Yuri's Task Guide (tracks a task the user names and nudges when they drift) and OCR watch (rare ambient remarks about the screen). The user wants them in the product, and treats the feature list as growing while the phase plan stays.
**Decision:** Supersedes the "park" part of D-029. Both become **screen companions**, specified as FR-SC-1..6 in `SPEC.md` §2.17: opt-in, off by default, local models only (FR-R-7), a visible indicator while active, the active waifu delivers the remark in her own persona and voice (no waifu-dependent logic, FR-W-3), and each can be stopped with one action. K1 exposes the toggles in the `＋` tray and a status chip; K2 adds the voice delivery through the arbiter.
**Consequences:** `SPEC.md` gains §2.17 and the K1/K2 rows of the acceptance matrix; `TODO.md` gains K1-05b. The feature list may keep growing through new decisions; the phase order does not change.

## D-049 Protocol v1 lives beside Yuri's flat messages until the widget is replaced
Accepted · Default · 2026-11-14
**Context:** ARCHITECTURE §5.3 asks for versioned frames `{v, type, id, thread, data}`. The current widget (`src/ws-client.ts`) speaks Yuri's flat messages (`user_text`, `speak`, `turn_end`, ...); rewriting it now would be thrown away when the K1 React shell replaces it (K1-02).
**Decision:** Every message added from K1 on is a v1 frame, validated by pydantic in `KASANE/protocol/` (mirrored in `src/net/protocol.ts`, a test keeps the type lists equal). A frame with the wrong `v` gets `error {code:"protocol_version"}`; an invalid one gets `bad_message`. Messages without `v` are the legacy set and are handled exactly as before. Replies stream as `turn_start`, `token` (raw model text) and `turn_done` (the reply without the emotion tag, and whether Stop cut it); clients hide a trailing or half-written `[tag]` with `stripTrailingTag`. The legacy `speak`/`turn_end` messages are still sent, so voice and the widget keep working.
**Consequences:** K1-02 moves the client onto v1 and the flat messages are retired one by one (each with a decision when removed). Tokens are sent per model chunk; batching is a K6 tuning item if it ever shows up in profiles.

## D-050 K1-00c implementation of D-025
Accepted · Default · 2026-11-14
- **The conversation runs as the `chat` role** (new default role, `local_only: false`, chain `[airouter, local_ollama]` = the providers a user may pick). `decide_chat` in `router/decision.py` executes the thread's `model_ref` or returns a **blocked** decision; the router raises `RouteBlockedError` (audited, no provider called). There is no fallback chain for `chat`, and shadow/enforce and the old API toggle do not apply to it.
- **No selection = the local default model**, so a fresh install and every existing call keep working.
- **Ambient = a camera/screen capture taken this turn** (`look_intent`). Task Guide and OCR watch already run on local-only roles.
- **Images are still treated as secret** by the router (Yuri's rule), so an attached image blocks an API model with a plain message until K2-07 implements the attachment path and its badge (D-025 rule 4).
- **Effort:** `off|low|medium|high`. Ollama gets `think` (off = false, otherwise true; nothing when unset); OpenAI-style providers get `reasoning_effort` for low/medium/high. The calibrated, per-model effort UI is K1-11.
- **Failures show, never swap:** a blocked selection sends `error {code:"model_blocked", reason, message, actions:["retry","switch_model"]}`; a provider error sends `model_failed`. The spoken/captioned line is the plain message, not a persona line.
- **llama.cpp and generic OpenAI-compatible refs** are rejected as unsupported until K1-01 / K1-08b.

## D-051 llama.cpp backend for large local models (K1-01)
Accepted · Default (the user asked for "a better model": the 35B MoE on llama.cpp) · 2026-11-14
**Context:** SPEC lists `local:llamacpp/<preset>` refs and a Qwen 35B-A3B MoE on llama.cpp. The user's file is **Qwen3.6**-35B-A3B (unsloth `UD-Q4_K_XL`, about 21 GB), not the 3.5 named in older docs. The RTX 3060 has 12 GB, so the model only fits with expert weights in system RAM.
**Decision:**
- **Server:** the kernel runs one `llama-server` child per preset (`router/providers/llamacpp.py`), started on first use, restarted when another preset is chosen, stopped at kernel shutdown. It listens on 127.0.0.1 only. The binary comes from `llamacpp.server_path`, else `llama-server` on PATH, else the copy bundled inside Ollama (development convenience; it needs its `cuda_v12` folder on PATH and `GGML_BACKEND_PATH`). Downloading a pinned llama.cpp release stays W-03.
- **Presets** live in `config.yaml` under `llamacpp.presets` (id, model_path, n_cpu_moe, gpu_layers, ctx, threads, flash_attn, extra_args) until `models.yaml` arrives with K1-07; the ref is `local:llamacpp/<preset id>`. `chat.default_model_ref` makes it the model for threads without their own selection.
- **Measured settings for this PC:** `--n-cpu-moe 40` (every expert on the CPU) and `--threads 10`. Fewer experts on the CPU used more VRAM without a clear speed gain; 10 threads generated about 23 tok/s against 7 to 21 with 6. Numbers in `STATE.md`.
- **VRAM coexistence:** at about 3 GB the MoE is not a "large" resident in the VRAM sense, so the small Ollama helpers (classifier, embeddings) may run beside it. Starting `llama-server` unloads every Ollama model once (`keep_alive: 0`); helpers reload on demand. The real VRAM manager is still K1 work (ARCHITECTURE §7.3).
- **Prompt cache:** with experts on the CPU, reading the prompt is the slow part (about 34 tok/s cold). Per-turn system notes (recall, hints, scene) are moved into the next user message instead of being folded into the system prompt, so the prompt prefix stays byte-identical across turns and llama-server re-reads only the new tokens (measured: the second turn re-read 23 tokens and answered in 0.8 s).
- **Thinking:** effort maps to `chat_template_kwargs.enable_thinking` (off = false, else true; unset follows `llm.think`).
- **Safety:** a server already answering on the port when we start one is refused with a plain message (usually a leftover from a killed kernel), never silently used.
**Consequences:** The first message after start waits for the load and the cold prompt read (74 and 111 s in two runs); K1-01b warms the default model at kernel start. The 21 GB file is memory-mapped (about 19.5 GB working set, 4.6 GB private), so the other apps on the PC share about 12 GB of RAM while it runs.

## D-052 Warm the chat model at boot; helper roles get the model the router chose (K1-01b)
Accepted · Default · 2026-11-14
**Context:** With the 35B as the default (D-051), a live kernel run showed the first message after boot waiting 50 s even though the 35B itself answered from its cache in 3 s. Ollama's log showed why: the classifier call, audited as `qwen3.5:4b`, actually loaded `qwen3.5:9b` (26 s), then the embedding model cold-loaded (22 s). `OllamaNativeProvider` ignored the model the router chose for every role (an inherited Yuri gap, listed in ARCHITECTURE §7.4), so all local helpers ran on `llm.model` while the audit log named another model. Measured on the 3060: 9B + 4B + embeddings occupy 11.9 of 12.3 GB, which leaves no room for TTS.
**Decision:**
- **The provider always passes the router's model.** The audit log is now true. Test stubs of `llm.stream_reply` accept keyword arguments.
- **Helper models default to "same as reflex"** (`models.local.classifier` / `memory_writer: null`, now meaningful like `vision: null`), so a 9B-only install keeps one model in VRAM, exactly what Yuri really did. A setup whose chat model lives elsewhere (llama.cpp) sets them to a small model; the user's `config.yaml` uses `qwen3.5:4b`.
- **Starting `llama-server` keeps the helpers loaded** (classifier, memory writer, embedding models from the config) and unloads only the rest of Ollama.
- **Boot warm-up follows `chat.default_model_ref`** (FR-V-8 targets a warm first token): a llama.cpp default is started and reads the active waifu's system prompt and the tool list once (one-token `chat` call through the router), then the classifier and embedding models are loaded; an Ollama default loads that model (not always `llm.model`); an API default loads nothing. It runs in the background; the kernel serves meanwhile, and a failure is logged and shows up again, with Retry, on the first message. The waifu is only used to pick the prompt (FR-W-3).
- **Tray Quit (`/shutdown`) stops `llama-server` itself**, because `os._exit` skips the lifespan teardown; the Tauri Job Object stays the backstop.
**Consequences:** Measured on the PC: warm-up about 110 s after boot (35B) plus 27 s (4B); then the first message's first token in 1.7 s, VRAM 8.4 GB. A "loading model" status in the UI belongs to the model chip (K1-10); until then the kernel log says when the model is ready.

## D-053 K1-02 shell: React chat window now, widget page until K2
Accepted · User ("Chat now, avatar in K2") · 2026-11-14
**Context:** D-013 (React + Zustand) was provisional until K1 start. K1-02 replaces Yuri's widget as the main window.
**Decision:**
- D-013 confirmed: React 19, Zustand 5, `@vitejs/plugin-react` 4, plain CSS variables.
- `index.html` is the React chat window (`src/app/`); Yuri's widget moved unchanged to `widget.html` (Vite builds both pages) until the Stage view replaces it in K2. Only one of them should be open at a time (the second connection becomes an observer).
- All behaviour is a **pure reducer** (`src/app/chat-state.ts`) over v1 frames, Yuri's legacy messages and local events, tested in Node; `store.ts` wraps it in Zustand with the few actions that use the socket (`src/net/kernel.ts`). Components only render.
- Until v1 equivalents exist, the window still *sends* Yuri's flat `user_text` and `stop`, and plays the legacy `speak` clips (no lip-sync without an avatar). The user's line appears at once and is confirmed by `turn_start`; Retry drops the failed line and resends it.
- The **dev** CSP allows inline scripts because the React plugin injects its fast-refresh preamble inline; the production CSP stays `script-src 'self'` (the built page has no inline script). A test guards both.
**Consequences:** K1-03/04/05 extend this shell (sidebar groups and search, Markdown and Regenerate, the `＋` tray and heart). A kernel-side retry/regenerate (no duplicate user line in history) belongs to K1-04.

## D-054 Model picker: background loading with a "waking up" status, last pick wins (K1-07, K1-10)
Accepted, except the `models.yaml` bullet, which is **Proposed** (awaiting the user) · User asked ("bring the model selector down as documented and add options to select other models"; a creative loading line "like your waifu is waking up") · 2026-11-14
**Context:** The 35B on llama.cpp takes about two minutes to load (D-051, D-052), the boot warm-up always loaded the configured default, and the only model indicator was a read-only chip in the header. FR-M-1..7 put one model chip in the input row with a popover; FR-M-6 wants progress while a model loads.
**Decision:**
- **The chip lives in the input row** (FR-M-1) with a local/cloud icon, the model's label and the effort label; the header chip is gone. Its popover has a search box, Local and API sections as one list, a check mark on the current model, keyboard navigation, a refresh button for the API catalog and the spend footer (today and this month against the caps, FR-M-7). Picking a row is the whole action (FR-M-2). Rows that cannot be used (no API key, missing model file) are listed greyed with the reason.
- **Discovery (K1-07 part):** Local = the llama.cpp presets (with file size) plus Ollama's `/api/tags` minus embedding models (name contains "embed", or a BERT-family model, or the configured embedding model). API = the router's cached catalog; offline it is the cache, marked "cached". A source that cannot be read leaves its section empty with the reason. *Fits / won't fit* stays empty until the VRAM manager (K1-09).
- **Presets stay in `config.yaml` (`llamacpp.presets`, D-051), not a new `config/models.yaml`** as FR-M-3 says: they hold machine paths, and one file to edit is simpler. The per-model effort data FR-M-10 wants from `models.yaml` comes with the effort slider (K1-11). (**Proposed** spec deviation: the user has not approved it yet; K1-07's capability registry stays open until they do.)
- **One background loader** (`KASANE/model_loader.py`) owns "which chat model is loaded". It runs at boot (the **last thread's model**, else `chat.default_model_ref`: FR-M-5's "new threads inherit the last selection" also decides what boot loads, so a user who moved to the 9B no longer waits for the 35B), on a pick (`set_model`, at once), on opening a thread with another model (after `chat.load_delay_s`, default 1.5 s, so clicking through old threads does not start a load per click), and on *Try again* (`model_load`). One load at a time; a newer request cancels the older one. API models are "ready" at once.
- **Per backend:** llama.cpp starts `llama-server` and reads the persona once (D-052), which unloads Ollama's chat model and keeps the helpers; an Ollama pick **stops `llama-server` first** (FR-M-6, one large local model at a time) and loads the model through `llm.load_model`, which now raises instead of swallowing errors. A cancelled llama.cpp load leaves the half-loaded server running; asking for the same preset again waits for it instead of starting a second load.
- **Status to every window:** v1 `model_status` frames (`idle | loading | ready | failed`, label, message, seconds so far), sent on connect and on every change. The chat shows a **"waking up" card** with rotating lines in the app's voice ("Yuri is waking up…", "Rubbing the sleep out of Yuri's eyes…", "Yuri is swapping brains. Hold still…" when another model was up; after a minute "Big brains take a minute…"), the model's label and a timer; "Your waifu" stands in when no companion is installed. A failed load says "Yuri couldn't wake up." with the reason, **Try again** and **Switch model** (no silent fallback). A reply from the model clears a stale failure.
- **Switching models waits for the reply:** `set_model` during a running turn is refused with `turn_running` (loading another model would pull the answering one away); the chip is disabled while a reply streams.
- New protocol types: client `model_list` (`refresh`), `model_load`; server `model_list`, `model_status`; `hello` now carries `default_model_ref` and `default_effort`, so the chip shows what a thread without its own pick really runs.
- **Only the driver window loads** (review finding): an observer opening a thread or pressing Try again must not swap the model under the driver's streaming reply. Observers still get every `model_status`; their Try again and Switch model buttons are hidden.
- **Spend footer** shows the hour as well as today and the month (the hourly cap usually blocks first); caps are shown only when the budget is on. A failed catalog refresh keeps the cached list but marks it "cached" and says why.
- **Helper models stay in the list** when they can chat (R-03/D-018 hide helper *roles*, not models): with the default config the classifier and memory writer are the chat model itself, so hiding them would hide the default. Embedding models are hidden because they cannot chat.
- **Preloading is not a routed call:** the Ollama load calls `llm.load_model` directly, like the boot warm-up (D-052) and the helper warm-ups. There is no prompt, cost or answer to audit; the turn itself still goes through `router.decide()`.
**Consequences:** Measured live on the PC (scratch data dir, real config): boot loaded the 35B with the card counting up, ready after 109 s; picking qwen3.5:9b stopped `llama-server` (port 8080 freed), kept the 4B and embeddings loaded, showed "swapping brains", ready after 54 s (cold disk read), and answered within a few seconds. The waifu is only used for the name in the lines (FR-W-3 unaffected). Not verified: the Tauri window, the failure card against a real failure (unit-tested only), an API model (no key on this PC).

## D-055 Replies render Markdown with an in-house parser; Regenerate and Retry run in the kernel (K1-04)
Accepted · Implements FR-C-8, FR-C-9 (no spec deviation) · 2026-11-14
**Context:** FR-C-8 wants Markdown with code-block copy buttons, rendered "with a sanitizing renderer". No Markdown library is installed, and adding one means a download. The K1-02 Retry resent the failed line, so the thread stored that line twice (D-053 left a kernel-side retry to K1-04).
**Decision:**
- `src/app/markdown.ts` parses paragraphs, line breaks, headings, bullet and numbered lists, block quotes, rules, fenced code (an unclosed fence while streaming is code so far), inline code, bold, italics and links; `ui/Markdown.tsx` builds React elements from that tree. Model output never becomes HTML, so there is nothing to sanitize. Only `http(s)` and `mailto` links are links; they open in a new window. No tables, nested lists or images (marked as a `shortcut:`).
- Replies get *Copy* (the Markdown source) and the last reply *Regenerate*; code blocks get *Copy*. The user's own lines stay plain text.
- New client frame `regenerate`. The kernel takes the thread's last exchange back out (`ConversationManager.pop_last_exchange`: the line and its reply, or a failed turn's lone line), drops it from the in-memory history when it is still there, and runs the turn again. Retry after a failure uses the same path, so nothing is stored twice. Driver only; refused mid-reply (`turn_running`) and when the thread does not end in an exchange (`bad_message`).
**Consequences:** Verified live: Markdown sample rendered with `<b>` left as text, a real Regenerate replaced the reply and kept one user line in the store. **Open, for the user:** the persona prompt (from Yuri's voice-only design, `KASANE/persona.py`) tells the model "No markdown … no code blocks", so the model rarely writes any; FR-C-8 assumes it may, with speech getting the cleaned version (FR-V-2, `audio/speech.py` already strips it). Relaxing that one rule is the user's call. FR-C-10 token counts are not recorded yet (the stream does not pass usage up); speaker, model, effort and timestamps are.

## D-056 Screen companions in K1: tray switches, chips, a vision check, and a typing signal (K1-05b)
Accepted · Implements FR-SC-1..5 per D-048 · 2026-11-14
- **Task Guide is off at launch and gated as a whole.** Yuri ran the task classifier on every message, so a task could start without the user asking. Now the classifier and the `set_active_task` tool do nothing until the user turns Task Guide on; turning it off ends the task. A side effect: one classifier call less per message while it is off.
- **Starting it:** the `＋` tray's "Task Guide…" asks "What are you working on?" and starts tracking that task; picking it again replaces the task; while it is on, a task stated in chat is still picked up by the classifier. "OCR watch" is an on/off item. One v1 frame, `screen_companion {mode, on, task?}`, from the driver window only (observers are ignored, as with `model_load`).
- **Refusal (FR-SC-3):** turning either on first asks Ollama whether the vision model (`llm.vision_model`, else the chat model) reports `vision`; if not, or Ollama does not answer, the kernel sends `error {code: vision_unavailable}` with a plain message and the mode stays off. The `vision` role was already `local_only`.
- **Indicator (FR-SC-2):** every window gets `screen_companions {task_guide: {on, task}, ocr_watch: {on}}` on connect and on every change (tray, chip, classifier, idle timeout); the composer shows a chip per active mode with a × that stops it.
- **Typing (FR-SC-5):** the chat window sends `typing` at most every 4 s while keys go down; OCR watch skips its check for 10 s after the last one.
- **Not yet:** turning them on at launch from Settings (FR-SC-1's Settings half) lands with K1-13; spoken delivery through the arbiter and remarks in the thread are K2 (FR-SC-6).

## D-057 Closing two egress gaps and the open kernel socket (review findings)
Accepted · Implements FR-R-7, FR-SC-3, D-047 (no spec deviation) · 2026-11-14
**Context:** Two reviews found ways ambient content reached an API model without the AMBIENT_CONTEXT block: (1) the chat model is offered `capture_screen`, `capture_camera` and `read_clipboard`, and an API model that called one got the local description back in the next round; (2) Task Guide and OCR watch remarks are written from screen captures and stay in the in-memory history, so the next turn on an API model sent them along. D-050 had narrowed "ambient" to a capture taken this turn and missed both paths. Separately, the kernel's websocket accepted any Origin (CORS covers HTTP only), so any web page the user had open could connect, read every thread and the transcript log, or take the driver role.
**Decision:**
- **Local-only tools:** on a turn whose model is not local, the screen, camera and clipboard tools are not offered at all (`tools.offered_schemas(local_model=False)`). The clipboard joins them because the user never handed its content over. An explicit "look at my screen" still goes through look_intent and gets the visible AMBIENT_CONTEXT refusal. An unreadable model ref counts as not local.
- **Remarks stay local:** `_run_turn` leaves the unprompted remarks (tracked by identity in `unprompted_msgs`) out of an API model's messages. They remain in a local model's context. Her replies to a "look" turn stay in the thread: they are thread text, which choosing an API model consents to send (FR-R-4).
- **Socket origin:** the websocket refuses a handshake whose Origin is not one of Kokyu's pages (Vite on :1420, the Tauri webview); a missing Origin (tests, local programs) is allowed, since only browsers send one. Same list as the CORS middleware (`ALLOWED_ORIGINS`).
- **Tests use a throwaway data dir:** an autouse fixture sets `KOKYU_DATA_DIR` to a temp folder and rebuilds the router singleton, so the suite no longer appends to the developer's `logs/audit.jsonl` (a run added about 250 rows before).
**Consequences:** On an API model she cannot look or read the clipboard unless the user asks in words look_intent catches, which then shows the refusal. A per-launch token for the socket (stronger than Origin) is left for packaging (K7).

## D-058 What the AI Router bills, blocks and logs (K1-08 audit)
Accepted, pending the user's review · Implements FR-R-2, FR-R-5, FR-R-6, FR-M-4 · 2026-11-14
**Context:** An audit of K1-08 found the spend ledger missed most calls that did not end normally: a tool round (app.py stops reading at the tool call, before the usage frame), Stop, a failure mid-reply, and any reply whose provider sent no usage. Each was recorded as $0 or not at all. The cap read a snapshot that never refreshed, so once it blocked it stayed blocked until a restart. Calls started together all passed it. Chat calls went out with no `max_tokens`, so the worst-case estimate was not a bound. A model with no catalog price was never capped. Provider error text (which can echo the key) reached the audit log, the kernel log and the chat unredacted.
**Decision:**
- **Every AI Router call that may have been billed gets a ledger row**, $0 included. Reported usage is used when there is some. Otherwise it is an estimate flagged `estimated`: prompt from the router's estimate; reply from generated characters / 4, thinking and tool arguments included. A call cut short (Stop, failure, or the caller putting the stream down mid-reply) with no reported count is billed at its whole reply cap: thinking the client never saw is billed, and many providers keep generating after a hang-up. A call refused or unreachable before HTTP 200 gets no row. Any failure after 200 (`StreamFailed`) gets one, even with no chunk shown, because a reasoning model can think for minutes and then drop.
- **The cap reads the ledger before each call** (off the event loop) and counts the worst case of calls still in flight (a reservation taken with no await after the decision). A tool round is booked and its reservation freed at the tool call, before the caller routes the next round: the stream itself is only finalized later.
- **An API call is sent with the reply cap its estimate assumes:** the role's `max_tokens` (chat: 1200), else `llm.max_tokens`. A model that may think (an effort is set, or the catalog tags it `reasoning`/`thinking`) gets the role's `reasoning_tokens` on top (chat and mind: 6000). Thinking is billed as output and counts against the cap. Local calls are unchanged.
- **A cap spent before any answer is an error, not an empty turn:** finish `length` with nothing said and no tool call raises `StreamFailed`, with a message naming the cap. llama.cpp is exempt: its one-token warm-up ends exactly that way.
- **A model with no catalog price is refused while any cap is on** (`PRICE_UNKNOWN`, with its own message), because the cap cannot be kept on a cost nobody knows. A price of 0 is a price. With every cap unlimited, it runs.
- **Errors are cleaned where they are made:** the provider swaps its own key for `[secret]` and runs the redaction rules over the error text; the audit redacts `error` again as a backstop.
- **The audit records calls, it does not gate them:** a failed audit or ledger write is logged and the call goes ahead. The audit says `cancelled` for Stop, `closed early` for a stream put down mid-reply, and names unexpected exceptions. A caller putting the stream down after a tool call (or the end) is not an error.
- **A stream that fails inside HTTP 200** (an error event, `finish_reason: error`, a JSON error body, a cut-off or empty stream) raises ProviderError (`StreamFailed` once frames came), so the turn shows Retry and Switch model. Only a refused or unreachable provider gets the 60-second offline back-off; one that answered and then failed does not, so Retry (or a lower effort) goes straight through. Usage the provider reported before or after the failure is handed over first, so the bill uses it. Error text is redacted whole, then cut, so a key across the cut cannot slip out.
- **Catalog:** a refresh also re-checks whether the cloud is usable, without reloading the cache over the fresh list or fetching again (startup, too, reads the cache only into an empty catalog, and runs once); API rows carry their vendor as `group` (shown as sub-headings) and the label without it; AI Router's `tool-use` tag gets the tools badge; a cache that cannot be written is logged, not reported as a failed refresh.
**Consequences:** The ledger over-counts rather than under-counts. A stopped call with no reported usage is booked at its whole cap, and estimates round up and assume the whole prompt was read. The cap is a ceiling, so the spending cap still holds. An API chat reply is capped at 1200 tokens, or 7200 when the model may think. Blocking unpriced models is the conservative reading of FR-R-2 and **awaits the user's choice**: block, or run the model and flag the row.

## D-059 One API endpoint at a time; keys in the Windows Credential Manager through the shell (K1-08b)
Accepted · User (one endpoint at a time) · Implements FR-R-6, D-037; deviates from FR-M-4 · 2026-11-15
**Context:** FR-M-4 lists the models of every configured endpoint at once, grouped by provider. The router has one API slot (D-058 was built on it). Asked which to build, the user chose "One at a time": pick a preset or a custom URL, with its key.
**Decision:**
- **One active endpoint.** Presets: `airouter` (AI Router), `openrouter` (OpenRouter), `deepseek` (DeepSeek); `custom` takes `base_url` from config. The config slot keeps its name, `providers.airouter`, so existing `config.yaml` files and role chains keep working; its new `preset` key picks the developer default. A preset knows its base URL, models URL, price unit (USD per 1M, per token, or none), cache file and developer key variable.
- **The active endpoint is the provider of the key saved in the app.** The app saves at most one key; saving another provider's key replaces it. With no app key, the config `preset` and its developer key (environment, `secrets.local.yaml` section, `.env`) apply. Packaged builds use app keys only (FR-R-6).
- **Model refs name the endpoint:** `api:<id>/<model>`. Old threads (`api:airouter/…`) keep working. A thread whose endpoint is not the active one is blocked with its own message (`OTHER_PROVIDER`), never sent to another provider (D-025, FR-R-5).
- **Keys at rest:** Windows Credential Manager, generic credential `Kokyu/api-key/<id>`, this user on this PC. Two Tauri commands write and remove a key (main window only); none reads one back.
- **Keys to the kernel:** at spawn, the shell passes the saved key in one environment variable (`KOKYU_API_KEYS`, JSON), which the kernel removes at import. A key saved or removed later goes as one JSON line over the kernel's private stdin pipe, so no restart (FR-R-6 "at spawn", extended to "and when the user changes it"). Keys never cross the websocket. Long-lived children (llama-server, GPT-SoVITS) get no stdin.
- **Catalogs:** per-token prices are stored per 1M. Tags come from the catalog's `tags`, or from OpenRouter's `supported_parameters` and input modalities. The key is sent to `/models` only on the endpoint's own host (DeepSeek needs it). Each preset has its own cache.
- **Spend:** one global cap (D-058); the ledger records the endpoint id. A call keeps the price and endpoint id it started with, even if the key changes mid-reply.
- **Hardened after review:**
  - A preset fixes its own URLs, key variable, price unit and cache, and values written in the YAML are ignored with a warning. Otherwise changing only `preset:` in a copied config would send the new provider's key to the old URL.
  - A custom endpoint needs an id the shell can store (`^[a-z][a-z0-9_]{0,31}$`); any other id turns API models off with a warning.
  - An app key for an endpoint the config no longer knows is ignored.
  - A developer key with spaces or control characters is ignored, so no HTTP error can quote it.
  - The shell writes the new key before it deletes the old one.
  - The stdin reader uses its own unbuffered handle, so a normal exit does not crash.
**Consequences:** Switching provider means entering that provider's key again. DeepSeek publishes no prices, so its models stay blocked while a cap is on until the user answers D-058's open question. The picker has no per-provider headings (one provider). Custom endpoints and the Settings page are K1-13; error classes are K1-12. Until then, keys are entered in a small form behind the Key button in the model menu's API heading (with a hint to use .env outside the desktop app).

## D-060 Lazy boot: nothing heavy before the window, one load at a time, llama.cpp only when picked
Accepted · User ("make llama server start only after app is loaded and model is selected. default is an ollama model which is faster for the cold start"; "an app must not take that long to start") · Supersedes D-027's parallel start and D-052's boot warm-up of a llama.cpp default · 2026-11-15
**Context:** `npm run tauri dev` showed a blank window for a long time, lagged the PC and sometimes crashed File Explorer. The logs showed why. At kernel start, all of these loaded at once:
- the 35B on llama.cpp (21 GB file mapped, about 19.5 GB working set; 43 to 48 s to load, then a 1,003-token warm prompt at 34 tok/s on all 10 cores);
- GPT-SoVITS (torch and CUDA), spawned by the shell in parallel;
- faster-whisper on the CPU;
- the Ollama classifier and embedding models;
- a memory pass 20 s in.

Three launches between 11:56 and 11:58 each restarted the 35B load. Vite also watched `.venv` (8,160 files) and the `data/` and `logs/` folders the kernel writes all the time. The shell ran `netstat` and `tasklist` on the thread that creates the window. The PC's page file is 3.5 GB (commit limit 35.4 GB on 32 GB of RAM), so the simultaneous loads pushed the commit charge towards the limit, the likely cause of the Explorer crashes (**not verified**: no crash was reproduced). Nothing was wrong with a package: the kernel imports in about 1 s.
**Decision:**
- **The kernel opens its port at once and loads nothing heavy until the first window connects.** Then one step at a time: the thread's chat model, the GPT-SoVITS server, the speech model (only if `voice.stt.warm_up_on_start`), the memory catch-up pass. The router reads its cached catalog at once (cheap). A failed step does not stop the next.
- **llama.cpp starts only when the user picks a llama.cpp model in the chip, sends a message in a thread that uses one, or presses Try again.** Boot and opening a thread never start it. Ollama and API models still load on their own (D-054's loader, unchanged otherwise).
- **The default chat model on this PC is `local:ollama/qwen3.5:9b`** (the user's `config.yaml`). The example config stays `null` (= `llm.model`, an Ollama model).
- **The kernel owns GPT-SoVITS.** The folder moves from `src-tauri/launcher.local.txt` (deleted) to `tts.gpt_sovits.launch` in `config.yaml`. The kernel starts the server once (concurrent callers share the start), logs its output to `logs/gpt_sovits.log` (it went to DEVNULL), and stops it at shutdown. A server already answering on the port is used, never a second one. The kernel runs inside the shell's Job Object, so the server still ends with the app. `KOKYU_SHELL_STARTS_TTS` is gone. A line spoken while our server is still loading waits up to 8 s.
- **The shell starts only the kernel**, with the stale-port sweep and the spawn on a background thread, so window creation never waits for them.
- **`voice.stt.warm_up_on_start` defaults to false:** the mic arrives with K2.
- **Vite ignores** `.venv`, `data`, `logs`, `assets`, `docs` and `dist`.
**Consequences:** The window should paint while the PC is idle, and the 9B is ready seconds later. A user whose last thread used the 35B sees that thread with its model not loaded; the first message, or picking it, starts it with the "waking up" card. Voice arrives after the chat model is ready, not at the same time. Advice outside the repo, for the user: a system-managed page file (or at least 16 GB) gives the 35B headroom. **Not verified:** the Tauri window itself; voice playback after the change.

## D-061 Voice starts only when it is used
Accepted · User (relayed by a peer session, 2026-11-15): "only boot up voice when its needed (stt-tts mode) or the live back and forth voice chat" · Supersedes D-060's "GPT-SoVITS after the chat model" boot step · 2026-11-15
**Decision:**
- **At launch the kernel never starts GPT-SoVITS and never loads faster-whisper.** Plain text chat loads neither. The boot sequence is the chat model, then the memory catch-up pass.
- **Voice mode** is a kernel-wide switch, like the screen companions (D-056): one voice server, the driver window changes it, every window sees it. It always starts off. New v1 frames: client `voice_mode {on}`, server `voice_status {on, state, message, elapsed_s}` with the loader's states (`idle | loading | ready | failed`).
- **Turning it on** starts GPT-SoVITS (`tts.ensure_server`), then loads faster-whisper (`stt.preload`, replacing the boot warm-up and its `voice.stt.warm_up_on_start` key, now ignored). The composer shows "<name>'s voice is waking up…", then "Voice on", or the failure with **Try again**; × turns it off. The switch is in the `＋` tray ("Voice", replacing the disabled stub).
- **Mic only** (a transcription without voice mode) loads faster-whisper on first use, as before; replies are spoken only while voice mode is on.
- **Turning it off** makes replies text-only at once (no synthesis, no prewarm on a companion switch). The voice server the kernel started stops after `tts.idle_stop_s` (default 300 s) unless voice comes back on first, so a quick off/on does not reload it.
- **Live back-and-forth voice** (K2) turns voice mode on through the same switch.
- **The kernel stays in Python** (the slow boot was what loaded at launch, not the language) and keeps supervising the voice server: it decides when voice is needed, and the shell's Job Object still ends every child with the app. Moving more process supervision into the Rust shell is reconsidered in the kernel rebuild (C-2).
**Consequences:** The first spoken reply after turning voice on waits for the server (measured 47 s on this PC). Yuri's legacy widget page (`widget.html`) no longer speaks unless voice mode is on; it is due for removal (C-1). Verified live (browser pane, scratch data dir): no voice server at launch or after the chat model; the tray switch showed "waking up", then "Voice on"; GPT-SoVITS listened after 47 s; with `idle_stop_s: 20` it stopped 20 s after voice went off. Not verified: audible playback in the Tauri window.

## D-062 Yuri is only a character: Kokyu naming, v1-only protocol, the kernel split by job
Accepted · User ("code still mentions Yuri all the time. fix it. make it a flexible orchestrator, yuri must only be a character."; earlier: "Yuri is supposed to be a reference, I want you to create a cleaner, faster version which is flexible as well") · Supersedes D-049's coexistence of flat and v1 messages, and D-053's "Yuri's widget stays until K2" · Carries out TODO C-1 and C-2 · 2026-11-15
**Context:** The kernel was Yuri's code with names changed: one 2,097-line `app.py` holding module globals and one websocket function with an if-chain per message type, 121 `print("[yuri] …")` lines, Yuri's prompt as the built-in persona, the tool instructions only in Yuri's prompt, a Cargo crate called `yuri`, `orchestrator.log`, Yuri's widget page and its flat protocol beside the React window.
**Decision:**
- **Naming (`038ad7e`):** no code path names Yuri; she is a premade pack (`assets/premade/yuri/`) like Luna. Module loggers instead of prints (R-13); `logs/kernel.log`; crate and binary `kokyu`. With no pack installed a neutral `FALLBACK_PERSONA` answers. The tool instructions (screenshot, webcam, clipboard) move to the shared addendum, so every companion gets them (FR-W-3).
- **Shell:** Yuri's widget leftovers are dropped: tray click-through, the tray's "Use API model", and the global F9 push-to-talk hotkey (nothing listened to it, and it took F9 from every other app). `tauri-plugin-global-shortcut` removed.
- **Protocol (`d512ac9`):** the window speaks v1 only; a flat message is a typed `bad_message`. New client types `send`, `send_file`, `stop`, `switch_waifu`, `set_temp`, `camera_frame`; server types `waifu_state`, `surface_status`, `speak`, `camera_request`; error code `observer`. Retired: `settings.py` and the widget's settings messages, the router's runtime "Use API model" override (the chat role follows the user's pick, D-025, D-049).
- **The widget is deleted** (`widget.html`, `src/main.ts`, `src/ws-client.ts`, `src/style.css`). The avatar engine moves to `src/engine/` for the K2 Stage view; Yuri's repo stays the reference.
- **Screen companion remarks** are stored in the thread, flagged `ambient`, and never handed to a model (FR-SC-3, FR-R-7). With voice off they used to be lost.
- **Kernel layout (`d5da9f8`):** `app.py` is the server only (routes, lifespan, entry point). `session.py`: one `Session` per window; a message type is a `CLIENT_TYPES` entry plus one `Session.on_<type>` method (a test checks every type has one). `turns.py`: one model turn. `ambient.py`: the screen companions' checks. `companions.py`: the active companion's persona and voice. `boot.py`: start-up (D-060, D-061) and the stale-kernel takeover. `hub.py`: open windows, the driver, broadcasts, the shutdown event. TODO C-2 proposed `server.py`; `app.py` keeps the name because the shell, `dev.mjs` and the docs start it by that name.
- **Lazy imports:** faster-whisper and sqlite-vec load when first used, not at import (`import app` about 750 → 615 ms; most of the rest is FastAPI).
- **Graceful Quit (`8e4997b`, SPEC §4.2):** a window that has left counts as closing until its memory pass ends, and `/shutdown` waits for it (still bounded at 5 s). Before, Quit could exit mid-pass. The bug predates the split.
**Consequences:** Adding a message type touches `protocol/`, `src/net/protocol.ts` and one `Session` method. Tests patch the new modules (`turns.send_speak`, `hub.connections`, …); `tests/kernel_fixtures.set_config` gives every module that reads `CONFIG` the test's config. `KASANE/voice_files/` stays: it is `scripts/build_premade.py`'s input (voice clips, gitignored). **Not verified:** the Tauri window, the tray, voice playback.

## D-063 The heart and the thinking lines sit above the input; threads fill from the bottom
Accepted · User ("i believe heart loader should be above the input box and spin while model shows creative thinking words just like you", relayed by a peer session; "the messages should start at bottom not top. and its valid, if you ask me.") · Refines FR-C-5 and D-054's waking-up card · 2026-11-15
**Decision:**
- The heart moves out of the composer into a row just above it. While a turn is thinking, its outline traces round and a line beside it names the companion and rotates every 3 s through ten lines ("Luna is mulling it over…", "Luna is connecting the dots…"), starting at a random one. When the reply starts the line fades out and the heart beats once; it then rests.
- While a model is loading, the waking-up card speaks instead and the row stays quiet (one message at a time).
- The "•••" typing bubble is gone: the streaming bubble appears with the first token.
- A short thread sits on the input box and grows upwards, like a messenger.
- Screen readers hear "<name> is thinking" once, not each rotating line. With reduced motion the heart does not trace or beat, and the lines change without fading.
**Consequences:** `THINKING_LINES` live in `src/app/models.ts` beside the waking-up lines. Verified live in the browser pane against `qwen3.5:9b` (fb804a1). Not verified in the Tauri window.

## D-064 Effort is data: `config/models.yaml` for local models, catalog tags for API models, remembered per model per thread
Accepted · User (relayed by a forked session, 2026-11-15): "whichever out of config/model is appropriate. btw you are documenting these changes against spec right" · Settles D-054's **Proposed** `models.yaml` bullet; implements FR-M-8..11 (K1-07b, K1-11) · 2026-11-15
**Context:** FR-M-10 wants effort support as data, from catalog flags for API models and from `config/models.yaml` for local ones, with a thinking-token budget per detent "where the model/backend supports it". FR-M-3 also put the llama.cpp presets in `models.yaml`; D-054 kept them in `config.yaml` and left the question open. A peer session built the animated slider (`src/app/effort-slider.ts`, `EffortSlider.tsx`) without wiring it.
**Decision:**
- **Two files, two jobs.** Local models' effort levels live in `config/models.yaml` (the user's, optional, read first) and `config/models.example.yaml` (shipped, read second). The llama.cpp presets stay in `config.yaml` (`llamacpp.presets`, D-051): they hold machine paths. This is the only deviation from FR-M-3.
- **Format.** A `local:` list of `{match, efforts}` entries; `match` is a case-insensitive shell pattern on the model ref (`local:ollama/<name>`, `local:llamacpp/<preset id>`), the first match wins. `efforts` maps a level from the canonical set `off, low, medium, high, max` to what the backend gets as `think`: `true`/`false`, or `low|medium|high` for models that take a level (gpt-oss on Ollama). An unquoted YAML `off` key (read as `False`) means the level `off`. Bad entries are skipped with a warning. Shipped: gpt-oss (low, medium, high), Qwen3, DeepSeek-R1 and Magistral (off, high).
- **No thinking budget.** Neither Ollama's `/api/chat` nor llama-server's chat endpoint takes a per-request thinking-token budget, so no detent carries one. FR-M-10's budget is "where supported": nothing here supports it yet.
- **API models** offer low, medium and high when the catalog tags them `reasoning` or `thinking`, sent as `reasoning_effort` (`model_ref.openai_reasoning_effort`). `off` and `max` send nothing.
- **One place reads it.** `router/capabilities.py`: `efforts_for(ref, tags)` gives the slider's detents (each `model_list` row carries `efforts`); `think_for(ref, effort)` gives the backend value, `None` meaning the model's own default (`llm.think`). Both providers (`ollama_native`, `llamacpp`) ask it; neither knows model names any more (`model_ref.ollama_think` is gone).
- **Remembered per model per thread (FR-M-11).** Threads gain an `efforts` JSON column (schema 2, migrated in place). Switching models stores the old model's effort there and restores the new model's, or none.
- **The slider** sits in the model popover, shows only the current model's levels, and is hidden when there are none. While a reply generates, the chip glows with the level's intensity and speed (FR-M-9); reduced motion keeps it still. The chip names a level only when the model offers it; before the model list arrives (it loads with the picker), only a level the thread picked itself.
- **Room to think (found live).** Ollama counts thinking against `num_predict`: `qwen3.5:9b` on High spent the whole 512-token `llm.max_tokens` thinking and replied with nothing. While a local model thinks, Ollama now gets `llm.max_tokens + llm.reasoning_tokens` (new key, default 4096, under `num_ctx` 8192 with a typical 2.7k prompt). llama-server is sent no cap, as before.
- **No silent turn.** A turn that ends without a word sends a `model_failed` error, reason `EMPTY_REPLY`, with Retry and Switch model (FR-R-5), instead of ending with nothing on screen.
**Consequences:** Adding a model's effort support is a YAML edit, not code. A model no entry matches has no slider and runs with its default. The user's file is read once per process; `capabilities.reload()` exists for a later Settings page (K1-13). Reasoning text is still never spoken or shown (`llm.py` streams only `content`).

## D-065 VRAM manager v1: driver-read GPU, measured sizes, fits hints, a check before a load
Accepted · User asked to finish K1 ("push it and finish the rest") · Implements K1-09 (FR-M-3 hint, FR-M-6 load errors, ARCHITECTURE §7.3) · 2026-11-15
**Context:** The picker's rows carried `fits: null`, and a model too big for what was free loaded anyway, slowly or not at all. One cold `qwen3.5:9b` load took 104.6 s while the 9B and the `qwen3.5:4b` classifier swapped each other out (STATE, session 4). Measured on the dev PC today: 9B 5.6 GB, 4B 3.2 GB and embeddings 0.3 GB resident, 2.7 GB held by other programs, 394 MB free of 12 GB. A peer session wrote `KASANE/vram.py` (pure helpers, 19 tests) without wiring it in.
**Decision:**
- **Reading the GPU:** NVML straight from the driver's `nvml.dll` through ctypes, loaded by full path, else the driver's `nvidia-smi`. No `nvidia-ml-py` package (ARCHITECTURE §7.3 named it): the driver already ships both, and one dependency fewer helps the clean-machine install (PRODUCT). Several NVIDIA GPUs read as unknown in v1.
- **Measured beats estimated.** What a model really took is cached in `data/vram_measured.json`: from Ollama's `/api/ps` for models held whole on the GPU (read whenever the kernel looks), and for `llama-server` as the GPU-wide change between Ollama making room and the server answering `/health`. A model never measured is estimated as file size + `vram.kv_mb_per_1k_ctx` per 1024 tokens of context + `vram.margin_mb`. A MoE with its experts in RAM has no estimate until measured.
- **The plan for a load:** the helpers (classifier, memory writer, embeddings) stay; any other chat model makes room (the kernel or Ollama unloads it); a model already in VRAM fits. Room an unmeasured model would free is unknown. It fits if its need ≤ free + freed − `vram.headroom_mb`.
- **The picker** shows *fits* (muted) or *won't fit* (red) on each local row; unknown shows nothing. Never a refusal on a guess.
- **Before a load** (`boot.load_chat_model`), a local model that will not fit is refused before anything is unloaded, so the current model stays up. The waking-up card says why and names what holds the memory, largest first, with the rest as "other programs": "It needs about 10.3 GB of graphics memory, but only 5.3 GB would be free. In use: qwen3.5:4b (3.1 GB), other programs (2.7 GB), nomic-embed-text (0.3 GB)." *Try again* checks again (after closing something); *Switch model* opens the picker.
- **Not a lock.** A message sent to a refused Ollama model still goes to Ollama, which may run it split across GPU and CPU (slowly). The check guards the load the kernel starts, not the user's choice.
- **Config:** a `vram:` block (`headroom_mb` 512, `kv_mb_per_1k_ctx` 128, `margin_mb` 512).
**Not in v1:** the TTS backend and the renderer are not named residents (they show as "other programs"); `vram.is_large` is unused because cross-backend exclusivity stays where D-052 and D-054 put it; no *Unload X* button (SPEC §5 table) yet. The 4B/9B swap is now reported instead of silently slowing a load; whether the 4B classifier should stay beside an Ollama 9B chat model is the user's config (`models.local.classifier`; the shipped default is null, one model).
**Consequences:** Tests never read the real GPU: `conftest.py` stubs `vram.gpu_memory` and gives each test a fresh measured cache.

## D-066 A failed turn says why on the turn; API failures in plain words, the provider's own in Details
Accepted · User asked to finish K1 ("push it and finish the rest") · Implements K1-12 (FR-R-5, SPEC §5 "API quota or error") · 2026-11-15
**Context:** Failed turns already carried Retry and Switch model (D-025, D-050), but in a bar above the input box, and an API failure read "The chosen model failed (401 from https://…: '{…}')".
**Decision:**
- **Inline.** A `model_failed` or `model_blocked` error shows as a card right under the turn it failed, with Retry, Switch model and dismiss; the line stays marked "Not answered". The bar above the input keeps only notices that are not about a turn (a refused send, a lost connection). One `notice` in the store; `turnFailure` and `barNotice` decide where it shows.
- **Plain words per kind (FR-R-5):** `ProviderError` carries the HTTP `status` and a `timeout` flag. 401: "The API key was refused." 403: "…not allowed to use this model." 402: "The API account is out of credit." 429: "The provider is limiting requests right now." Timeout: "The provider did not answer in time." 5xx: "The provider had a problem on its side." Anything else: "The chosen model failed." Each ends "Retry, or switch model." `reason` says which (AUTH, QUOTA, RATE_LIMIT, TIMEOUT, PROVIDER_ERROR).
- **Details:** the error frame gains an optional `detail`, the provider's own first line (already redacted, at most 300 characters), under a "Details" disclosure on the card.
**Consequences:** Protocol v1 grows one optional field; old windows ignore it.


## D-067 Settings v1: Models, Memory, Doctor, About; editing settings waits for settings.json
Accepted · User asked to finish K1 ("push it and finish the rest") · Implements K1-13 (FR-SET-1 partly, FR-SET-3, FR-MEM-4, FR-COMP-5); FR-SET-2 deferred to K1-13b · 2026-11-15
**Context:** The sidebar's Settings button opened nothing (K1-03). FR-SET-1 lists eight sections, most of which belong to later phases (Voice K3, Waifus K6, Scenes, Pets). FR-SET-2 wants settings in `settings.json` that apply without a restart, but every tunable lives in `config/config.yaml` today (CLAUDE.md §6), and which file wins when both set a key is the user's call.
**Decision:**
- **A dialog over the chat** with four sections: *Models* (the default model, local rows, API key status and budget, read-only), *Memory*, *Doctor*, *About*. Other sections arrive with their phases. Escape or a click outside closes it.
- **Memory (FR-MEM-4)** lists the live facts, newest first (at most 500, no paging), shared by every companion (FR-MEM-1, so nothing looks at a waifu). Nothing is hard-deleted (FR-MEM-3): *Correct* adds the user's wording as a new fact (`source="correction"`) that supersedes the old one; *Forget* marks it forgotten (the writer's existing marker), and it waits under "Forgotten" with *Restore*. A replaced fact cannot be restored. Each action is logged as a memory event. A correction is embedded at once, else the writer pass backfills its vector.
- **Doctor (FR-SET-3, FR-COMP-5):** one row per component (kernel, Ollama, default local model, embeddings, llama.cpp, voice, speech to text, GPU memory, API models), each `ok`, `warn`, `fail` or `off` with a fix hint on every problem. Checks are read-only and never start or load anything; voice reads *Off* ("Starts when you turn voice on", D-061) until voice mode is on. The GPU row splits used memory into Kōkyū's models and other programs and warns only when other programs hold more (found live: a card full of Kōkyū's own 9B, 4B and embeddings is the normal state, not a problem).
- **Protocol v1** gains client `doctor`, `memory_list`, `memory_edit`, `memory_forget`, `memory_restore` and server `doctor_report`, `memory_facts`. Any window may send them, observers included: they act on app-level data, not a thread.
**Deferred (K1-13b, needs the user):** `settings.json` and editing in the app (FR-SET-2), the Settings switches for the screen companions (K1-05b), a custom API endpoint (K1-08b) and the Ollama URL. Open question: when `settings.json` and `config.yaml` both set a key, which wins?
**Consequences:** Settings changes nothing yet but memory; models and budgets are still edited in `config/config.yaml`, and the Models section says so.

## D-068 The chat window follows the reference image; SPEC places the chips where it shows them
Accepted · User asked for the UI matched to `docs/reference-images/chat-ui.webp` (session 4) and to finish K1 ("push it and finish the rest") · Implements K1-15; amends FR-C-4, FR-C-6, FR-S-1, FR-M-1 · 2026-11-15
**Context:** The reference puts the companion chip in a top bar, has no companions list in the sidebar, opens the attach tray with a paperclip and puts the model chip under the input box. SPEC said the companions sit at the top of the sidebar (FR-C-6) and both chips in the input row (FR-S-1, FR-M-1).
**Decision:**
- **Frameless window** (`decorations: false`) with its own minimize, maximize and close buttons at the top right; the top bar is the drag region. Close still hides to the tray (`CloseRequested`, as the frame's button did). The capability grants only `minimize`, `toggle-maximize`, `close` and `start-dragging`. Outside the desktop app the buttons are not drawn.
- **Top bar:** the companion chip (avatar and name, popover opening downward) and a **Temp Chat switch** (FR-MEM-5) that sends the existing `set_temp`; the sidebar's *Temp* badge follows. The thread's title is no longer repeated above the thread (the sidebar marks the open thread with a pink edge).
- **Sidebar:** the app icon and name, a pink *New chat*, search with an icon, the history groups, a Settings gear with the connection state. No companions list: one way to pick a companion (the chip), as SPEC already has one model control. SPEC FR-C-6 and FR-S-1 now say so.
- **Input box:** one rounded box with the paperclip (it opens the same tray, FR-C-4), the message, a mic and a round Send (Stop while a reply runs). The mic is drawn but disabled: speaking to her needs voice input, which arrives in K2. The model chip sits under the box at its right, outlined in pink: icon, name, `·`, the effort in pink.
- **Model popover:** one line per row (name, size or price, fits, badges), columns lined up by a CSS subgrid; the backend detail (Ollama · 9.7B · Q4_K_M) moved to the row's tooltip. Local rows get **vision / thinking / tools** badges from the `capabilities` Ollama already returns in `/api/tags` (no extra request); "reasoning" and "thinking" both read *thinking*; badges keep one order. Prices drop "per M" from each row; the API heading says "$ per 1M in / out". The footer is one line, "Spent today $X of $Y", with the hour and the month in its tooltip (FR-M-7).
- **Palette:** plum-black panels and a brighter pink (`--accent #f27aa6`); list bullets in replies are pink.
**Not taken from the reference:** *VR space* and *Enable 2D pet* (3D mode and pets are later phases; a dead button there would mislead), the sakura logo (the app icon is used), the `zdr` label (it stays *no retention*).
**Consequences:** `tests-fe/tauri-window.test.mjs` checks the frameless window's shadow, its four permissions and that the top bar wires the buttons. The window's look and dragging in the real WebView2 window are not verified until `npm run tauri dev` is run.

## D-069 Replies end at their text; a status line fills the left under the input box
Accepted · The user's review of K1-15: "left side looks kinda blank below input, suggestions?" and "move the bot's message box closer to heart (just some proper spacing like a chatui)" · Refines D-068 (K1-15; FR-C-5, FR-C-9, FR-SC-2, FR-MEM-5) · 2026-11-15
**Context:** Under every reply sat an invisible row for Copy and Regenerate (shown on hover), so the newest reply ended about 66 px above the heart. Under the input box only the model chip sat at the right.
**Decision:**
- **Copy and Regenerate share the name line** of a reply (still shown on hover or keyboard focus), so a reply ends at its text. Turns are 22 px apart; the newest item has no bottom margin and the thread ends 10 px above the heart.
- **One column width** (`--column`, 800 px) for the thread, the heart row, notices and the input box; the heart lines up with the reply text.
- **A status line under the input box, at the left:** the voice and screen companion chips (FR-SC-2) move there from inside the box, so the box stays one row; with none on, it says "Temp Chat: this chat is not remembered" (FR-MEM-5) or, normally, "Enter to send · Shift+Enter for a new line".
**Consequences:** No layout change on hover. The chips' one-click stop is unchanged, only placed under the box.

## D-070 settings.json wins over config.yaml; what Settings edits applies at once
Accepted · The user ("Settings file wins") · Implements FR-SET-2 and FR-SET-1 (Models), FR-SC-1's Settings half (left open by D-056), the custom endpoint in the app (K1-08b, FR-R-6, D-059) · K1-13b · 2026-11-15
**Context:** D-067 left Settings read-only, except the memory viewer, until the user said which file wins when `settings.json` and `config/config.yaml` both set a key.
**Decision:**
- **Precedence:** `settings.json` (in the app data folder, `paths.app_data_dir()`) > `config/config.yaml` > the code defaults, key by key (sections merge). `settings.json` holds only what Settings edits, in config.yaml's own layout: the Ollama address (`llm.base_url` and `providers.local_ollama.base_url`, both, because the legacy key wins inside config.yaml), the budget (`budget.enabled` and the three caps; an empty cap is saved as -1, no cap), a custom API endpoint (`providers.airouter.*`) and `task_guide.on_at_start` / `ocr_watch.on_at_start`. config.yaml stays the developer's and the advanced file (default model, llama.cpp presets, roles). *Use the default* and *Remove* drop the keys, so config.yaml's value shows again.
- **Applied at once:** a change is checked, the config is built with it, the file is written in one step (temporary file, then replace), and `config.install` makes it the running config: every loaded module that bound `CONFIG` at import is pointed at the new one, and modules read `CONFIG` when they run. `Router.reconfigure` follows (budget, roles, the API slot); every window gets the new `settings` and `model_list`. Hand edits to config.yaml still need a restart.
- **At start:** the kernel lays `settings.json` over config.yaml in its lifespan, before boot. Not at import, so the test suite never sees the user's file. A file that cannot be read or does not build is ignored with a warning and the app starts on config.yaml; a top-level value that is not a section is dropped, so a hand edit cannot wipe a whole section.
- **Ollama on this PC only:** the address must be http(s) to 127.0.0.1, localhost or ::1, with no user name, query or fragment. Screen captures, camera frames and voice go to the local model and must never leave the machine (invariant 3); an Ollama elsewhere on the network would break that without a sign.
- **A custom endpoint:** a name (at most 40 characters) and an https address (plain http only to this PC; the same `url_problem` check as for keys). Its provider id is `custom_` plus 8 hex digits of the SHA-256 of its origin, so a key saved for it never follows an edited address to another host. `api_key_env` is empty, so it never receives a developer key from `.env`; only a key saved for it with *Key* in the model picker, which lists it. Its prices are unknown (`price_unit: none`), so with a cap on its models are blocked (D-058); the form says so. Saving one turns the API slot on.
- **Screen companions:** the new Screen section has *On now* (the same switch as the ＋ tray, driver window only) and *On at start* for each mode. At start, once a window is up, a mode set to start passes the same vision check as the tray (FR-SC-3), or stays off and the window gets the `vision_unavailable` notice.
- **The kernel checks every value** (`settings_file.change`) and answers every change with a `settings` frame, with `problem` set when it refused; the form shows it beside its Save. The client refuses only a cap it cannot read as a number, because JSON would carry it as null, which means no cap.
- **Protocol v1:** client `settings_get`, `settings_set {ollama_url?, budget?, custom_api?, screen?}` (only the keys sent change); server `settings`.
**Consequences:** new `KASANE/settings_file.py`; `config.load_config(overlay=)` and `config.install`; `Router.reconfigure`; llama.cpp's start reads the Ollama address when it frees Ollama, not when it was built. Still in config.yaml only: the default model and the llama.cpp presets (the user's K1-07b answer), voice (K2).

## D-071 *Unload X* on the graphics-memory card, only for a model that stays unloaded
Accepted · The user ("yeah finish up") · Implements K1-09b (SPEC §5 "Model fails to load (VRAM)": *Unload X* / *Pick smaller model*); refines D-065 · 2026-11-15
**Context:** D-065's refusal names what holds the memory but offers only *Try again* and *Switch model* (the "pick smaller model" half). The models it names are Kōkyū's own helpers, which stay beside the chat model (D-052: the classifier, the memory writer, the embedding model), plus "other programs"; any other chat model already counts as freed.
**Decision:**
- Each blocker carries its model ref. The card offers *Unload X* for an Ollama model the kernel will not load again at once. Not the classifier or the embedding model: `warm_helpers` loads them again right after the chat model, and the classifier runs before every reply, so unloading them would make room for a moment and bring back the swap D-065 reports. In practice the button appears for the previous chat model kept as the memory writer, which loads again only at the next memory pass. "Other programs" get no button: Kōkyū cannot close them.
- One click unloads that model (`keep_alive: 0` to Ollama) and tries the load again; the new check says whether it fits now. Only a model the card offers (the kernel checks the request against the failed status), from the driver window, never mid-reply. A failed unload is logged; the load that follows says what is still in the way.
- **Protocol v1:** client `model_unload {ref}`; `model_status` gains `unload: [{ref, label}]`, empty unless a load was refused for graphics memory.
**Not in v1:** a classifier blocker gets no button; freeing it for good is `models.local.classifier: null` in config.yaml (one model; the open classifier question). The TTS backend is still part of "other programs" (D-065).

## D-072 One chat model in memory: the helper roles follow the pick
Accepted · The user ("only load the model that is selected. when selecting other one, unload rest"; helpers: "The selected model"; embeddings: "Keep it loaded") · Extends FR-M-6; supersedes D-052's helpers kept beside the chat model; refines D-065 and D-071 · 2026-11-15
**Context:** D-052 kept the classifier (qwen3.5:4b on the user's PC), the memory writer and the embedding model loaded beside the chat model, so picking a 12B left a 4B taking 3 GB and the VRAM card refused loads that would fit alone. FR-M-6 unloaded only the other *backend*: a second Ollama model or llama-server under an API pick stayed.
**Decision:**
- **Picking a model unloads the rest.** An Ollama pick stops llama-server and unloads every other Ollama model but the embedding model; a llama.cpp pick keeps D-052's llama-server keep set, now only the embedding model; an API pick stops llama-server and unloads Ollama's models but the embedding model (still ready at once; the freeing runs after).
- **The helper roles run on the picked model.** With an Ollama model picked, `classifier`, `memory_writer` and `vision` resolve to it (`model_for`), so nothing else loads. Their `models.local` entries apply only while a llama.cpp or API model is picked; then that model loads for its call and leaves (`keep_alive: 0`). Memory writing stays local (D-015).
- **The embedding model stays loaded** (about 0.3 GB): recall embeds every message.
- `providers.local_ollama.keep_alive` (30m), which no request sent, now goes with every call to the picked model and the embedding model; any other model gets `keep_alive: 0`.
- *Unload X* (D-071) may now offer the classifier: it is no longer warmed after a load.
**Cost:** Task Guide's classifier and memory passes use the bigger chat model (slower, better). With a llama.cpp or API model they pay a cold load per call.

## D-073 Settings → Appearance: themes kept by the page, not settings.json
Accepted · The user ("fix the colors too. add a theme selector in ui which gives option to customize chat interface"; options picked: preset themes, accent color, message style, text size) · Not in SPEC; adds a Settings section beside FR-SET-1 · 2026-11-15
**Context:** One dark plum palette was hard-coded, with a few colors outside the variables (a violet heart beside a pink accent, white text on any accent). The user's references are character-chat sites with neutral greys and replies in bubbles beside the character's picture.
**Decision:**
- Settings gains **Appearance**: a theme (Kōkyū plum, Midnight neutral greys, Light), an accent color (the theme's own, six swatches or any color), messages (Open, the current layout, or Bubbles: her replies in a bubble beside her initial) and a text size for chat messages (small, normal, large).
- It is the window's own look, so the page keeps it in `localStorage` (`kokyu.theme`), applies it before the first paint, and other open windows follow through the `storage` event. The kernel never sees it; settings.json (D-070) stays for what the kernel uses. A stored value is checked field by field; anything unknown is the default (an accent must be `#rrggbb`).
- Every color the window draws comes from a variable: the heart follows the accent, text on the accent is black or white by contrast, error cards mix the danger color into the background.
**Not in v1:** her real picture in the bubble (the VRM thumbnail arrives with K2), a font choice, the roleplay styling of actions and asides (the modes plan).

## D-074 Conversation modes: Chat and Roleplay per thread; prompt layers; story memory
Accepted (assumed answers) · The user: "we should make modes … brainstorm and come up with a plausible plan", then "continue next step … complete as far as you can work". The six questions in `docs/notes/modes-plan.md` §9 were not answered; Claude took the recommended answer to each and the user may reverse any of them · Adds SPEC §2.18 FR-MODE-1..10 and phase K1c; amends SPEC Appendix A rules 3 and 6; partly answers D-055 · 2026-11-17
**Context:** The plan in `docs/notes/modes-plan.md`. A code map of everything modes touch found traps the plan did not name: a fictional "forget that" would retire real facts (`forget.maybe_forget` runs every turn), "look at me" in a story would capture the camera (`look_intent` runs even in Temp Chat), screen companions write remarks into whatever thread is open, the opening message of a story is dropped by `history_from`, Regenerate can leave a summary that folded the replaced reply, and the stored reply loses its line breaks (`" ".join` of speech chunks), which breaks Markdown and paragraphs after the stream ends.
**Assumed answers (§9):** (1) a thread's mode is fixed when it starts; (2) Chat answers in about 3 to 4 lines, longer only when the task needs it; (3) no tools in Roleplay; (4) voice speaks only dialogue in Roleplay; (5) no premade scenario cards per companion (they would be a new per-companion asset beyond prompt, voice, VRM and sprites; RULES §3.1): cards are the user's, app-level, saved in `threads.db`; (6) Claude writes persona-only prompts for Luna and Yuri as `persona.md` in each pack and points `waifu.yaml` at it; the original `prompt.md` stays untouched, so going back is one line.
**Decision:**
- **Mode is a thread property** (`threads.mode`, `chat` | `roleplay`, schema 3 with `scenario` JSON, added in place by column checks like `efforts`). Never read from or keyed by a companion. The router role stays `chat` in both modes (a new role would route an API pick to the local default: a silent fallback); only the tool list differs.
- **System message** = persona, then the mode layer (and, in Roleplay, the scenario card with its opening line), then the shared addendum (emotion tag, honesty about abilities), then the tool guidance in Chat only. It is rebuilt by one helper wherever history[0] is set (window open, thread load, Regenerate, companion switch, llama.cpp warm-up), so a switch or a regenerate never drops the mode. Stable per thread, so llama-server's cached prefix holds.
- **Per-turn, not in history[0]:** the story summary and the delivery layer (voice on) go into the turn's ephemeral system note, beside recall: voice is kernel-wide and toggles, and the summary changes; neither should break the cached prefix.
- **Roleplay turn:** no `forget`, no Task Guide classification or idle-clock touch, no look intent, no tools (and a tool call the model makes anyway is refused: dispatch only runs tools offered this turn, which also closes the same hole for API models); recall is the profile card only, framed as the real person, not their role; the exchange is not written to `transcript_log`, so the memory writer never sees it. Temp Chat in a roleplay thread also drops the profile card and the story memory.
- **Story memory** (`story_memory` in `threads.db`, cascades with the thread): a running summary written by the local `memory_writer` role (D-015) from the thread's own messages, in batches (every `story.summarize_every` new messages, never the newest `story.keep_recent`, so Regenerate, which replaces only the last exchange, never touches summarized text), when the arbiter is idle, and on opening a roleplay thread that is behind. Fed to each turn capped at `story.max_chars`.
- **Opening message:** stored as her first message flagged `meta.opening` and written into the scenario part of the system message, so the model keeps it after reloads and once it falls out of the history window. A greeting written by the model from the card is not in v1.
- **Speech in Roleplay:** a streaming dialogue filter on the speech path only (`*…*`, `(OOC …)`, `((…))`, `[…]` dropped; text outside quotes counts as dialogue until the reply's first quote, after which only quoted text is spoken); captions show what is spoken. The stored and displayed reply is the raw streamed text minus the emotion tag, in both modes (fixes the lost line breaks).
- **Screen companions** stay quiet while a roleplay thread is open (both loops skip). Uploads stay allowed in Roleplay: the user chose to share.
- **Client:** New chat stays; a *New roleplay…* dialog takes a card (saved cards can be picked, saved, deleted) or starts blank. Roleplay threads carry a badge, render `*…*` italic and softer and asides muted, and render the user's own lines the same way; Chat threads keep ordinary Markdown.
**Not in v1:** a model-written opening, a viewer or editor for the story summary, actions driving the avatar (K2, FR-MODE-10), changing a thread's mode, premade cards.

## D-075 K1c build and review: what was settled, what stays open
Accepted · The user: "continue next step … complete till as far as you can work … then i will push" · Follows D-074; FR-MODE-1..9 · 2026-11-17
**Context:** K1c was built (b1cd674 to c9dbf95) and then reviewed adversarially; each finding was checked against the code before it was fixed or rejected.
**Decision:**
- **Schema:** `threads.db` went 3 (mode, scenario) → 4 (`story_memory`) → 5 (`scenarios`), each added in place like `efforts`; D-074's "schema 3" is only the first step.
- **Story folds wait for the chat model** (`boot.chat_model_settled_event`): a catch-up fold at start must not compete with the first model load. The fold's token cap is sized from `story.max_chars` (`tokens_for`), not a fixed 512.
- **A screen-companion remark is dropped if the open thread changed while it was being checked** (`still_valid`), so a remark never lands in a roleplay thread opened mid-check.
- **Stop keeps the raw text minus an unclosed `[tag` fragment**, the same rule as a finished reply.
- **The dialogue cut honours curly-quote direction** (U+201C opens, U+201D closes); the speech chunker's tag hold-back is linear (the first regex was cubic on long input and could block the loop, RULES §3.7).
- **Prompt wording:** the roleplay layer says the scenario sets place, time and her role while her personality and way of talking stay her own (a persona's "you live here" no longer pulls against a card); the chat voice note says the closing emotion tag still applies and is never spoken.
- **Client:** Start roleplay closes the dialog only when the kernel accepts; a save answers from its own `scenarios` frame; Escape during the delete confirm cancels only the confirm; bold inside an action parses as bold. *New roleplay…* sits under *New chat* (beside it, labels wrapped or cut in a narrow sidebar).
**Rejected after checking, recorded so they are not re-raised:** the user's own lines parsed as roleplay Markdown in a roleplay thread (intended, D-074 Client); Luna's persona mentions intimate roleplay (her pack text, the user's asset); the persona no longer says "[teasing] by default" (the shared addendum carries the tag rule); the llama.cpp warm-up picking the companion and thread from global state (that state is what the first turn uses).
**Left open (TODO K1c-10):** a reply quoted only with U+201D speaks its narration; a remark partly spoken is dropped if the thread changes during speech; a fold cut by the token cap is not detected (Ollama's `done_reason` is not read); a save pending over a disconnect stays "Saving…" until reopened; Escape-in-confirm has no automated test; a fold may start before `load_thread`'s delayed model request; Temp Chat lines in a roleplay thread can later be folded into its summary; `thread_list` sends full cards on every refresh.
