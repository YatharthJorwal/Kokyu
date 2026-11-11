# TODO — Kōkyū

Phased plan with gates. Work **top to bottom inside the current phase**, one item at a time. Tick items with the commit hash: `- [x] K0-03 … (a1b2c3d)`. Do not start the next phase until its gate passed **and** the user approved (R-32). Requirement IDs refer to `SPEC.md`.

Last updated: 2026-11-11 (session 0, docs only).

## Phase overview

| Phase | Goal | Status |
|---|---|---|
| Docs | Spec set, license, README | **Done** (session 0), awaiting first commit |
| **T** | Headless GPT-SoVITS backend by a CLI agent (parallel track) | Not started |
| **K0** | Skeleton: seed from Yuri, waifu pack, shared memory, invariance | **Next** |
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
- [ ] DOC-1 User reviews the docs and corrects anything wrong (assumptions listed in `SCOPE.md` §13 and `HANDOFF.md`)
- [ ] DOC-2 User makes the first commit to `main` (the repo is currently empty)

## Track T: TTS backend (parallel, separate agent) — brief: `TTS-BACKEND.md`

- [ ] T-1 Choose the install folder outside the repo; do not modify the old cluttered GPT-SoVITS folder
- [ ] T-2 Clean install of the newest stable GPT-SoVITS with zero-shot support; own venv; CUDA build matching the RTX 3060; record version/commit
- [ ] T-3 Headless API server, no WebUI, bound to 127.0.0.1, port configurable
- [ ] T-4 `start` and `stop` scripts, plus a health check
- [ ] T-5 `smoke_test` script: same sentence with two different reference clips back-to-back, no restart, prints latency per call
- [ ] T-6 English `INSTALL.md` and `README.md` in the backend folder; record exact API parameters actually accepted
- [ ] T-7 Measure VRAM use while idle and while synthesizing; report to the user (feeds `ARCHITECTURE.md` §13)
- **Gate T:** smoke test passes on this machine; parameters and VRAM numbers recorded in `STATE.md`.

## Phase K0: Skeleton (starts after DOC-2)

Goal: a running kernel and shell seeded from Yuri where a **waifu is a pack** and switching her changes only persona and voice.

- [ ] K0-00 Verify the environment: Node 18+, Rust stable, Python 3.11+, WebView2, `ollama list`; record in `STATE.md`
- [ ] K0-01 Confirm the docs are committed; create branch `k0-skeleton`
- [ ] K0-02 Read Yuri's `docs/` (SCOPE, ROUTING, PHASES, DECISIONS, handoff) and Luna's `CLAUDE.md`. Write `docs/notes/yuri-inventory.md`: where the heart animation, audio arbiter, router, bus events, WebSocket message names and speech-safe module live. Reconcile `ARCHITECTURE.md` §5 with the real protocol
- [ ] K0-03 Copy Yuri (no `.git`, no docs, no user assets) at a chosen commit; record the hash in `DECISIONS.md` D-002 and `STATE.md`
- [ ] K0-04 Rebrand and rename: `orchestrator/` → `kasane/`, product name Kōkyū, identifier `io.github.yatharthjorwal.kokyu` (D-021), window title, tray, default port 8780
- [ ] K0-05 Add `kasane/paths.py` (dev `./data`, packaged `%APPDATA%\Kokyu`) and replace every hard-coded path
- [ ] K0-06 Config schema v3: remove persona-specific model/tool keys; add `waifus`, `ui`, `tts.backend`; update `config.example.yaml`, add `models.example.yaml`
- [ ] K0-07 Waifu pack: pydantic model for `waifu.yaml` (FR-W-1, 4, 6), loader, validator, registry with hot-reload, unit tests
- [ ] K0-08 `scripts/seed_waifus.py`: import Luna and Yuri personas into packs (prompt text from their persona files; the user supplies VRM and ref-wav paths); create `docs/THIRD-PARTY.md` with the seeded dependencies
- [ ] K0-09 Threads store (SQLite, `threads.db`) with `active_waifu_id`; `switch_waifu` event and divider message
- [ ] K0-10 Prompt assembly (persona prompt + shared app addendum + recall block) with unit tests (ARCHITECTURE §4.1)
- [ ] K0-11 TTS adapter to the contract: per-request ref clip/text/lang, pre-warm, backend-down error, tests against a fake server; `pyttsx3` as opt-in dev fallback (FR-V-1, 7)
- [ ] K0-12 Memory: confirm it is not namespaced; message and episode summaries name the speaking waifu (FR-MEM-1..3); tests
- [ ] K0-13 **Invariance tests** (FR-W-3, FR-S-5): two fixture waifus; identical router decision, effort, tool set and recall for the same input; only prompt and TTS parameters differ
- [ ] K0-14 Router role scaffolding: `decide()` with roles and the local-only refusal (FR-R-1, 3) and tests
- [ ] K0-15 Temporary waifu dropdown on the existing shell (the real UI is K1), with a debug HUD showing prompt id, voice params, model
- [ ] K0-16 `npm run check` aggregate script; make `npm run check` and `pytest` green
- [ ] K0-17 Update `STATE.md`, `HANDOFF.md`, `TODO.md`, `DECISIONS.md`; run the gate review
- **Gate K0 (automated):** invariance tests green; switching Luna ↔ Yuri changes only prompt text and TTS parameters (asserted); `npm run check` + `pytest` green.
- **Gate K0 (manual, needs Track T):** audibly different voices for the two waifus with no restart. If T is not done, record "voice not audibly verified" in `STATE.md`.

## Phase K1: Chat shell

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
