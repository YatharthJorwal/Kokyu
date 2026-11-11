# TODO — Kōkyū

Phased plan with gates. Work **top to bottom inside the current phase**, one item at a time. Tick items with the commit hash: `- [x] K0-03 … (a1b2c3d)`. Do not start the next phase until its gate passed **and** the user approved (R-32). Requirement IDs refer to `SPEC.md`.

Last updated: 2026-11-11 (session 1, docs only: inventory and corrections).

## Phase overview

| Phase | Goal | Status |
|---|---|---|
| Docs | Spec set, license, README | **Done and pushed** (`704c05d`) |
| **T** | Headless GPT-SoVITS backend by a CLI agent (parallel track) | Not started |
| **K0** | Skeleton: seed from Yuri, waifu pack, shared memory, invariance (rescoped, D-026) | **In progress:** K0-00 to K0-02 done; K0-03 onward awaits plan approval |
| K1 | Chat shell, waifu switcher, model switcher, effort slider | Not started |
| K2 | Stage view, voice, senses | Not started |
| K3 | In-app waifu creator | Not started |
| K4 | Desktop pets | Not started |
| K5 | 3D mode | Not started |
| K6 | Hardening | Not started |
| K7 | Windows packaging | Not started |
| D1, D2 | Agent mode, VR | Deferred |

---

## Docs (session 0)

- [x] Scope v0.3, SPEC, ARCHITECTURE, RULES, DECISIONS, STATE, HANDOFF, TODO, TTS brief, README, LICENSE, `.gitignore`
- [x] DOC-1 User reviewed the docs (confirmed: shared memory, name Kōkyū, KASANE folder stays uppercase)
- [x] DOC-2 First commit pushed to `main` (`704c05d`)

## Track T: TTS backend (parallel, separate agent) — brief: `TTS-BACKEND.md`

- [ ] T-1 Choose the install folder outside the repo; do not modify the old cluttered GPT-SoVITS folder
- [ ] T-2 Clean install of the newest stable GPT-SoVITS with zero-shot support; own venv; CUDA build matching the RTX 3060; record version/commit
- [ ] T-3 Headless API server, no WebUI, bound to 127.0.0.1, port configurable
- [ ] T-4 `start` and `stop` scripts, plus a health check
- [ ] T-5 `smoke_test` script: same sentence with two different reference clips back-to-back, no restart, prints latency per call
- [ ] T-6 English `INSTALL.md` and `README.md` in the backend folder; record exact API parameters actually accepted
- [ ] T-7 Measure VRAM use while idle and while synthesizing; report to the user (feeds `ARCHITECTURE.md` §13)
- **Gate T:** smoke test passes on this machine; parameters and VRAM numbers recorded in `STATE.md`.

## Phase K0: Skeleton (rescoped in session 1, D-026)

Goal: a running kernel and shell seeded from Yuri where **a waifu is a pack** and switching her changes only persona and voice. Everything marked "sandbox" can be verified by Claude (pytest, `test:fe`, `tsc`, `vite build`); everything touching Rust, a window, audio or a model needs the user (manual gate).

- [x] K0-00 Environment: sandbox baseline verified (Yuri: 641 pytest, 65 frontend, tsc, vite build). **User machine still unverified:** run the command block in `HANDOFF.md` §5 and paste the output into `STATE.md` §2
- [x] K0-01 Docs committed and pushed (`704c05d`)
- [x] K0-02 Yuri and Luna inventory: `docs/notes/yuri-inventory.md`; `ARCHITECTURE.md` §2, 3, 4.1, 5, 7.1, 9.1, 11 corrected; D-024 to D-031 recorded
- [ ] K0-03 Seed commit: copy Yuri at `e32af4f` **verbatim** (excluded as in D-028); tests green in the sandbox as seeded
- [ ] K0-04 Rename and rebrand in small reviewed steps (no bulk replace): `orchestrator/` → `KASANE/` (`git mv`), `conftest.py`, scripts, Rust paths; product name Kokyu, identifier `io.github.yatharthjorwal.kokyu`, window title, tray text, `YURI_*` → `KOKYU_*`, log prefixes, npm package name; kernel port 8765 → 8780 in Python, Rust, `ws-client.ts`; no hard-coded ports left in Rust
- [ ] K0-05 `KASANE/paths.py` (dev `./data`, packaged `%APPDATA%\Kokyu`); replace `repo_path("data/…")` and other hard-coded locations; tests
- [ ] K0-06 Config v3: strip machine paths from the example, move the TTS reference clip and transcript out of config (they become waifu data), add `waifus.dir` and `kernel.port`, TTS block becomes `tts.backend` (URL plus optional launch); update `config.example.yaml`; add `models.example.yaml`
- [ ] K0-07 `KASANE/waifus/`: pydantic model for `waifu.yaml` (FR-W-1, 4, 6), loader, validator, registry; unit tests
- [ ] K0-08 Persona as data (D-031): split Yuri's `SYSTEM_PROMPT` into personality (waifu prompt) and shared app addendum (emotion tags, speech rules); `scripts/seed_waifus.py` imports the Luna and Yuri prompts from paths the user supplies and writes `data/waifus/<id>/`; create `docs/THIRD-PARTY.md`
- [ ] K0-09 Active waifu in the existing single-history flow: per-connection active waifu; `switch_waifu` and `waifu_state` messages (`ARCHITECTURE.md` §5.2); system prompt swapped on switch; history kept
- [ ] K0-10 `KASANE/prompting.py`: system assembly (persona + addendum), ephemeral blocks unchanged; unit tests
- [ ] K0-11 TTS per waifu: `tts.synthesize(text, voice)` with the waifu's reference clip, transcript and language; backend URL from config; pre-warm; **pyttsx3 fallback off by default** (FR-V-7); typed error when the backend is down; tests with a fake server
- [ ] K0-12 Shared memory with speakers (FR-MEM-1, 2): `transcript_log` gains a speaker column through `memory/migrate.py`; `add_transcript_turn(..., speaker=)`; writer prompt and episode summaries name the waifu; migration and writer tests
- [ ] K0-13 **Invariance tests** (FR-W-3, FR-S-5): two fixture waifus; the `ModelRequest` messages differ only in the persona prompt; same role and model decision, same recall results, same tool schemas offered; only prompt and TTS parameters differ
- [ ] K0-14 Map the existing local-only router tests to FR-R-3 (no behaviour change); add one test that no waifu field reaches `router.route`
- [ ] K0-15 Temporary waifu dropdown in the existing widget's quick-action menu, with a one-line debug readout (waifu, voice clip, model); no layout redesign (that is K1)
- [ ] K0-16 `scripts/check.mjs` and `npm run check` (tsc, test:fe, build, cargo check, pytest; cargo skippable with a flag); green in the sandbox
- [ ] K0-17 Update `STATE`, `HANDOFF`, `TODO`, `DECISIONS`; gate review
- **Gate K0 (sandbox, automated):** invariance tests green; switching Luna ↔ Yuri changes only the persona prompt and TTS parameters (asserted); `pytest` + `test:fe` + `tsc` + `vite build` green.
- **Gate K0 (manual, user):** `npm run tauri dev` opens the Kokyu window; the dropdown switches waifus; replies differ in persona; the voice is audibly different per waifu using the **existing GPT-SoVITS install** (same `/tts` contract, so Track T is not required for this gate); `cargo check` passes on the PC.

## Phase K1: Chat shell

- [ ] K1-00 Extract a **conversation manager** from `ws_endpoint` / `_run_turn`; SQLite **threads store** with `active_waifu_id`, per-thread `model_ref` and effort; divider messages (FR-C-1, 10, FR-S-2)
- [ ] K1-00b Typed protocol (`KASANE/protocol/`, mirrored in `src/net/`), token streaming events, versioned frames (`ARCHITECTURE.md` §5.3)
- [ ] K1-00c `llm.py` takes a model and an effort/think parameter; `OllamaNativeProvider` honours `model`; `chat` role and the egress policy in `router/decision.py` with tests (D-025, FR-R-4, 5, 7) — **needs the user's OK on D-025 first**
- [ ] K1-00d Normal app window (replace the 340×480 widget window), CSP locked down, Temp Chat flag per thread (FR-MEM-5)
- [ ] K1-01 Spike: Qwen3.5-35B-A3B Q4 on llama.cpp with experts on CPU: VRAM, RAM, tokens/s; record numbers
- [ ] K1-02 Introduce React shell around the existing engine; Zustand store fed by WebSocket events (D-013)
- [ ] K1-03 Sidebar: waifu list, history (grouped, search, rename, delete), Settings entry (FR-C-6)
- [ ] K1-04 Thread view with streaming, Markdown, copy/regenerate, Stop (FR-C-1, 2, 8, 9, 10)
- [ ] K1-05 Input box and `＋` tray with disabled stubs (FR-C-3, 4); port the heart animation (FR-C-5)
- [ ] K1-06 Waifu switcher chip and divider behaviour (FR-S-1, 2)
- [ ] K1-07 Capability registry (`models.yaml`) and Ollama/llama.cpp discovery (FR-M-3, 10)
- [ ] K1-08 AI Router provider: catalog fetch/cache, SSE streaming, spend ledger, audit, budget cap, redaction (FR-M-4, FR-R-2, 6)
- [ ] K1-09 VRAM manager v1 (NVML), exclusivity across backends, fits hints, load errors (FR-M-6, ARCHITECTURE §7.3)
- [ ] K1-10 Model chip + popover (search, Local/API sections, badges, footer meters) (FR-M-1, 2, 5, 7)
- [ ] K1-11 Effort slider with animation and reduced-motion fallback (FR-M-8, 9, 11)
- [ ] K1-12 Inline API failure UX with Retry / Switch model (FR-R-5)
- [ ] K1-13 Settings (FR-SET-1, 2), Doctor panel (FR-SET-3), Memory viewer (FR-MEM-4)
- [ ] K1-14 Tests, `STATE`/`HANDOFF` update
- **Gate K1:** chat with one local and one API model; change model, effort and waifu mid-thread independently; failure UX shown with a forced API error; user sign-off on the layout vs the reference.

## Phase K2: Stage and voice

- [ ] K2-01 Stage view: auto-framing, backdrop, spring bones, idle motion, look-at, expression hooks (FR-ST-1..3, 5, 7)
- [ ] K2-02 Lip-sync from played audio; captions; docked input; chat log slide-over; Chat | Stage toggle (FR-ST-3, 4, FR-C-7)
- [ ] K2-03 Sidebar waifu click → Stage, history click → Chat (FR-S-4)
- [ ] K2-04 Speech-safe normalizer, clause pipelining, arbiter, barge-in (FR-V-2..5)
- [ ] K2-05 TTS pre-warm on switch (FR-S-3); TTS-down banner (FR-V-7)
- [ ] K2-06 STT (faster-whisper CPU), VAD, push-to-talk, mic toggle, live voice (FR-V-6)
- [ ] K2-07 Camera and file attach into the tray; vision helper (FR-C-4, FR-R-3, 4)
- [ ] K2-08 Measure and calibrate latency and fps targets (FR-V-8, FR-ST-6); record in `STATE.md`
- **Gate K2:** alternate two waifus mid-conversation; voice and persona change, no reload; barge-in works; targets measured and recorded.

## Phase K3: Waifu creator

- [ ] K3-01 Form shell with name, slug, validation messages (FR-CR-1)
- [ ] K3-02 VRM upload, validation, live preview, auto-frame (FR-CR-2)
- [ ] K3-03 Voice upload, clip checks, auto-transcript, language detect, Test voice (FR-CR-3)
- [ ] K3-04 Traits chips and instruction block with Copy (FR-CR-4, 5; Appendix A)
- [ ] K3-05 Paste-only prompt box with validation and token count (FR-CR-5, 6)
- [ ] K3-06 Test chat, Save, atomic pack creation, delete flow (FR-CR-7, 8; FR-W-2, 5)
- **Gate K3:** a new waifu created end-to-end with no file touched; she speaks in her own voice.

## Phase K4: Desktop pets

- [ ] K4-01 Spike: single overlay per monitor with alpha hit-testing vs one window per pet; record result in `DECISIONS.md` (D-014)
- [ ] K4-02 Baker: VRMA clips (idle, sit, walk) or procedural → atlas in `pet/` (FR-P-2)
- [ ] K4-03 Overlay window, sprite player, state machine (FR-P-3, 4)
- [ ] K4-04 Click, drag, quick-reply, speech bubble, right-click menu; speaks through the arbiter (FR-P-5)
- [ ] K4-05 Lifecycle with tray, 1 to 3 pets, overhead measurement (FR-P-1, 6)
- **Gate K4:** two pets idle and walk for an hour; overhead measured; user sign-off.

## Phase K5: 3D mode

- [ ] K5-01 Port Luna's sandbox into the engine: room, camera, wandering
- [ ] K5-02 Scene pack loader, WASD + pointer lock + colliders, scene switcher (FR-3D-1, 2)
- [ ] K5-03 Apartment and garden scenes within budget (FR-3D-6)
- [ ] K5-04 Bring in one or two waifus; anchors, waypoints, face/approach behaviour; `scene_state` (FR-3D-3)
- [ ] K5-05 Two-waifu turn arbiter with per-speaker prompts (FR-3D-4)
- [ ] K5-06 Voice and text overlay in 3D (FR-3D-5)
- **Gate K5:** walk, switch scene, talk to two waifus with no persona bleed; fps recorded.

## Phase K6: Hardening

- [ ] K6-01 Calibrate all NFR targets and fix misses (SPEC §4)
- [ ] K6-02 Crash recovery and graceful shutdown tests (SPEC §4.2)
- [ ] K6-03 Soak test (several hours, mixed use); log findings
- [ ] K6-04 Docs pass: README quickstart verified from a clean clone
- **Gate K6:** soak test clean; docs verified.

## Phase K7: Windows packaging (planned)

- [ ] K7-01 Freeze the kernel (PyInstaller or embedded Python) as a Tauri sidecar; Job Object still works
- [ ] K7-02 Tauri bundler: NSIS installer, WebView2 bootstrapper, icons, version stamping
- [ ] K7-03 Resource resolver for built-in scenes/templates; verify the app works with the repo absent
- [ ] K7-04 First-run checklist (Doctor) for Ollama, models, TTS backend, key
- [ ] K7-05 Portable bundle: zip + `setup.ps1` + README setup instructions
- [ ] K7-06 `docs/THIRD-PARTY.md` complete; SHA-256 checksums; release notes
- [ ] K7-07 Test on a clean Windows machine/VM; decide on code signing (unsigned builds trigger SmartScreen warnings)
- **Gate K7:** clean-machine install runs the app and the Doctor guides the user to a working setup.

## Deferred

- **D1 Agent mode** (`SCOPE.md` §12): workspace grant, permission levels, diffs, backups, audit, no shell at first.
- **D2 VR:** WebXR spike (WebView2 vs browser page) once a headset is available.

## Backlog (parked, not approved)

- Waifu export/import as a single file
- Selectable stage backdrops and lighting presets
- Collapsible *Thoughts* block for reasoning models
- Emotion detection driving expressions
- Proactive messages / idle behaviours
- Multi-monitor pets
- Auto-update
- Per-waifu private memory (option; contradicts D-005 today)
