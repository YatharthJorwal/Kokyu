# TODO — Kōkyū

The forward plan. Work top to bottom inside the current phase, one item at a time; tick an item with its commit hash. A phase ends with one **checkpoint**, run in the desktop app with a real model and ticked by the user (D-076). Requirement IDs refer to `SPEC.md`; decisions to `DECISIONS.md`.

Last updated: 2026-11-18 (session 7: UI1-15 and UI1-16, the c.ai-style message card and the roleplay story tray, D-100, D-101).

## Phase order (D-085, amended by D-086; provisional)

| Phase | Goal | Release | Status |
|---|---|---|---|
| K0 | Skeleton: companion packs, shared memory, invariance | 1.0 | Done (`0cd2d20..ba7c2a3`) |
| K1 | Chat app: threads, model picker, effort, API endpoint, VRAM checks, failure cards, settings | 1.0 | Done (`5deb6b6..89bdb95`) |
| K1c | Conversation modes: Chat and Roleplay, story memory, scenario cards (D-074, D-075) | 1.0 | Done (`470a05e..2b99262`); the user ran it on their PC 2026-11-17 |
| Docs | Docs reset (D-076) | n/a | Done (`5e82558`) |
| UI-1 | Chat app polish: names, working controls, behaviour (D-084, D-082) | 1.0 | Code-complete; the checkpoint is the user's |
| **UI-2** | **Design standard: the user's references, screen by screen (D-086, D-102)** | 1.0 | **In progress** |
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
- [ ] C-2 Back up the premades' VRM and WAV files off this PC (the user; D-118 proposes a release on the private repo), so a fresh clone can be built
- [ ] The open questions in `DECISIONS.md` (the user will come back to them)

## Phase UI-1: Chat app polish

Goal: a chat app that feels finished, not a localhost shell. Each item is one commit with screenshots at 900×600 and 1440×900 in every theme. New dependencies get a decision and a `THIRD-PARTY.md` row first.

- [x] UI1-01 Model names (D-084, FR-M-12) `883f4f7`: kernel `router/names.py` (override, preset label, derivation, collisions get the quant) with a pytest row per example; rows carry `label`, `full` and `detail` (the facts; no separate `facts` field); the chip, picker, loading card, VRAM messages and "Sent to" use them; muted full id and facts on hover or focus (a card on the chip, a strip in the picker). `shortRef` kept only as the fallback before the list arrives
- [x] UI1-02 Only working controls and plain words (D-082) `a412120`, `c575b72`: the mic, the "soon" tray items and New waifu removed; no phase codes, "kernel" or "waifu" in UI text; the sidebar status line replaced by a banner after 6 s offline, whose Reconnect restarts a stopped engine (shell `restart_kernel`)
- [x] UI1-03 Unpriced models under the cap (D-083) `3e552e7`: they run, uncounted; the picker says "price unknown" (detail: "price unknown, not counted against the cap"); a notice once per model per run (in memory, so it returns after a restart); a reached cap still stops them; `budget.on_exhausted` removed
- [x] UI1-06 Her face (D-091, FR-W-8) `04e0296`: the engine reads the VRM thumbnail, scales it down, serves `/waifus/<id>/portrait`; her initial when there is none; the portrait in the companion chip, the conversation list and her messages
- [x] UI1-06b Her profile (D-091, FR-W-9) `e62374f`: portrait, name, traits, About (packs gain `about`; `build_premade.py` keeps it), a Chat button; *Change picture* (stored in the app data folder) and *Use the model's face*
- [x] UI1-07 Message list (D-092, FR-C-9, FR-C-5) `0fac211`: grouped by speaker, a hover action bar with icons, time and model on hover, no jump to the bottom while reading plus a jump-to-latest pill, the thinking state where the reply appears, a streaming caret, edit and resend of the last message (`regenerate {text}`; a line with a file can't be edited)
- [x] UI1-08 Markdown (D-093, FR-C-8) `12af2b8`: tables, nested lists, highlighted code with a header and copy; in-house parser and highlighter, no dependency
- [x] UI1-09 Shell (D-094, FR-C-6) `cb24949`: one slim header (portrait chip, thread title, Temp toggle, window buttons), a split New button (Chat / Roleplay…), a sidebar context menu and pinning (`thread_pin`, schema 6), an empty state with her face and starter chips, toasts, in-app confirms instead of `window.confirm`
- [x] UI1-10 Keyboard (D-095) `77af8c0`: Ctrl+N, Ctrl+K palette, Ctrl+comma, Esc stops a reply
- [x] UI1-11 The user's notes of 2026-11-18 (D-096): Tauri crate and npm on 2.12 `514e5c6`; the effort slider dragged smoothly `3565673`; thinking beside her face with animated words, replies typed out, a compact loading strip `7203bb0`
- [x] UI1-12 The user's notes of 2026-11-18, part two (D-097): "Waifu-mode-engaging" back, one slow letter lift, no slider end dots, a soft ⋯ hover `88ae626`; emotion tags shown like actions (FR-C-8) `510d629`; `speakable(text, mode)`, fixed rules before TTS (FR-V-2) `1562135`; Read aloud replaces voice mode, kept in settings.json, her voice only while on, the starting chip (FR-V-9) `c29500e`; dictation, the mic button and F9 into the input box, Settings → Voice, PyAV capped below 19 (FR-V-6) `6a254cf`; docs `c7fd2e4`
- [x] UI1-13 Chat memory (D-098, FR-M-13; the user's task 10, relayed): a context-length slider per model under Effort, 8K doubling to the model's maximum, kept in settings.json; every Ollama request, the history budget and llama.cpp's `-c` follow it; the fit point from Ollama's `model_info` or the GGUF header, a warning past it that never blocks `b6e97c8`, `f9648b0`
- [x] UI1-14 A speaker on each of her messages reads it aloud on request, Read aloud on or off (D-099, FR-V-10) `d65feec`
- [x] UI1-15 A message's ⋯ card on the c.ai model (D-100): Copy, Edit, Rewind to here, Pin (roleplay only, FR-MODE-11), New chat from here; Regenerate with swipes under her latest reply; the speaker by her name (FR-V-10); the sidebar's hide button and All / Chats / Roleplays filter (FR-C-6, FR-C-9) `cd872b5`
- [x] UI1-16 A roleplay keeps its character (FR-S-1); the story tray, a book: History, New chat, Memory (FR-C-4, FR-MODE-12); the Read aloud switch says Off or On; D-100's review fixes (D-101) `9597652`
- [x] **Checkpoint UI-1** (2026-11-24): the user went through the app in the desktop window: "it seems working fine to me"

## Phase UI-2: Design standard (D-086)

Planned before it is built: no code until the user agrees `DESIGN.md`. UI-1's items get their final look here.

- [x] UI2-00 (`5a1c7ae`) The user's first references (D-102): Settings restyled to `settings-general.png` and `settings-models.png`; the chat title centred on the top bar
- [x] UI2-00b (`5e679a8`) Her pet (D-103; first numbered UI2-01 in 5e679a8's message): chibi her walking above the input box in chat and roleplay; the cat button; Settings → Pet with behaviour, size and Create pet (prompt, upload a 4×3 sheet, check the poses, save) (FR-P-1..4)
- [x] UI2-00d (`34b0aeb`, `52a3a3b`) The Stage, the user's "VR mode" (D-104): Yuri's shell, the Chat | Stage switch, captions, lip-sync from the played voice, her mood from the emotion tag (FR-ST-1..3, 5, 7; K2-01, most of K2-02); Create pet's Take her picture opens her model full-body or bust, turned with the mouse, to copy or save a see-through PNG. Not yet: the chat log slide-over (FR-ST-4), the frame-rate check (FR-ST-6)
- [x] UI2-00e (`fb8e7fa`) Pet, round two (D-107): she walks on the window's bottom, a step-synced walk, carried and dropped (held, fall, land); saved poses fit a box per kind; Make a new pet for any character. Upload limits and formats in the window and the kernel (D-106). Picking an Ollama model starts Ollama (D-105)
- [x] UI2-00f (`0611ebe`) Pet sizes (D-108): each pose drawn at its own size; the size checker matches her head to idle's; the picture viewer's note on the picture and Save as
- [x] UI2-00g (`0611ebe`) The cat button (D-109): blue while the pet is shown, greyed on the Stage, Pet settings on hover
- [x] UI2-00h (`9bd3a65`) Pet settings (D-110): the hover menu closes when used and is absent on the Stage; Switch character in Settings → Pet
- [x] UI2-00i (`f82cf8e`) The Stage caption from Yuri (D-111): words pop in with her voice, the said word glows; Caption glow in Appearance
- [x] UI2-00j (`c653031`) Readable accent text on any theme; her voice's starting and failed notes with Set up (D-112)
- [x] UI2-00k (`ff520be, 783e39b`) Round swatches, five more theme presets; the Stage speaks by default with paced, fading captions (D-113)
- [x] AUD-01 The repo audit's bugs fixed (D-114): `781cd84` turns, sends, regenerate, delete, memory passes; `af5b98a` shutdown and Host checks, stale PID, settings.json, voice, dictation, pet saves; `62ec66f` the window's turn, asides, Markdown speed, offline notice, links, focus, Esc, caps, labels; `38768de` decay, the profile card, looks, speech, smaller races
- [x] AUD-03 (`684eb1d`) The audit's lean items: `chunking.extract_ready_chunks` and its tests, `conversation.thread_summary`, `router._MODEL_FALLBACKS`, the duplicate `public/vrm-animations/vrma/` (608 KB per build). Kept on the user's word: `audio/voice.py`, `audio/vad.py`, `src/engine/mic-stream.ts` and the arbiter's barge-in states, groundwork for K2's push-to-talk and hands-free voice (FR-V-6)
- [x] UI2-00l The AI note under the message box in every mode (D-119, FR-C-11)
- [x] SAFE-01 The self-harm detector and crisis card (D-121, FR-C-12) `d730ee5`
- [x] SAFE-02 Calibrate the detector's meaning check against the real `nomic-embed-text` (0.80 / 0.10; `scripts/calibrate_safety.py`) (D-121) `35453c2`
- [ ] SAFE-03 The detector in more languages than English, before selling outside English-speaking countries (D-121)
- [x] UI2-00m (`cdaef1e`) The Stage's top-bar title overlapped the Chat | Stage switch: the top bar is three columns (D-124)
- [x] AUD-05 (`df15e25`, `cdaef1e`, `c831d19`) The second audit (D-122, D-123): access, keys, inputs, unused packages
- [x] FALL-01 (`69ec49e`) The fallback model, Ask me or Answer by itself; the Stage shows a failed turn; the cap message names the cap (D-125, FR-R-5)
- [x] API-01 (`69ec49e`) The picker lists the API models chosen in Settings: popular sets, a checklist with Select all (D-126, FR-M-4)
- [x] THEME-01 (`69ec49e`) Picking a theme drops an accent chosen before, so New chat follows it (seen with Forest)
- [ ] SEC-01 A per-launch token for `/ws`, `/shutdown` and the VRM, from the shell to the kernel and the window (D-057, D-122); a plan first, it touches the shell
- [x] AUD-02 The audit fixes checked in the desktop app on 2026-11-24, driven by Claude through WebView2's debugging port: a link opens the browser and `file:`, `javascript:` and spaced URLs are refused; Ctrl+, moves focus into Settings, typing stays out of the message box, Esc returns focus; a half-filled New roleplay card survives Esc; Esc in Take her picture closes only the viewer; with the engine stopped a send says it is not connected and keeps the text, Reconnect brings it back in about 2 s and the note goes
- [ ] UI2-00c The two premade pets: Luna's and Yuri's sheets made with Create pet's prompt, shipped in their packs' `pet/` (D-103)
- [x] UI2-01 (D-102..D-113, D-124) References: the user and Claude collect apps and screens to follow (chat apps, character apps, what to avoid) into `docs/reference-images/`, each with a note on what to take from it (open question 1)
- [x] UI2-02 (D-124; `docs/DESIGN.md` records the look as built, for the user to read) `docs/DESIGN.md` agreed: colour roles, a type scale with nothing under 12 px, a 4 px spacing scale, one bundled UI font, radii, motion, focus rings, light and dark, the copy rule (FR-C-4); a mock of the main window before code
- [ ] UI2-03 Tokens in code (done: the CSS variables and eight themes); no white flash at startup (not checked)
- [x] UI2-04 Dropped (D-124): the app's own dialogs, menus and line icons stay. Primitives: tooltip, popover, dialog and menus on a headless library (proposed: Radix) and one icon set (proposed: lucide) replacing the emoji and text glyphs; decision first
- [x] UI2-05 (D-102..D-113) Apply to every surface: shell, sidebar, message list, composer, picker, settings, dialogs; before and after screenshots in `STATE.md`

## Phase K1b: Installer walking skeleton (D-035, D-081), time-boxed to about two sessions

- [ ] K1b-01 Kernel packaging spike: PyInstaller one-folder vs embedded CPython (size, antivirus, updates) (`ARCHITECTURE.md` packaging questions)
- [ ] K1b-02 Tauri per-user NSIS `.exe`, WebView2 bootstrapper, kernel as a sidecar named `kasane.exe`, data in `%APPDATA%\Kokyu` (D-081, D-089)
- [ ] K1b-03 Clean Windows VM (no Python, Node, Rust, Git): install, launch, a chat (local model, or an API key once there is one), uninstall
- [ ] K1b-04 Record antivirus/SmartScreen behaviour, size and install time in `STATE.md`
- **Checkpoint K1b:** a clean-machine install reaches a working chat; the packaging approach is a decision.

## Phase K2: Stage and voice

- [ ] K2-01 Stage view: auto-framing, backdrop, spring bones, idle motion, look-at, expression hooks (FR-ST-1..3, 5, 7)
- [ ] K2-02 Lip-sync from played audio; captions; docked input; chat log slide-over; Chat | Stage toggle in the top bar (FR-ST-3, 4, FR-C-7, FR-S-4)
- [ ] K2-03 GPT-SoVITS hardware spike (D-115): does it run, and how fast, on NVIDIA, CPU only, AMD and Intel; the provider interface (FR-VP-1); the "needs this PC's hardware" note wherever it is offered (FR-VP-5)
- [ ] K2-04 Barge-in (FR-V-5); clause pipelining while she writes, for Live (FR-V-3). Done in UI1-12: `speakable` and one-ahead synthesis of a finished reply (D-097)
- [ ] K2-05 TTS pre-warm on switch (FR-S-3) checked against real audio. Done in UI1-12: the starting chip for the 47 s cold start and the failure chip (D-097)
- [ ] K2-06 ElevenLabs with the user's own key (D-115, FR-VP-3, 5): key in the Credential Manager, an in-app picker of their account's voices with previews, per companion; the cloud badge
- [ ] K2-07 Voice input beyond dictation (UI1-12 shipped the mic button and F9, D-097): a system-wide key, VAD, push-to-talk, hands-free live voice (FR-V-6); keep STT off the asyncio loop
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

- [ ] W-01 Setup modules with pinned manifests (URLs, SHA-256, sizes, versions), progress, cancel and resume: local models, GPT-SoVITS, the STT model and `nomic-embed-text` (FR-COMP-2, D-117)
- [ ] W-02 Ollama through its official installer; model pull with progress
- [ ] W-03 Doctor checks grow fix actions (open the installer, start, retry) (FR-COMP-4, 5)
- [ ] W-04 The setup screen (D-117, FR-WIZ-2): after the age check, cards for Select the brain (local models with size and fit, or an API key with Test key), Select the voice, Speech to text, and Memory (required); then companion, then the first conversation; no account
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

- [ ] K7-10 Premade packs shipped packed and encrypted, read in memory by the engine; `prompt.md` left out (D-122). Only a deterrent: the window must decode the model to show it
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
- [ ] B-10 The premades are explicit (D-116); deferred until before K7: find a payment provider that accepts an explicit 18+ app in writing (all those checked ban sexual products; Lemon Squeezy is closing, Gumroad bans chatbots)
- [ ] B-11 UK: ask Ofcom's checker whether a local-only app is in scope of the Online Safety Act; block UK sales until then
- [ ] B-13 At launch (D-120): the crisis protocol on the website, UK sales blocked at checkout until Ofcom answers, the wording "runs on your PC, no account, no servers of ours" with the line on API models
- [ ] B-12 A lawyer's read on California SB 243 (and New York's companion law) for a bring-your-own-model desktop app: AI disclosure, crisis referral
- [ ] B-9 Marketing plan

## Backlog (parked, not approved)

- The sidebar lists the newest 200 conversations and search returns 50, with no note that older ones exist (the audit)
- A text file cut to 6,000 characters says so to the model but not on the attachment chip (the audit)
- GPT-SoVITS on 9880 has no authentication: any program on the PC can make her voice say anything (third-party; the audit)

- AUD-04 From the audit, not fixed: `context_budget.fit_messages` can drop a user line but keep the reply after it; `forget`'s trigger fires on "dont forget …"; the camera tool's `camera_request` is not wired in the window (K2-08)

- K1c follow-ups (D-075), none blocking:
  - a reply quoted only with U+201D speaks its narration;
  - a screen remark partly spoken is dropped if the thread changes during speech;
  - a story fold cut by the token cap is not detected;
  - a scenario save pending over a disconnect stays "Saving…";
  - no test for Escape in the delete confirm;
  - a fold may start before `load_thread`'s model request;
  - Temp Chat lines in a roleplay can be folded into its summary;
  - `thread_list` sends full cards on every refresh.
- D-098 follow-ups, none blocking:
  - the picker's "fits" badge still uses the flat `vram.kv_mb_per_1k_ctx`; the fit point uses the model's real shape: use the shape for both;
  - llm.py's length-stop diagnostics still name `llm.num_ctx`, not the model's Chat memory;
  - a KV cache quantized with `OLLAMA_KV_CACHE_TYPE` is not read: the estimate assumes f16 (it leans high);
  - check the fit point against a real load on the 9B, and whether a reply still works at a large value.
- D-097 follow-ups, none blocking:
  - a system-wide dictation key (the Tauri global-shortcut plugin, with a THIRD-PARTY row);
  - PyAV bundles FFmpeg (LGPL): review before release (THIRD-PARTY.md);
  - `test_vram`'s Windows-path test fails on a non-Windows machine (PosixPath of `C:\Windows` is not absolute): build the expected paths with PureWindowsPath;
  - dictation inserts at the caret where the box last had it; typing during the write-down moves nothing.
- Companion export/import as one file
- Stage backdrops and lighting presets
- A collapsible *Thoughts* block for reasoning models
- Emotion detection driving expressions
- Proactive messages and idle behaviours
- Multi-monitor pets
- Per-companion private memory (an option; contradicts D-005 today)
- Remember the last-used companion in `settings.json` instead of `data/active_waifu.txt`
