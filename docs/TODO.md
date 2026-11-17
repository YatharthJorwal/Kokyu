# TODO — Kōkyū

The forward plan. Work top to bottom inside the current phase, one item at a time; tick an item with its commit hash. A phase ends with one **checkpoint**, run in the desktop app with a real model and ticked by the user (D-076). Requirement IDs refer to `SPEC.md`; decisions to `DECISIONS.md`.

Last updated: 2026-11-17 (session 5: docs reset, D-076 to D-085).

## Phase order (D-085, amended by D-086; provisional)

| Phase | Goal | Release | Status |
|---|---|---|---|
| K0 | Skeleton: companion packs, shared memory, invariance | 1.0 | Done (`0cd2d20..ba7c2a3`) |
| K1 | Chat app: threads, model picker, effort, API endpoint, VRAM checks, failure cards, settings | 1.0 | Done (`5deb6b6..89bdb95`) |
| K1c | Conversation modes: Chat and Roleplay, story memory, scenario cards (D-074, D-075) | 1.0 | Done (`470a05e..2b99262`); the user ran it on their PC 2026-11-17 |
| Docs | Docs reset (D-076) | n/a | Done (`5e82558`) |
| **UI-1** | **Chat app polish: names, working controls, behaviour (D-084, D-082)** | 1.0 | **In progress** |
| UI-2 | Design standard: references first, then DESIGN.md, then build (D-086) | 1.0 | Not started |
| K1b | Installer walking skeleton, time-boxed | 1.0 | Not started |
| K2 | Stage view, voice providers, voice input | 1.0 | Not started |
| K3 | Companion creator (D-077) | 1.0 | Not started |
| W | First run with automatic setup (D-080) | 1.0 | Not started |
| K6 | Hardening | 1.0 | Not started |
| K7 | Release engineering | 1.0 | Not started |
| K4 | Desktop pets | 1.1 | Not started |
| K5 | 3D apartment (D-078) | 1.1 | Not started |

Not planned: agent mode. Deferred long term: VR (D-079).

## Now

- [x] Docs reset (D-076) `5e82558`: SCOPE, PRODUCT, README, SPEC v1.1, ARCHITECTURE, DECISIONS compacted, CLAUDE.md, RULES, TODO, STATE, HANDOFF; old notes in `docs/archive/`
- [ ] C-1b Delete `KASANE/vrm/` (the user): byte-identical copies of the pack VRMs, read by nothing
- [ ] The open questions in `DECISIONS.md` (the user will come back to them)

## Phase UI-1: Chat app polish

Goal: a chat app that feels finished, not a localhost shell. Each item is one commit with screenshots at 900×600 and 1440×900 in every theme. New dependencies get a decision and a `THIRD-PARTY.md` row first.

- [x] UI1-01 Model names (D-084, FR-M-12) `883f4f7`: kernel `router/names.py` (override, preset label, derivation, collisions get the quant) with a pytest row per example; rows carry `label`, `full` and `detail` (the facts; no separate `facts` field); the chip, picker, loading card, VRAM messages and "Sent to" use them; muted full id and facts on hover or focus (a card on the chip, a strip in the picker). `shortRef` kept only as the fallback before the list arrives
- [x] UI1-02 Only working controls and plain words (D-082) `a412120`, `c575b72`: the mic, the "soon" tray items and New waifu removed; no phase codes, "kernel" or "waifu" in UI text; the sidebar status line replaced by a banner after 6 s offline, whose Reconnect restarts a stopped engine (shell `restart_kernel`)
- [x] UI1-03 Unpriced models under the cap (D-083) `3e552e7`: they run, uncounted; the picker says "price unknown" (detail: "price unknown, not counted against the cap"); a notice once per model per run (in memory, so it returns after a restart); a reached cap still stops them; `budget.on_exhausted` removed
- [x] UI1-06 Her face (D-091, FR-W-8) `04e0296`: the engine reads the VRM thumbnail, scales it down, serves `/waifus/<id>/portrait`; her initial when there is none; the portrait in the companion chip, the conversation list and her messages
- [x] UI1-06b Her profile (D-091, FR-W-9) `e62374f`: portrait, name, traits, About (packs gain `about`; `build_premade.py` keeps it), a Chat button; *Change picture* (stored in the app data folder) and *Use the model's face*
- [ ] UI1-07 Message list: grouped by speaker, a hover action bar with icons, time and model on hover, no jump to the bottom while reading plus a jump-to-latest pill, the thinking state where the reply appears, a streaming caret, edit and resend of the last message
- [ ] UI1-08 Markdown: tables, nested lists, highlighted code with a header and copy
- [ ] UI1-09 Shell: one slim header (portrait chip, thread title, Temp toggle, window buttons), a split New button (Chat / Roleplay…), a sidebar context menu and pinning, an empty state with her face and starter chips, toasts, in-app confirms instead of `window.confirm`
- [ ] UI1-10 Keyboard: Ctrl+N, Ctrl+K palette, Ctrl+comma, Esc stops a reply
- **Checkpoint UI-1:** the user uses the app for a while in the desktop window with a local model and signs off the look.

## Phase UI-2: Design standard (D-086)

Planned before it is built: no code until the user agrees `DESIGN.md`. UI-1's items get their final look here.

- [ ] UI2-01 References: the user and Claude collect apps and screens to follow (chat apps, character apps, what to avoid) into `docs/reference-images/`, each with a note on what to take from it (open question 1)
- [ ] UI2-02 `docs/DESIGN.md` agreed: colour roles, a type scale with nothing under 12 px, a 4 px spacing scale, one bundled UI font, radii, motion, focus rings, light and dark, the copy rule (FR-C-4); a mock of the main window before code
- [ ] UI2-03 Tokens in code; no white flash at startup
- [ ] UI2-04 Primitives: tooltip, popover, dialog and menus on a headless library (proposed: Radix) and one icon set (proposed: lucide) replacing the emoji and text glyphs; decision first
- [ ] UI2-05 Apply to every surface: shell, sidebar, message list, composer, picker, settings, dialogs; before and after screenshots in `STATE.md`

## Phase K1b: Installer walking skeleton (D-035, D-081), time-boxed to about two sessions

- [ ] K1b-01 Kernel packaging spike: PyInstaller one-folder vs embedded CPython (size, antivirus, updates) (`ARCHITECTURE.md` packaging questions)
- [ ] K1b-02 Tauri per-user NSIS `.exe`, WebView2 bootstrapper, kernel as a sidecar named `kasane.exe`, data in `%APPDATA%\Kokyu` (D-081, D-089)
- [ ] K1b-03 Clean Windows VM (no Python, Node, Rust, Git): install, launch, a chat (local model, or an API key once there is one), uninstall
- [ ] K1b-04 Record antivirus/SmartScreen behaviour, size and install time in `STATE.md`
- **Checkpoint K1b:** a clean-machine install reaches a working chat; the packaging approach is a decision.

## Phase K2: Stage and voice

- [ ] K2-01 Stage view: auto-framing, backdrop, spring bones, idle motion, look-at, expression hooks (FR-ST-1..3, 5, 7)
- [ ] K2-02 Lip-sync from played audio; captions; docked input; chat log slide-over; Chat | Stage toggle in the top bar (FR-ST-3, 4, FR-C-7, FR-S-4)
- [ ] K2-03 The 1.0 voice for buyers (open question 2): a voice provider interface and a small `builtin` voice spike (licence, quality, CPU latency) (FR-VP-1, 5; D-036)
- [ ] K2-04 Speech-safe normalizer, clause pipelining, arbiter, barge-in (FR-V-2..5)
- [ ] K2-05 TTS pre-warm on switch (FR-S-3); a "voice warming up" state for the 47 s cold start; TTS-down banner (FR-V-7)
- [ ] K2-06 `elevenlabs` provider: voice ID plus key, cloud badge, opt-in (FR-VP-3)
- [ ] K2-07 Voice input: faster-whisper on CPU, VAD, push-to-talk, the mic button appears here (FR-V-6, D-082); keep STT off the asyncio loop
- [ ] K2-08 Camera and paste-image into the tray as working items (FR-C-4, FR-R-3, 4)
- [ ] K2-09 Live (Stage plus voice) per window, from the modes work (FR-MODE-10)
- [ ] K2-10 Measure latency and fps targets (FR-V-8, FR-ST-6); record in `STATE.md`
- **Checkpoint K2:** switch companions mid-conversation on the stage; voice and persona change without a reload; barge-in works; targets recorded.

## Phase K3: Companion creator (D-077, D-087)

A step-by-step panel with simple instructions; the user brings their own keys, models and files.

- [ ] K3-01 Form: name, slug, validation messages (FR-CR-1)
- [ ] K3-02 VRM upload, validation, live preview, auto-frame (FR-CR-2)
- [ ] K3-03 Voice: clip upload and checks, auto-transcript, language detect, Test voice (FR-CR-3); the builtin-voice picker once K2-03 decides it
- [ ] K3-04 Traits, then **Write it for me**: the persona instruction (SPEC Appendix A) through `router.decide()` with the selected model (FR-CR-4, 5)
- [ ] K3-05 An editable persona box with validation and token count; Copy instruction as an extra (FR-CR-5, 6)
- [ ] K3-06 Test chat, Save, atomic pack creation, delete flow (FR-CR-7, 8; FR-W-2, 5)
- **Checkpoint K3:** a new companion created end to end with no file touched; she speaks in her own voice.

## Phase W: First run and automatic setup (D-080)

- [ ] W-01 Setup modules with pinned manifests (URLs, SHA-256, sizes, versions), progress, cancel and resume: GPT-SoVITS and the STT model, run at first start (FR-COMP)
- [ ] W-02 Ollama through its official installer; model pull with progress
- [ ] W-03 Doctor checks grow fix actions (open the installer, start, retry) (FR-COMP-4, 5)
- [ ] W-04 First run: model or key (with Test key), companion (premade or create), setup, first conversation (FR-WIZ)
- [ ] W-05 Premade companions as built-in read-only packs (D-039; open questions 3 and 4)
- [ ] W-06 Age check as the first step of the first run; under 18 stops (FR-WIZ-8, D-090)
- **Checkpoint W:** on a clean machine, installer to first reply on the API path and on the local path; voice set up with no terminal; every failure shows a plain message.

## Phase K6: Hardening

- [ ] K6-01 Calibrate the NFR targets and fix misses (SPEC §4)
- [ ] K6-02 Crash recovery and graceful shutdown tests (SPEC §4.2)
- [ ] K6-03 Soak test (several hours, mixed use)
- [ ] K6-04 README quickstart verified from a clean clone
- **Checkpoint K6:** soak clean; docs verified.

## Phase K7: Release engineering (1.0)

- [ ] K7-01 Productionize K1b packaging; resource resolver for built-in packs and templates; verified with the repo absent
- [ ] K7-02 Code signing; SmartScreen behaviour recorded (Track B)
- [ ] K7-03 Updater: signed updates, static manifest, "update available" (FR-DIST-7)
- [ ] K7-04 Licence key check with the payment provider's keys (FR-DIST-10)
- [ ] K7-05 Export diagnostics (FR-DIST-8)
- [ ] K7-06 `THIRD-PARTY.md` complete including asset rights; checksums; release notes
- [ ] K7-07 A tagged release builds the installer in CI; clean-VM install test
- [ ] K7-08 The kernel port as a setting (hard-coded in several places today; `ARCHITECTURE.md` §12)
- [ ] K7-09 Premade assets in an app-only packed format the engine reads; no export path in the UI; the licence forbids extraction (D-087)
- **Checkpoint K7:** a signed installer from a tagged release installs on a clean machine, completes the first run, updates to the next tag, exports diagnostics.

## Phase K4: Desktop pets (1.1)

- [ ] K4-01 Spike: one overlay per monitor with alpha hit-testing vs one window per pet (hit-testing starts from zero)
- [ ] K4-02 Baker: VRMA clips (idle, sit, walk) to a sprite atlas (FR-P-2)
- [ ] K4-03 Overlay window, sprite player, state machine (FR-P-3, 4)
- [ ] K4-04 Click, drag, quick reply, speech bubble, right-click menu (FR-P-5)
- [ ] K4-05 Tray lifecycle, 1 to 3 pets, overhead measured (FR-P-1, 6)
- **Checkpoint K4:** two pets idle and walk for an hour; overhead measured.

## Phase K5: 3D apartment (1.1, D-078)

- [ ] K5-01 Port Luna's apartment: a prebuilt GLB room as a user asset, BVH collision, spectator and first-person visitor cameras (WASD, pointer lock), her wandering with walk clips, time-of-day lighting (FR-3D)
- [ ] K5-02 Real room and anchor data (Luna's floorplan is a placeholder rectangle)
- [ ] K5-03 A room that can ship: asset rights recorded (R-51)
- [ ] K5-04 Voice and text overlay in 3D; VRAM measured beside the LLM and TTS
- [ ] K5-05 Design two-companion scenes before building them: who speaks next, both reacting to what the user says
- **Checkpoint K5:** walk the apartment and talk to her; fps and VRAM recorded.

## Track B: business (the user's, deferred, D-043)

- [ ] B-2 Price and trial
- [ ] B-3 Payment provider: acceptable-use rules for a companion and roleplay app; Merchant of Record (open question 3)
- [ ] B-4 Name and domain check
- [ ] B-5 Premade companions with written rights (D-039)
- [ ] B-6 Code-signing options and cost
- [ ] B-7 Website, checkout, downloads, support
- [ ] B-8 Privacy policy, terms (audience age), refunds
- [x] B-9 Research for D-088: age-rating norms, laws, payment-provider rules, age-gate options; report `docs/research-age-content-2026-11.md`; the user chose 18+ (D-090)
- [ ] B-10 Premade personas explicit or not (open question 3); then ask Paddle and FastSpring in writing whether they accept the app as described (Lemon Squeezy is closing, Gumroad bans chatbots)
- [ ] B-11 UK: ask Ofcom's checker whether a local-only app is in scope of the Online Safety Act; block UK sales until then
- [ ] B-12 A lawyer's read on California SB 243 (and New York's companion law) for a bring-your-own-model desktop app: AI disclosure, crisis referral
- [ ] B-9 Marketing plan

## Backlog (parked, not approved)

- K1c follow-ups (D-075), none blocking:
  - a reply quoted only with U+201D speaks its narration;
  - a screen remark partly spoken is dropped if the thread changes during speech;
  - a story fold cut by the token cap is not detected;
  - a scenario save pending over a disconnect stays "Saving…";
  - no test for Escape in the delete confirm;
  - a fold may start before `load_thread`'s model request;
  - Temp Chat lines in a roleplay can be folded into its summary;
  - `thread_list` sends full cards on every refresh.
- Companion export/import as one file
- Stage backdrops and lighting presets
- A collapsible *Thoughts* block for reasoning models
- Emotion detection driving expressions
- Proactive messages and idle behaviours
- Multi-monitor pets
- Per-companion private memory (an option; contradicts D-005 today)
- Remember the last-used companion in `settings.json` instead of `data/active_waifu.txt`
