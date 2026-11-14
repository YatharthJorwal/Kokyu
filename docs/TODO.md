# TODO — Kōkyū

Phased plan with gates. Work **top to bottom inside the current phase**, one item at a time. Tick items with the commit hash: `- [x] K0-03 … (a1b2c3d)`. Do not start the next phase until its gate passed **and** the user approved (R-32). Requirement IDs refer to `SPEC.md`.

Last updated: 2026-11-11 (session 1, docs only: inventory and corrections).

## Phase overview

Execution order (D-034): T (parallel), K0, K1, K1b, K2, K3, W, K6, K7, then K4 and K5. IDs are stable labels, not the order.

| Phase | Goal | Release | Status |
|---|---|---|---|
| Docs | Spec set, README, product direction | n/a | Done; session-1 bundle pending merge |
| ~~LIC-1~~ | License decided: proprietary (D-040) | done | **Done** |
| **T** | GPT-SoVITS component recipe by a CLI agent (parallel track) | 1.0 | Not started |
| **K0** | Skeleton: seed from Yuri, waifu pack, shared memory, invariance (rescoped, D-026) | 1.0 | **Code complete; waiting for the manual gate on the PC** (session 2) |
| K1 | Chat shell, waifu switcher, model switcher, API providers | 1.0 | Not started |
| **K1b** | Installer walking skeleton on a clean machine (D-035) | 1.0 | Not started |
| K2 | Stage view, voice providers, senses | 1.0 | Not started |
| K3 | In-app waifu creator | 1.0 | Not started |
| **W** | Component manager and Welcome wizard | 1.0 | Not started |
| K6 | Hardening | 1.0 | Not started |
| K7 | Release engineering: signing, updater, license key, diagnostics, CI | 1.0 | Not started |
| K4 | Desktop pets | 1.1 | Not started |
| K5 | 3D mode | 1.1 | Not started |
| D1, D2 | Agent mode, VR | 2.x | Deferred |

---

## Docs (session 0)

- [x] Scope v0.3, SPEC, ARCHITECTURE, RULES, DECISIONS, STATE, HANDOFF, TODO, TTS brief, README, LICENSE, `.gitignore`
- [x] DOC-1 User reviewed the docs (confirmed: shared memory, name Kōkyū, KASANE folder stays uppercase)
- [x] DOC-2 First commit pushed to `main` (`704c05d`)
- [x] LIC-1 License decided: proprietary, not open source (D-040)
- [x] PROD-1 Product direction and spec finalized as the baseline (D-044)

## Track T: TTS backend (parallel, separate agent) — brief: `TTS-BACKEND.md`

- [ ] T-1 Choose the install folder outside the repo; do not modify the old cluttered GPT-SoVITS folder
- [ ] T-2 Clean install of the newest stable GPT-SoVITS with zero-shot support; own venv; CUDA build matching the RTX 3060; record version/commit
- [ ] T-3 Headless API server, no WebUI, bound to 127.0.0.1, port configurable
- [ ] T-4 `start` and `stop` scripts, plus a health check
- [ ] T-5 `smoke_test` script: same sentence with two different reference clips back-to-back, no restart, prints latency per call
- [ ] T-6 English `INSTALL.md` and `README.md` in the backend folder; record exact API parameters actually accepted
- [ ] T-7 Measure VRAM use while idle and while synthesizing; report to the user (feeds `ARCHITECTURE.md` §13)
- [ ] T-8 `component.json` manifest so Kōkyū's component manager can reproduce the install: URLs, versions, SHA-256, sizes, Python/CUDA versions, start command, health URL, hardware requirements; the install must be scriptable and non-interactive
- **Gate T:** smoke test passes on this machine; parameters and VRAM numbers recorded in `STATE.md`.

## Track B: business and content (non-code, user-owned): DEFERRED (D-043)

Dodo Payments, website, pricing and release work come after the product is developed. Kept here so nothing is forgotten.

- [x] B-1 License decided (D-040)
- [ ] B-2 Price and free-trial policy (demo limits)
- [ ] B-3 Dodo Payments account; **read its acceptable-use and prohibited-business rules** against a companion product; confirm whether it is the Merchant of Record for VAT/sales tax
- [ ] B-4 Name and domain check for "Kokyu" / "Kōkyū" (basic trademark search)
- [ ] B-5 Premade companions: commission or create 2 to 3 VRMs and original voices with written rights (D-039)
- [ ] B-6 Code-signing options and cost (individual publisher eligibility)
- [ ] B-7 Website (separate repo): landing, screenshots, checkout, downloads, docs, support
- [ ] B-8 Privacy policy, terms (including intended audience age), refund policy, support channel
- [ ] B-9 Marketing plan (kept out of engineering docs; see the IP caution in `PRODUCT.md` §6)

## Phase K0: Skeleton (rescoped in session 1, D-026)

Goal: a running kernel and shell seeded from Yuri where **a waifu is a pack** and switching her changes only persona and voice. Everything marked "sandbox" can be verified by Claude (pytest, `test:fe`, `tsc`, `vite build`); everything touching Rust, a window, audio or a model needs the user (manual gate).

- [x] K0-00 Environment: sandbox baseline verified (Yuri: 641 pytest, 65 frontend, tsc, vite build). **User machine still unverified:** run the command block in `HANDOFF.md` §5 and paste the output into `STATE.md` §2
- [x] K0-01 Docs committed and pushed (`704c05d`)
- [x] K0-02 Yuri and Luna inventory: `docs/notes/yuri-inventory.md`; `ARCHITECTURE.md` §2, 3, 4.1, 5, 7.1, 9.1, 11 corrected; D-024 to D-031 recorded
- [x] K0-03 Seed commit: copy Yuri at `e32af4f` **verbatim** (excluded as in D-028); tests green in the sandbox as seeded (0cd2d20)
- [x] K0-04 Rename and rebrand in small reviewed steps (no bulk replace): `orchestrator/` → `KASANE/` (`git mv`), `conftest.py`, scripts, Rust paths; product name Kokyu, identifier `io.github.yatharthjorwal.kokyu`, window title, tray text, `YURI_*` → `KOKYU_*`, log prefixes, npm package name; kernel port 8765 → 8780 in Python, Rust, `ws-client.ts`; no hard-coded ports left in Rust (8a61fcd)
- [x] K0-05 `KASANE/paths.py` (dev `./data`, packaged `%APPDATA%\Kokyu`); replace `repo_path("data/…")` and other hard-coded locations; tests (cae608a)
- [x] K0-06 Config v3: strip machine paths from the example, move the TTS reference clip and transcript out of config (they become waifu data), add `waifus.dir` and `kernel.port`, TTS block becomes `tts.backend` (URL plus optional launch); update `config.example.yaml`; add `models.example.yaml` Done as: machine paths removed from code defaults and the example, legacy clip keys emptied; the waifu directory comes from `paths.py` and the kernel port stays the constant `PORT` in `app.py` (a `kernel.port` config key moved to the backlog). (4963246)
- [x] K0-07 `KASANE/waifus/`: pydantic model for `waifu.yaml` (FR-W-1, 4, 6), loader, validator, registry; unit tests (fda24ad)
- [x] K0-08 Persona as data (D-031): split Yuri's `SYSTEM_PROMPT` into personality (waifu prompt) and shared app addendum (emotion tags, speech rules); `scripts/seed_waifus.py` imports the Luna and Yuri prompts from paths the user supplies and writes `data/waifus/<id>/`; create `docs/THIRD-PARTY.md` Done as: premade packs are built by `scripts/build_premade.py` from the user's files; the persona prompts are copied **verbatim** and the emotion-tag rule lives in the shared addendum instead of splitting Yuri's prompt (D-045). `docs/THIRD-PARTY.md` created. (470c947)
- [x] K0-09 Active waifu in the existing single-history flow: per-connection active waifu; `switch_waifu` and `waifu_state` messages (`ARCHITECTURE.md` §5.2); system prompt swapped on switch; history kept (28f7f9e)
- [x] K0-10 `KASANE/prompting.py`: system assembly (persona + addendum), ephemeral blocks unchanged; unit tests (28f7f9e)
- [x] K0-11 TTS per waifu: `tts.synthesize(text, voice)` with the waifu's reference clip, transcript and language; backend URL from config; pre-warm; **pyttsx3 fallback off by default** (FR-V-7); typed error when the backend is down; tests with a fake server (4963246)
- [x] K0-12 Shared memory with speakers (FR-MEM-1, 2): `transcript_log` gains a speaker column through `memory/migrate.py`; `add_transcript_turn(..., speaker=)`; writer prompt and episode summaries name the waifu; migration and writer tests (65de8d5)
- [x] K0-13 **Invariance tests** (FR-W-3, FR-S-5): two fixture waifus; the `ModelRequest` messages differ only in the persona prompt; same role and model decision, same recall results, same tool schemas offered; only prompt and TTS parameters differ (28f7f9e)
- [x] K0-14 Map the existing local-only router tests to FR-R-3 (no behaviour change); add one test that no waifu field reaches `router.route` Done as structural guards: no waifu input in `router.decide`, `Router.complete`, `stream_with_tools` or `ModelRequest`; Yuri's existing role-pinning tests cover FR-R-3. (28f7f9e)
- [x] K0-15 Temporary waifu dropdown in the existing widget's quick-action menu, with a one-line debug readout (waifu, voice clip, model); no layout redesign (that is K1) Done as: Companion `<select>` in the quick-action menu, avatar swapped by one reload per switch (temporary until the K2 stage rework, D-046). (0a23332)
- [x] K0-16 `scripts/check.mjs` and `npm run check` (tsc, test:fe, build, cargo check, pytest; cargo skippable with a flag); green in the sandbox (ba7c2a3)
- [x] K0-17 Update `STATE`, `HANDOFF`, `TODO`, `DECISIONS` (this commit); the gate review is the user's manual checks below
- **Gate K0 (sandbox, automated): PASSED 2026-11-12** (pytest 718, test:fe 76, tsc, vite build; a real kernel plus websocket smoke test also passed).
- *Original wording:* invariance tests green; switching Luna ↔ Yuri changes only the persona prompt and TTS parameters (asserted); `pytest` + `test:fe` + `tsc` + `vite build` green.
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
- [ ] K1-08b Generic `openai_compat` provider (base URL plus key; AI Router, OpenRouter, DeepSeek presets); end-user keys in the Windows Credential Manager through the shell (D-037, FR-R-6)
- [ ] K1-09 VRAM manager v1 (NVML), exclusivity across backends, fits hints, load errors (FR-M-6, ARCHITECTURE §7.3)
- [ ] K1-10 Model chip + popover (search, Local/API sections, badges, footer meters) (FR-M-1, 2, 5, 7)
- [ ] K1-11 Effort slider with animation and reduced-motion fallback (FR-M-8, 9, 11)
- [ ] K1-12 Inline API failure UX with Retry / Switch model (FR-R-5)
- [ ] K1-13 Settings (FR-SET-1, 2), Doctor panel (FR-SET-3), Memory viewer (FR-MEM-4)
- [ ] K1-14 Tests, `STATE`/`HANDOFF` update
- **Gate K1:** chat with one local and one API model; change model, effort and waifu mid-thread independently; failure UX shown with a forced API error; user sign-off on the layout vs the reference.

## Phase K1b: Installer walking skeleton (D-035)

Goal: find packaging problems in week one of the product, not the last week.

- [ ] K1b-01 Choose the kernel packaging approach by spike: PyInstaller one-folder vs embedded CPython (size, antivirus behaviour, updateability) (`ARCHITECTURE.md` §11.1)
- [ ] K1b-02 Tauri bundle: NSIS per-user installer, WebView2 bootstrapper, kernel as sidecar or resources, data in `%APPDATA%\Kokyu`
- [ ] K1b-03 Test on a clean Windows machine or VM (no Python, Node, Rust, Git): install, launch, text chat with an API key, uninstall
- [ ] K1b-04 Record antivirus/SmartScreen behaviour, installer size and install time in `STATE.md`
- **Gate K1b:** a clean-machine install reaches a working API chat; findings recorded; packaging approach decided in `DECISIONS.md`.

## Phase K2: Stage and voice

- [ ] K2-01 Stage view: auto-framing, backdrop, spring bones, idle motion, look-at, expression hooks (FR-ST-1..3, 5, 7)
- [ ] K2-02 Lip-sync from played audio; captions; docked input; chat log slide-over; Chat | Stage toggle (FR-ST-3, 4, FR-C-7)
- [ ] K2-03 Sidebar waifu click → Stage, history click → Chat (FR-S-4)
- [ ] K2-04 Speech-safe normalizer, clause pipelining, arbiter, barge-in (FR-V-2..5)
- [ ] K2-05 TTS pre-warm on switch (FR-S-3); TTS-down banner (FR-V-7)
- [ ] K2-05b Voice provider interface; spike a small `builtin` voice (license, quality, CPU latency); make it the default provider (FR-VP-1, 5)
- [ ] K2-05c `elevenlabs` provider: voice ID plus key, cloud badge, opt-in (FR-VP-3)
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

## Phase W: Component manager and Welcome wizard (release 1.0)

- [ ] W-01 Component interface and states in the kernel; manifests under `components/` (FR-COMP-1, ARCHITECTURE §15)
- [ ] W-02 Ollama: detect, guided install (silent mode tested), model pull with progress
- [ ] W-03 llama.cpp server download and start; STT model download with progress
- [ ] W-04 GPT-SoVITS component from Track T's manifest (advanced, hardware-gated)
- [ ] W-05 Doctor panel as the component UI with plain-language fixes (FR-COMP-4, 5)
- [ ] W-06 Welcome wizard: hardware check, API-key step with Test key, model, voice, companion (premade or create), first conversation (FR-WIZ-1..6)
- [ ] W-07 Premade companions as built-in read-only packs (D-039)
- **Gate W:** on a clean machine, installer to first reply on the API path, measured against FR-WIZ-7; the local path completes with guided installs; every failure shows a plain message.

## Phase K4: Desktop pets (release 1.1)

- [ ] K4-01 Spike: single overlay per monitor with alpha hit-testing vs one window per pet; record result in `DECISIONS.md` (D-014)
- [ ] K4-02 Baker: VRMA clips (idle, sit, walk) or procedural → atlas in `pet/` (FR-P-2)
- [ ] K4-03 Overlay window, sprite player, state machine (FR-P-3, 4)
- [ ] K4-04 Click, drag, quick-reply, speech bubble, right-click menu; speaks through the arbiter (FR-P-5)
- [ ] K4-05 Lifecycle with tray, 1 to 3 pets, overhead measurement (FR-P-1, 6)
- **Gate K4:** two pets idle and walk for an hour; overhead measured; user sign-off.

## Phase K5: 3D mode (release 1.1)

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

## Phase K7: Release engineering (release 1.0)

- [ ] K7-01 Productionize the K1b packaging; resource resolver for built-in scenes, templates and premade packs; verify with the repo absent
- [ ] K7-02 Code signing for the installer and the kernel; SmartScreen behaviour recorded (Track B-6)
- [ ] K7-03 Updater: signed updates, static manifest, "update available" UX (FR-DIST-7)
- [ ] K7-04 License key verification, per D-032 and the payment provider (FR-DIST-10)
- [ ] K7-05 Export diagnostics (FR-DIST-8)
- [ ] K7-06 `docs/THIRD-PARTY.md` complete including asset rights; SHA-256 checksums; release notes
- [ ] K7-07 GitHub Actions: tagged release builds the Windows installer; clean-VM install test (manual until automated)
- [ ] K7-08 Portable bundle with `setup.ps1` and README setup instructions as a fallback channel
- **Gate K7:** a signed installer from a tagged release installs on a clean machine, passes the wizard, updates to the next tag, and exports diagnostics.

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

- `kernel.port` as a config key (the port is the constant `PORT` in `KASANE/app.py`)
- Rename the Cargo package, binary and log file names (`yuri`, `orchestrator.log`) before packaging (K7)
- Persist the last-used companion in `settings.json` instead of `data/active_waifu.txt`
