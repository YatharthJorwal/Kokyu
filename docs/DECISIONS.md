# DECISIONS — Kōkyū

The compact decision reference: what holds now, what is open, what was replaced.

- **Status:** Accepted, Provisional (to be confirmed or validated), Superseded.
- **Source:** User (the user's explicit instruction), Claude (the default: Claude's proposal), Assumed (Claude took the recommended answer while the user was away, D-076).
- **Rules:**
  - An entry body is not rewritten later. Only its status line may be stamped "Superseded by D-xxx".
  - New entries are at most about 150 words. Implementation detail goes to ARCHITECTURE and commit bodies.
  - D-044 promoted the earlier Provisional entries to Accepted, except the spike-bound D-014, D-035 and D-036.
  - The full original text of D-001 to D-075 is in `docs/archive/decisions-log-2026-11-17.md` (frozen).

## Open questions

| # | Question | Blocks |
|---|---|---|
| 1 | Design references: which apps and screens the look follows. The user gives them screen by screen (D-102); Settings and the top bar so far. | UI-2 |
| 2 | Decided (D-115): GPT-SoVITS on the PC or ElevenLabs with the user's key. Open: where GPT-SoVITS runs (K2-03 spike); the rights of the premades' ElevenLabs-made clips (D-041). | K2, K7 |
| 3 | Personas: explicit (D-116). Open, deferred: a payment provider that accepts an explicit 18+ app (all checked ban sexual products); UK sales (Ofcom, B-11); a lawyer's read on California SB 243 and New York Art. 47 (B-12). | K7, B-3 |
| 4 | Closed (D-118): the packs' text in git, VRM and WAV beside it with checksums; the user backs up those files. | — |
| 5 | An API key for testing the API path. | K1 checkpoint |
| 6 | Closed: her face is the VRM's own thumbnail, changeable in her profile (D-091). | — |
| 7 | D-074's six assumed answers: mode fixed at thread start; Chat replies about 3 to 4 lines; no tools in Roleplay; voice speaks only dialogue in Roleplay; no premade scenario cards; persona-only `persona.md` for Luna and Yuri. | K1c checkpoint |
| 8 | D-057's per-launch WebSocket token. | K7 |
| 9 | Delete `KASANE/vrm/` (C-1b, the user's action). | Nothing |
| 10 | Assumed in autonomous mode, to confirm or reverse: D-092..D-095 (UI1-07..10), and D-097's assumed parts (the in-app dictation key, kept by the page; no delivery layer with Read aloud; a reply finished while her voice starts waits for it; Settings → Voice), and D-098's (the name Chat memory, its place under Effort, per model for every thread, Ollama loading past the fit point). | UI-1 checkpoint |

## In force

### Identity and companions

**D-001 Name: Kōkyū, kernel KASANE** · Accepted · User · 2026-11-11
The app is Kōkyū (ASCII `Kokyu`), the kernel KASANE. The `kasane/` package name is amended by D-024.

**D-002 Seeded from Yuri by copy** · Accepted · Claude · 2026-11-11
Kōkyū started from a copy of Yuri with fresh history; Yuri and Luna stay untouched. Amended by D-062.

**D-003 A companion is a voice and a persona only** · Accepted · User · 2026-11-11
Pack = prompt, TTS parameters, VRM, pet sprites; no model, tools, permissions or memory keys. FR-W-3 test; CLAUDE.md invariant 1.

**D-089 KASANE as a quiet credit** · Accepted · User · 2026-11-17
"B: quiet credit". Users meet the engine's name only where it helps: the Doctor row "Engine (KASANE)", About ("Engine: KASANE" and one line on the name), the log `logs/kasane.log`, and the packaged process `kasane.exe` (K1b). Banners and messages keep saying "Kōkyū's engine"; no "powered by" branding. Amends D-001.

**D-024 Kernel folder `KASANE/`, flat modules** · Accepted · User (folder), Claude (layout) · 2026-11-11
The kernel folder is on `sys.path`; modules import by top-level name. There is no `kasane` package.

**D-028 Seed commit and provenance** · Accepted · Claude · 2026-11-11
Seeded from Yuri `e32af4f`, copied verbatim in its own commit before any rename, so the diff to Yuri is reviewable.

**D-031 Emotion tag and speech rules in the shared addendum** · Accepted · Claude · 2026-11-11
One addendum, identical for every companion, carries the emotion-tag rule, speech rules and tool guidance; persona prompts hold personality. Amended by D-045 and D-062.

**D-038 A companion does not carry its own model** · Accepted · User · 2026-11-11
"Companion-specific intelligence" was rejected: intelligence is the global model switcher (D-003).

**D-039 Premade companions are read-only packs with a rights record** · Accepted · Claude · 2026-11-11
Users duplicate a premade to edit it. Every shipped asset gets a rights record in `docs/THIRD-PARTY.md`. "Conservative by default": open question 3. Amended by D-041.

**D-041 The premades are Luna and Yuri, with the user's own assets** · Accepted, amended by D-118 · User · 2026-11-12
Packs in `assets/premade/<id>/`, built by `scripts/build_premade.py`. Before release, check the ElevenLabs plan behind the clips for commercial rights. Committing assets: open question 4.

**D-087 Premade characters are paid content shipped inside the app** · Accepted · User · 2026-11-17
Buyers pay for the app and for Luna and Yuri. Each ships complete: persona, voice clips with transcripts, VRM. Users can read her traits and how she behaves; the clips and the VRM are used only inside the app, never offered for export. Our assets are not open-sourced; the repository stays private (D-040). A user's own characters come from the creator (D-077): a step-by-step panel where they bring their own keys, models and files. Files on a user's PC cannot be made unreadable: protection is an app-only packed format plus the licence terms (K7). Amends D-039 (what duplicating a premade copies is to be decided in K3).

**D-045 K0 companion handling** · Accepted · Claude · 2026-11-12
A switch during a turn applies between turns; with the voice backend down a reply is caption-only; the last companion is remembered. With no pack installed a neutral fallback persona answers (amended by D-062).

**D-062 Yuri is only a character; v1-only protocol; the kernel split by job** · Accepted · User · 2026-11-15
"yuri must only be a character." No code path names her. The window speaks protocol v1 only; the widget is deleted. The kernel is split by job (CLAUDE.md §4).

**D-077 Companion creator: traits in, the model writes the persona, the user edits** · Accepted · User · 2026-11-17
Name and traits in; **Write it for me** sends the SPEC Appendix A instruction through `router.decide()` (role `chat`, the selected model) and fills an editable box. Validation stays; "Copy instruction" is optional.

### Models and routing

**D-004 One model switcher with Local / API sections and an effort slider** · Accepted · User · 2026-11-11
One chip opens a searchable popover with Local and API sections and an animated effort slider. Placement amended by D-068.

**D-019 Model refs and per-thread selection** · Accepted · Claude · 2026-11-11
`model_ref = <kind>:<backend>/<id>`, stored per thread; new threads inherit the last pick. API refs name the endpoint (amended by D-059).

**D-020 No silent fallback** · Accepted · Claude · 2026-11-11
A failed user-selected model shows the error with *Retry* and *Switch model*; the router never swaps models (CLAUDE.md invariant 4).

**D-025 Router front end and egress for the chat model** · Accepted · Claude · 2026-11-11
A `chat` role runs the thread's `model_ref`. Picking an API model is consent for the thread's text and user-attached files (badged); ambient captures never reach it; local-only roles stay local. Confirmed by D-047.

**D-037 Model providers and key storage** · Accepted · Claude · 2026-11-11
A generic OpenAI-compatible provider with presets. End-user keys live in the Windows Credential Manager; `.env` is developer-only. Amended by D-059.

**D-047 D-025 confirmed** · Accepted · User · 2026-11-14
The user approved D-025 as written.

**D-050 The chat role in code** · Accepted · Claude · 2026-11-14
No selection runs the local default. A blocked pick or provider error shows Retry and Switch model. Attached images stay blocked for API models until K2-07. Effort amended by D-064.

**D-051 llama.cpp for large local models** · Accepted · Claude · 2026-11-14
One `llama-server` child per preset, on 127.0.0.1; presets in `config.yaml`. A foreign server on the port is refused. Starts only when picked (D-060).

**D-054 Model picker: background loading, "waking up" status, last pick wins** · Accepted · User · 2026-11-14
One loader owns the loaded chat model; a newer request cancels an older one. A failed load offers Try again and Switch model. No switch mid-reply; only the driver window loads. Its models.yaml bullet is settled by D-064.

**D-059 One API endpoint at a time** · Accepted · User · 2026-11-15
"One at a time": a preset or custom URL, with the one saved key. A thread on another endpoint is blocked, never redirected. Keys never cross the websocket. Amended by D-070.

**D-064 Effort is data** · Accepted · User · 2026-11-15
"whichever out of config/model is appropriate." Local levels in `config/models.yaml`, API levels from catalog tags; remembered per model per thread. An empty reply is an error.

**D-065 VRAM manager v1** · Accepted; amended by D-098 (an Ollama model past its Chat memory fit point loads anyway) · Claude · 2026-11-15
GPU read from the driver, no Python package. Measured sizes beat estimates. The picker shows fits / won't fit; a load that will not fit is refused before anything unloads, naming what holds the memory. Amended by D-071, D-072.

**D-071 *Unload X* on the graphics-memory card** · Accepted · User · 2026-11-15
The card offers *Unload X* for a model the kernel will not reload at once; one click unloads it and retries. Amended by D-072 (the classifier may be offered).

**D-072 One chat model in memory; helper roles follow the pick** · Accepted · User · 2026-11-15
"only load the model that is selected. when selecting other one, unload rest". The helper roles run on the picked Ollama model; only the embedding model stays loaded. Memory writing stays local (CLAUDE.md invariant 3).

**D-083 Unpriced models allowed under the spending cap** · Accepted · User · 2026-11-17
"Allow them." A model with no catalog price runs while caps are on, labelled "price unknown, not counted against the cap", with a one-time notice; `budget.on_exhausted` is removed. Answers D-058; the code change is on TODO.

**D-084 Model names: short name shown, details muted on hover** · Accepted · User · 2026-11-17
Adds FR-M-12; extends D-068. A short name ("Qwen3.5 9B") computed in the kernel (`router/names.py`, planned); full id and facts muted on hover or focus. Precedence: `names:` in models.yaml, llama.cpp preset label, derivation. Design: archived refinement proposal §7.

### Memory and privacy

**D-005 Memory is shared across all companions** · Accepted · User · 2026-11-11
One app-level memory, not namespaced. Messages and summaries name the speaking companion.

**D-021 App identifier and data location** · Accepted · Claude · 2026-11-11
Identifier `io.github.yatharthjorwal.kokyu`. `paths.py` resolves `./data` (dev) and `%APPDATA%\Kokyu` (packaged).

**D-057 Two egress gaps closed; socket origin checked** · Accepted · Claude · 2026-11-14
API turns get no screen, camera or clipboard tools and no screen-companion remarks. The websocket refuses a foreign Origin. Token: open question 8.

**D-058 Spend ledger and cap** · Accepted · Claude · 2026-11-14
Every possibly billed API call gets a ledger row, estimated upwards when unreported. The cap reads the ledger before each call and counts calls in flight. Provider errors are redacted. Unpriced models amended by D-083.

**D-067 Settings v1: Models, Memory, Doctor, About** · Accepted · Claude · 2026-11-15
Memory facts can be corrected, forgotten, restored; nothing is hard-deleted. Doctor checks are read-only with fix hints. Amended by D-070, D-073.

**D-070 settings.json wins over config.yaml; changes apply at once** · Accepted · User · 2026-11-15
"Settings file wins." `settings.json` > `config.yaml` > code defaults, key by key, applied live. Ollama must be on this PC (invariant 3). A custom endpoint's key never follows an edited address.

### Voice

**D-006 Zero-shot voice per companion** · Accepted · User · 2026-11-11
One GPT-SoVITS base model; each request carries the companion's reference clip, transcript and language. No weight swapping in v1.

**D-036 Voice providers** · Provisional, amended by D-115 · Claude · 2026-11-11
Providers `gpt_sovits` (local), `builtin` (small local default, chosen in a K2 spike) and `elevenlabs` (cloud, opt-in, badged). None of the interface is built yet; see open question 2.

**D-042 GPT-SoVITS install for development** · Accepted · User · 2026-11-12
Development uses `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (quote the space). Its path lives in `config.yaml` (D-060); Track T is retired (D-080).

**D-061 Voice starts only when it is used** · Superseded by D-097 (voice mode replaced; "starts only when needed" kept) · User · 2026-11-15
"only boot up voice when its needed". Launch never starts GPT-SoVITS or faster-whisper. Voice mode is a kernel-wide switch, always off at start; the server stops after `tts.idle_stop_s` once voice is off.

**D-080 Automatic setup at first run; small setup modules, no framework** · Accepted · User (automatic setup), Claude (shape) · 2026-11-17
"The user won't have a good time tinkering with sovits." The first run sets up GPT-SoVITS and the speech-to-text model with progress, no terminal: one small setup module per component with a pinned manifest (URLs, SHA-256). Ollama via its installer; Doctor repairs the rest. Track T retired.

### Modes

**D-029 Inherited Yuri features kept** · Accepted · Claude · 2026-11-11
Kept: Temp Chat, look-intent camera and screenshot, emotion tags, `scene_state`. The "park Task Guide and OCR watch" part is amended by D-048.

**D-048 Task Guide and OCR watch are v1 screen companions** · Accepted · User · 2026-11-14
"actually add them as a feature". Opt-in, off by default, local models only, visible while active, one action to stop. The feature list may grow through new decisions.

**D-056 Screen companions in K1** · Accepted · Claude · 2026-11-14
Task Guide's classifier runs only while it is on. A mode needs a local vision model, else it refuses. Amended by D-070 (on at start) and D-074 (quiet in Roleplay).

**D-074 Conversation modes: Chat and Roleplay per thread** · Provisional · User (modes), Assumed (six answers) · 2026-11-17
"we should make modes". Mode is a thread property, never a companion's; the role stays `chat`. Roleplay turns skip tools, look intent, forget and the transcript log; the local memory writer summarizes the story (invariant 3). Open question 7.

**D-075 K1c build and review** · Accepted · Claude · 2026-11-17
Story folds wait for the chat model; a remark is dropped if the thread changed. Rejected findings are in the archive, so they are not re-raised. Leftovers: TODO K1c-10.

### UI

**D-009 Stage view is Ani-style** · Accepted · User · 2026-11-11
Her VRM bust-up with lip-sync, eye contact and idle motion; Chat | Stage toggles the same thread. Amended by D-068 (no sidebar companion list).

**D-010 Desktop pets are 2D sprites baked from the VRM** · Superseded by D-103 · User (2D), Claude (baking) · 2026-11-11
Orthographic sprite atlases baked through VRMA clips, played as 2D animation (K4, release 1.1).

**D-013 Frontend stack** · Accepted · Claude · 2026-11-11
Tauri 2, Vite, strict TypeScript, three.js with `@pixiv/three-vrm`, React for chrome, Zustand, plain CSS variables. Confirmed by D-053.

**D-014 Pets in one overlay window per monitor** · Superseded by D-103 · Claude · 2026-11-11
One transparent always-on-top overlay with alpha hit-testing; K4 starts with a spike, falling back to one window per pet.

**D-053 React chat window** · Accepted · User · 2026-11-14
"Chat now, avatar in K2". All behaviour is a pure reducer over protocol frames, tested in Node; components only render. The interim widget part is amended by D-062.

**D-055 In-house Markdown; Regenerate and Retry in the kernel** · Accepted · Claude · 2026-11-14
Model output never becomes HTML. Regenerate and Retry take the last exchange back out, so nothing is stored twice. The "no markdown" persona line is answered by D-074's persona.md.

**D-063 Heart and thinking lines above the input; threads fill from the bottom** · Heart and lines amended by D-096 · Accepted · User · 2026-11-15
"the messages should start at bottom not top." Rotating thinking lines beside a tracing heart; reduced motion respected.

**D-066 A failed turn says why, on the turn** · Accepted · Claude · 2026-11-15
An error card under the failed turn, with plain words per kind (401, 402, 429, timeout, 5xx) and the provider's redacted text under Details.

**D-068 The chat window follows the reference image** · Accepted · User · 2026-11-15
Frameless window; companion chip and Temp Chat switch in the top bar; no companions list in the sidebar; the model chip under the input box. Amended by D-069, D-082 (mic hidden) and D-084 (names).

**D-069 Replies end at their text; a status line under the input** · Accepted · User · 2026-11-15
Copy and Regenerate share the reply's name line; one column width; voice and screen chips sit under the box.

**D-073 Settings → Appearance** · Accepted · User · 2026-11-15
Theme, accent, message style and text size, kept by the page in `localStorage`, not the kernel.

**D-078 3D apartment planned for 1.1, from Luna's apartment** · Accepted (direction) · User · 2026-11-17
Takes over D-011's 3D scope (FR-3D). Base: Luna's GLB apartment (a user asset), BVH collision, spectator and WASD visitor cameras, her wandering, time-of-day lighting. Open: room data, asset rights, VRAM, two-companion turn-taking.

**D-082 Only working controls** · Accepted; amended by D-097 (the mic is back, working; one copy exception) · User · 2026-11-17
"We only put working buttons and add new ones with working scripts." Supersedes FR-C-4's "visibly disabled". No placeholders or phase codes in UI text; the mic is hidden until voice input works.

### Product, packaging and process

**D-016 Living docs: HANDOFF and STATE** · Accepted · User · 2026-11-11
HANDOFF is read at session start; both are rewritten so they are true now. Amended by D-076.

**D-017 Repository layout and kernel port** · Accepted · Claude · 2026-11-11
`src/`, `src-tauri/`, `config/`, `data/`, `docs/`; kernel port 8780. The package name is amended by D-024.

**D-022 Windows distribution** · Accepted (direction) · User · 2026-11-11
"Later, this is to be packaged as a Windows app". An NSIS installer with the kernel as a sidecar; models are not bundled. The portable bundle is superseded by D-081.

**D-023 Engineering defaults** · Accepted · Claude · 2026-11-11
FastAPI, pydantic, httpx, sqlite-vec, faster-whisper, pytest; Conventional Commits; numbers are estimates until measured. `ruff` never added; `nvidia-ml-py` dropped (D-065).

**D-026 K0 re-scoped** · Accepted · Claude · 2026-11-11
Threads, typed protocol and model plumbing moved from K0 to K1 (done).

**D-033 Paid, one-time purchase; bring your own models and keys** · Accepted · User · 2026-11-11
No subscription, no hosted inference; sold from an official website. Price undecided. Deferred by D-043.

**D-034 Release boundaries** · Accepted · Claude · 2026-11-11
1.0: chat, stage, voice, creator, first run, installer. 1.1: K4 pets, K5 apartment. Amended by D-079, D-080 and D-085 (order).

**D-035 First-run wizard and an early installer** · Provisional · Claude · 2026-11-11
Phase W (Welcome wizard) and a K1b walking-skeleton installer to test the sidecar on a clean machine. Its generic component interface is replaced by D-080.

**D-040 Licence: proprietary** · Accepted · User · 2026-11-12
"All rights reserved"; the repo stays private. Commits through `346f0c3` (docs only) were published under MIT (CLAUDE.md invariant 9).

**D-043 Commercial and release work deferred** · Accepted · User · 2026-11-12
Payments, website, pricing, signing and licence keys come after the product; portability rules apply now.

**D-044 SPEC is the baseline** · Accepted · User · 2026-11-12
"finalize the spec and proceed". Changes go through new decisions. SPEC v1.1 is rewritten in place when a decision amends a row (D-076).

**D-060 Lazy boot** · Accepted · User · 2026-11-15
"an app must not take that long to start". Nothing heavy loads until a window connects, then one step at a time; llama.cpp only when picked. The kernel owns GPT-SoVITS (amended by D-061).

**D-076 Docs and process reset** · Accepted · User · 2026-11-17
A lean doc set (one-page SCOPE, SPEC v1.1, this file, STATE verified by tests / browser pane / desktop app, short HANDOFF); old material frozen in `docs/archive/`. Claude commits on the user's PC, pushes when told, updates docs once per session. Each phase ends with one desktop-app checkpoint with a real model, ticked by the user. Autonomous mode: take the recommended answer, mark it Assumed, keep it reversible, never start a phase unapproved.

**D-079 Agent mode not planned; VR deferred long term** · Accepted · User · 2026-11-17
"This is a roleplay character app primarily." No file read/write agent mode; VR deferred long term (no headset).

**D-081 One installer: per-user NSIS .exe** · Accepted · User (installer only), Claude (format) · 2026-11-17
"only installer. Msix or .exe. Upto you". A per-user NSIS `.exe` from Tauri: no admin rights, no MSIX limits on the sidecar. No portable zip or MSIX for 1.0.

**D-085 Phase order after K1c** · Provisional · Claude · 2026-11-17
Docs reset; UI-1 (model names first); K1b installer skeleton (time-boxed); K2 stage and voice; K3 creator; W first run; K6; K7; then 1.1: K4, K5. To confirm next session.

**D-086 The design standard is its own phase, planned from references** · Accepted · User · 2026-11-17
"we will *plan* it first by taking actual references and all before finally building. its a real frontend update so a separate phase." Phase UI-2: collect reference apps and screens, agree `docs/DESIGN.md`, then build tokens, type scale, primitives and icons and apply them to every surface. UI-1 keeps the work that does not depend on the look. Amends D-085: UI-2 follows UI-1 (order provisional).

**D-088 Audience: a 16+ roleplay character app** · Superseded by D-090 · User · 2026-11-17
"roleplay character app category is already for mature teens (16+) so its fine when we ship it like that. needs some research though". The premade personas ship as written, pending research before release (open question 3). Claude's flag: explicit sexual content usually means an 18+ rating and an age gate; if the research confirms that, the choice is 18+ with a gate, or 16+ with personas that are not explicit.

**D-090 Audience: 18+, with an age check at first run** · Accepted · User · 2026-11-17
"go with 18+". From `docs/research-age-content-2026-11.md` (TODO B-9): every comparable app with sexual content is 18+, and 16+ is not a norm or a legal line anywhere checked. Kōkyū is sold for adults: the first run asks for age before anything else and stops under 18 (FR-WIZ-8); the terms say 18+. Whether the premade personas stay explicit is separate and open (open question 3). Supersedes D-088.

**D-091 Her face, and a character profile** · Accepted · User · 2026-11-17
"yes, just a vrm face. we will include a way to change the pfp in character profile though." Her portrait is the VRM's own thumbnail (VRM 1.0 `meta.thumbnailImage`; VRoid exports a face shot, as Luna's and Yuri's are), scaled down by the engine and served like the VRM. A companion whose VRM has none shows her initial. The user may replace the portrait from her profile and reset it to the model's face; the replacement lives in the app data folder, so premade packs stay read-only (D-039, D-087). A **character profile** shows her portrait, name, traits, a short About and a Chat button; packs gain an optional `about` field. It is not a platform page: no creator handle, likes, counts, sharing or similar characters. character.ai screens were references only, nothing copied. Closes open question 6. Amends FR-W-1 and FR-W-3 (the portrait joins what differs per companion) and R-01; adds FR-W-8 and FR-W-9.

**D-092 The message list; edit and resend** · Assumed · Claude · 2026-11-17
UI1-07. Lines from one speaker group under one name; time and model show in a hover bar (Copy, Regenerate, Edit). Editing the last user line re-runs the exchange through `regenerate {text}`: the edited line replaces the old one and its reply, no new message type. A line sent with a file can't be edited (the engine refuses; send the file again). The thinking state sits where the reply will appear; the heart above the input stays (FR-C-5). The view never jumps down while the user reads; a pill jumps to the latest. Amends FR-C-9.

**D-093 Markdown tables, nested lists and coloured code, in-house** · Assumed · Claude · 2026-11-17
UI1-08. The parser gains pipe tables (with alignment) and nested lists by indentation; code blocks get a header with the language and Copy, and colour from a small in-house highlighter (about 30 languages, keywords, strings, comments, numbers; skipped above 60k characters). No dependency: the output stays a tree, never HTML (D-055). Reversible by swapping in a library later with a THIRD-PARTY row. Amends FR-C-8.

**D-094 The shell: one header, split New, pins, toasts, in-app confirms** · Assumed · Claude · 2026-11-17
UI1-09. One slim header (companion chip, thread title, Temp, window buttons). New is split: New chat, and a menu with Chat / Roleplay…. Each conversation has a menu (right-click or ⋯): Pin, Rename, Delete…. Pins are stored by the engine (`threads.pinned`, schema 6, `thread_pin`) so every window agrees; pinned threads lead the list under "Pinned". Deletes ask through an in-app dialog, never `window.confirm`. Toasts only confirm what the user did (deleted, pinned); errors keep their cards. A new chat shows her face, name and four starter lines that send as typed. Amends FR-C-6.

**D-095 Keyboard shortcuts and a palette** · Assumed · Claude · 2026-11-17
UI1-10. Ctrl+N a new chat, Ctrl+K a palette, Ctrl+, Settings, Esc stops a reply. While a dialog or pop-up is open, it owns Escape and the shortcuts wait. The palette lists what works now: actions, companions (talk to, profile) and conversations, filtered by every typed word; it hides what a running reply forbids. Hints sit beside the controls (the New menu, Settings, Stop). No rebinding.

**D-096 Thinking beside her face, typed replies, a compact loading strip, a dragged slider** · Accepted; amended by D-097 ("Waifu-mode-engaging" restored, the letter animation, the slider's ends) · User · 2026-11-18
"the heart must be right to her pfp in chat, must show animation when model thinks along with some more creative text … must stop when response comes in a typing animation (not fat chunks)". While she thinks, her face, the heart and one short animated word (the user's list plus more in its voice, none from the waking lines) sit where her reply will appear; nothing above the input box. Replies type out letter by letter, catching up with any model. The model loading card becomes one line above the input box ("compact and professional"). The effort slider follows the pointer and settles on the nearest level on release ("i need smoothness"; no new component). "Waifu-mode-engaging" is left out under D-082. Amends D-063, FR-C-5, FR-M-6, FR-M-8.

**D-097 Read aloud and dictation replace voice mode; tags shown; UI notes** · Accepted · User, with Assumed parts · 2026-11-18
The user's notes. Voice mode goes. **Read aloud** (speaker icon, `＋` menu) speaks each finished reply in Chat and Roleplay, kept in settings.json; GPT-SoVITS starts only while it is on, and the window shows it starting (about 47 s). What is said passes one deterministic `speakable(text, mode)`, **no second model**, as agreed with the user: one would add delay, compete for graphics memory (D-072) and could change her words. **Dictation:** a mic button and F9 (changeable in Settings) fill the input box, never send; STT stays on the CPU. Her `[emotion]` tags stay in the text for the Luna and Yuri shells and show like actions. "Waifu-mode-engaging" returns, the one approved D-082 exception. Assumed: the key works in-app only and the page keeps it (D-073 style); no spoken-delivery prompt layer; a reply waits while her voice starts; a Voice section in Settings. Live speech-to-speech comes later. Supersedes D-061; amends D-082, D-096.

**D-098 Chat memory: a context length per model** · Accepted · User, with Assumed parts · 2026-11-18
"add a memory configurator … a slider for tokens 8k till however far it goes for its respective model. show a brief warning when exceeding hardware limit" (relayed by a sibling session). It is the context length. Assumed: in the picker under Effort, named **Chat memory** (Settings → Memory keeps her saved facts); detents 8K doubling to the model's maximum, plus the maximum; per model for every thread, in settings.json; untouched, `llm.num_ctx`. One value per model reaches every request, the history budget and llama.cpp's `-c`. Local models: the fit point is estimated from Ollama's `model_info` or the GGUF header (weights, KV cache, margin) against the room the model would have; past it, one line warns, never blocks: Ollama loads anyway and spills to RAM (amends D-065), llama.cpp's refusal stands. API models: a cost note, no hardware warning. Amends FR-M rows; adds FR-M-13.

**D-099 Read one message aloud on request** · Accepted · User · 2026-11-18
"add a speaker icon next to each of her message bubble so selected message can be read aloud even when automatic mode is off". A speaker in her messages' hover bar reads that message now, through `speakable` (the thread's mode), in the voice of the companion who wrote it, Read aloud on or off; clicked again it stops. With Read aloud off her voice starts for it (the button says so) and idles afterwards as usual. One reading at a time; a new line, Stop or another thread ends it; stopping a reading never stops a reply being written.

**D-100 A message's ⋯ card, swipes, roleplay pins; sidebar hide and filter** · Accepted · User, with Claude's parts · 2026-11-18
The user's notes, with c.ai screenshots. The hover bar goes: a ⋯ beside each bubble (left of the user's) opens a card: Copy, Edit (last line), Rewind to here (not on the newest; asks; deletes what follows, a chat's transcript rows and a story summary past it), Pin (roleplay only, "roleplays never affect normal chat"; always in her per-turn note, never memory.db), New chat from here (both modes; a copy up to that message). Her speaker sits by her name. Under her latest reply: Regenerate and ‹ n/m › swipes; Regenerate keeps the old replies, an edited line starts over. No like, dislike or report: "we arent selling our own ai model". The sidebar gets a hide button and All / Chats / Roleplays. Claude's: 10 pins per story (`story.max_pins`), the card's order and icons, the copy's title, the hidden flag kept by the page.

**D-101 A roleplay keeps its character; the story tray** · Accepted · User, with Claude's parts · 2026-11-18
The user's notes, with a c.ai screenshot. "in a roleplay, the character cannot be changed. start a new chat if user wants to": the chip opens her profile and the engine refuses a switch. In a roleplay the paperclip becomes a book opening the story tray: History (a page listing every roleplay with her), New chat (the story again from its card), Memory (a box the user writes, in her note every turn, with the story's pinned messages listed); "no ocr watch and task guide". Claude's: Memory is per story (c.ai's is per chat) and up to 1000 characters; Upload file and Read aloud stay in the tray; History lists the roleplays the window knows (the newest 200). Settings → Voice's switch now says Off or On.

**D-102 UI-2 starts from the user's references, one screen at a time** · Accepted · User, with Claude's parts · 2026-11-22
The user opened UI-2 with screenshots: "first fix the settings and make them look proper like ref images", and "shift chat title to middle". So UI-2 restyles a screen against a reference the user gives, instead of a full `DESIGN.md` first; the tokens and type scale grow from those screens. Settings first: icons in the section list, rows with a title and a muted line left and the control right, theme cards, bordered provider cards with a status dot and Edit, nothing under 12 px; same sections and features. The chat title is centred on the whole top bar. Claude's: the icons are drawn in-house like the rest (no icon library yet, D-086's UI2-04 still open). Amends D-086.

**D-103 The pet is chibi her, inside the window, from a pose sheet** · Accepted · User, with Claude's parts · 2026-11-22
The user, after ThatPet's screenshots: the pet is "the companion herself, chibi luna while you chat with luna", in chat and roleplay, not in the stage view; it stays in the app window ("doesnt interact with desktop stuff"), about ten animations; Kōkyū sells two premade pets and has a step-by-step Create pet; "develop the pipeline first"; the art comes from a strong image model drawing many poses on one sheet. A pet is a skin: labelled pose images, one engine plays any of them. Claude's parts: a 4×3 sheet of 12 named poses; the engine cuts the grid, keys out a flat background when the sheet has no transparency, trims each pose and keeps the sheet's scale, so her feet sit on one line; each animation is one to three stills moved by code (slide, bob, breathe, flip), not frame-by-frame art, because image models do not keep a walk cycle consistent; the user generates the sheet outside the app with the prompt it gives (an in-app image call with the user's key comes later); her pet lives in the app data folder, or in her pack's `pet/` for a premade; the behaviour setting and size are the window's own, like Appearance. Supersedes D-010 and D-014; FR-P rewritten; pulled forward from 1.1 into UI-2.

**D-104 The Stage (the user's "VR mode") is Yuri's shell in the chat column** · Accepted · User, with Claude's parts · 2026-11-22
The user: "add the VR mode and it will be the shell from yuki" (Yuri's repo; there is no Yuki), "build shell too (VR mode)"; the pet is "not VR mode cuz it already has VRM". So "VR mode" is the VRM stage of D-009, not a headset. Claude's parts: a Chat | Stage switch in the top bar, per window and not saved; the Stage replaces the conversation in the chat column, keeps the top bar and the same input box, and shows her latest words as a caption; Yuri's `boot()` scene (framing from the head bone, rest pose, flat light, idle motion, eyes, expression life with Yuri's blends, lip-sync) as `src/engine/stage.ts`, loaded only when the Stage is first opened; every voice clip now plays through the engine's lip-sync player so her mouth follows it; the pet stays out of the Stage. Not yet: the chat log slide-over (FR-ST-4), the frame-rate target (FR-ST-6). Pulls K2-01 and most of K2-02 into UI-2; the label is "Stage" (SPEC's word), not "VR".


**D-105 Picking a model starts its server** · Accepted · User · 2026-11-22
"make it start ollama/llama.cpp if they are not already running when a model is selected". llama.cpp's `llama-server` was already started by its provider on load. Ollama now is too: before an Ollama model loads (picked, or the boot warm-up), the kernel asks Ollama (`GET /api/version`); if nothing answers on a local address (127.0.0.1, localhost, ::1) it starts `ollama serve` (on PATH, else the Windows installer's folder), with no console window, and waits up to 20 s. Someone else's server is never started. Started from the kernel it is the kernel's child, so it ends with the app. `llm.start_ollama` (default true) turns it off. Dev and tests never start the user's Ollama (conftest stubs it).

**D-106 Uploads: one size limit and an allowlist of formats, checked twice** · Accepted · User, with Claude's parts · 2026-11-22
"add an upload limit to everywhere (chat upload files, pet upload) and a strict file format especially for upload. we dont want anything to break when this app sells". Every picture (a chat image, her picture, a pet sheet) must be PNG, JPEG, WebP or GIF, at most 20 MB and about 40 megapixels (6300 × 6300); no SVG, HEIC, TIFF, BMP or ICO. A chat text file is chosen by its extension only (the existing list of text and code types), at most 2 MB, refused if it holds a NUL byte, and cut to 6000 characters as before. The window checks before reading (`src/app/file-upload.ts`, one check for all three uploads, a plain reason on refusal); the kernel opens every picture again through `KASANE/uploads.py`: strict base64, Pillow limited to the four formats, the pixel count checked from the header before decoding. A chat image that fails there is refused as `picture_unreadable` and the turn ends with no line, before the vision model sees it. Claude's: the numbers.

**D-107 The pet walks on the window's bottom, can be carried, and keeps one size** · Accepted · User, with Claude's parts · 2026-11-22
The user: "make walking animation better", "make it walk on the bottom of the window" (she walked on the input box), "make it draggable and stick to one pose when dragging … then a falling one", "make the sitting pose slightly smaller … she looks too big when sleeping", "make an auto size checker when making pets so everything is constant", "put a make new pet option and it will show list of currently made characters", with a note to make a new character first for a different pet. So: she walks along the chat column's bottom edge, in front of the input box (under its menus); the walk's speed and step length scale with her size and her steps follow the distance walked (walk 1 and walk 2 alternate per step, a rise mid-step, a slight sway, easing in and out), so her feet do not slide. Pressed and moved she is held in the *surprised* pose, swinging slightly; let go she falls with gravity, lands sitting for a moment, then carries on; a press without a move is still a click (wave). When a pet is saved, each pose must fit a box for its kind (standing as tall as idle, sitting 0.74, sleeping 0.5 tall and 0.72 long, happy with arms up 1.12), and a cell drawn too big is shrunk to fit, never grown. Settings → Pet gains Make a new pet: a list of the characters, each marked with or without a pet; picking one runs Create pet for that character. Amends D-103, FR-P-1, 3, 4.


**D-108 The pet's size checker matches her head; each pose drawn at its own size; Save as** · Accepted · User, with Claude's parts · 2026-11-22
The user, with screenshots after D-107: sit and sleep "are still distinct". Two causes. The window drew every pose at idle's height, stretching the shorter sit and sleep up to it; each pose is now drawn at its own saved height times Size. And a box per pose could not see that the image model drew her head bigger in some cells; the size checker now looks for idle's head in each pose (normalized cross-correlation over scales, and turned up to 90 degrees for sleep) and scales the pose until her head matches; where her head is not found with confidence (side-view walks, arms up, often lying down) D-107's box decides. Luna's live pet was redone this way from its original cells. Also from the user: the picture viewer shows a short note on the picture when it is copied or saved, and Save asks where to save it (the window's Save As; a webview without one saves to Downloads and says so). Amends D-107 and FR-P-2.


**D-109 The cat button: blue when she is out, grey on the Stage, Pet settings on hover** · Accepted · User · 2026-11-22
"on pet icon in chat, hover must show an option to show settings. and it must turn bluish when pet is shown. make it grey/muted where pet is disabled by default (stage)". Hovering or focusing the cat button shows a Pet settings button under it (Settings → Pet); the cat is blue while her pet is shown, muted otherwise; on the Stage, where the pet never walks (D-104), it is greyed and does nothing, and still offers Pet settings. Amends FR-P-1.


**D-110 Pet settings: the hover menu closes when used, none on the Stage; Switch character** · Accepted · User · 2026-11-22
"the pet settings on hover must disappear when it is clicked. and dont show it on hover at stage. also in pet settings card, add an option to switch character (same list thing)". Clicking Pet settings hides the menu until the pointer leaves the cat; on the Stage the cat offers no menu. Settings → Pet gains Switch character beside Make a new pet: the same list of characters, the current one marked; picking one switches to her as the companion chip does. Not in a roleplay (she stays for the story, D-101) or with no one else. Amends D-109.


**D-111 The Stage caption is Yuri's; its glow color is the user's** · Accepted · User, with Claude's parts · 2026-11-22
"take the caption style from the yuri repo for stage. and the glow color must be changable". Yuri's caption (`src/style.css` `#caption`, `src/main.ts` `applyCaptionProgress`): no box; while her voice plays, the clip's words pop in one at a time, each given a share of the clip's length by its letters (no word timings from the voice engine); the word being said glows; the four behind it dim; older ones fold away. Settings → Appearance gains Caption glow: six swatches and any color, Yuri's pink by default, kept with the theme in this window. Claude's: without her voice (Read aloud off, or before the first clip) the caption shows her latest words still, in the same lettering and glow; the colors follow the theme's text color so the light theme stays readable. Amends D-104.


**D-112 Accent text stays readable; her voice's start and failure are always said** · Accepted · User, with Claude's parts · 2026-11-22
The user, with a screenshot (light theme, a near-white accent): "her name text goes invisible when white. i want it to be visible no matter what theme is chosen. and for some reason, the sound icon vanished too", and "add a note about fetching voice model when it is cold started and a fail note when it fails, with the option to set up which opens settings". Text and icons drawn in the accent (her name, a lit speaker, links) use `--accent-text`: the accent when it reaches 3:1 contrast on the theme's background, else the theme's text color; fills keep the accent. The Read aloud chip now also shows while her voice starts for one message read on request (D-099) with Read aloud off, counting as before, and stays if that fails; a failed voice offers Set up (Settings → Voice) beside Try again. Amends D-097, D-099.

**D-113 Round swatches, five more themes; on the Stage she speaks, a line at a time** · Accepted · User, with Claude's parts · 2026-11-22
The user: "color icons in settings are oval. fix / add more theme presets. and also, stage must have her speak by default with slower captions that also disappear, not just type out quickly like chat mode". The swatches lose the settings buttons' 32 px minimum height. New presets: Sakura and Paper (light), Ocean, Forest and Mocha (dark), each held to text 7:1 and accent and muted text 3:1 by a test. Opening the Stage turns Read aloud on, and closing it turns it back off if the Stage turned it on. The Stage caption no longer streams the reply: with her voice it follows the clip playing (D-111); without it (Read aloud off, or her voice failed) the finished reply is shown one sentence at a time, word by word at about speaking pace (0.07 s a letter, 1.6 s at least), *actions* left out; each line holds 0.9 s, then fades. While she thinks or writes, only an ellipsis shows. Amends D-111, D-097; FR-ST-4 rewritten.


**D-114 What the audit's bug fixes changed for the user** · Accepted · User ("check rest of the stuff and fix current bugs"), Claude's parts · 2026-11-24
A whole-repo audit (four reviewers, then each finding checked against the code) found bugs; all were fixed except the lean items (TODO AUD-03, AUD-04). The ones a user can notice: only the window in charge may delete a conversation (another window's delete is refused); a request to quit from a web page, or any request whose Host is not 127.0.0.1 or localhost, is refused; a link in a reply opens in the user's browser through the shell (http and https only); a click that needs the engine while it is offline says so once, and the note goes when it is back; Esc or a click outside does not close the New roleplay or story Memory dialog while it holds unsaved text (Cancel and ✕ still do); the message box, Edit box, fact editor and address fields stop at the engine's limits; a look at the camera or screen needs a first-person ask ("what am I holding", "use your tools"); an unreadable settings.json is kept as settings.json.broken; the last run's log is kept as kasane.prev.log. Amends D-070, D-082, D-095, D-100, D-101; FR-SC look phrases. Commits `781cd84`, `af5b98a`, `62ec66f`, `38768de` and the window's offline-note fix.


**D-115 The voice a buyer hears: GPT-SoVITS on their PC, or ElevenLabs with their own key** · Accepted · User ("their own api from eleven labs … also gpt sovits if it runs on other graphic cards"), Claude's parts Assumed · 2026-11-24
Two voices, both the user's choice. **GPT-SoVITS** runs on the user's PC and is set up by the app (D-080); a K2 spike finds where it runs (NVIDIA, CPU only, AMD, Intel) and how fast. Wherever it is offered (first-run setup, the creator, Settings → Voice) a note says a local voice needs this PC's hardware. **ElevenLabs** with the user's own key (Credential Manager): an in-app picker lists the voices on their account with a preview to play, chosen per companion, with the cloud badge (FR-VP-3). With neither, she is text only and the chat never waits. Assumed: the `builtin` CPU voice is no longer planned (brought back only if the spike finds no usable local voice without a GPU). Open: the commercial rights of the premades' ElevenLabs-made reference clips (D-041). Amends D-036; FR-VP-1, FR-VP-5; TODO K2-03, K2-06.

**D-116 The premade personas are explicit** · Accepted · User ("the personas can curse and get into sexual roleplay as well") · 2026-11-24
Luna and Yuri curse and can take part in sexual roleplay. The app is 18+ with the age check as the first step of setup (D-090, FR-WIZ-8). The research report's recommendation C (non-explicit premades) is not taken. The payment provider is **deferred**: every provider the research checked bans sexual products (`docs/research-age-content-2026-11.md` §3), so a provider that accepts the app is found before K7 (TODO B-3, B-10). UK sales (Ofcom) and California SB 243 / New York Art. 47 stay open (B-11, B-12). Closes open question 3's persona part.

**D-117 First-run setup: pick the parts on cards, no accounts** · Accepted · User, Claude's parts Assumed · 2026-11-24
After the age check, setup works like ComfyUI's: cards to pick what is installed, then the app downloads and sets each up itself with progress, cancel and resume (FR-COMP-2). **Select the brain:** open-source models to run locally through Ollama, each with its size and fit on this PC, or an API key; optional, since an API key always works. **Select the voice:** GPT-SoVITS (local, the hardware note) or ElevenLabs (a key), or none (D-115). **Speech to text:** faster-whisper, optional. **Memory:** `nomic-embed-text`, required, shown but not a choice. No login, no account, no server of ours: everything stays on the PC, and the data folder stays after uninstall unless the user chooses to delete it (FR-DIST-4). Assumed: memory's embedder runs through Ollama today, so every install sets up Ollama, even API-only ones; W may swap it for a smaller in-app embedder. Amends FR-WIZ-2, FR-WIZ-3, FR-COMP-2, FR-COMP-3; TODO W-01, W-04.

**D-118 The premade packs: their text in git, their files beside it** · Accepted · Claude (the user: "its your call") · 2026-11-24
Luna and Yuri ship with the app, whole: persona, about, traits, voice clip and transcript, VRM, and later their pet sheets. In the private repo: `waifu.yaml` (with the transcript), `persona.md`, `prompt.md`, the README. Out of git, per invariant 5: `model.vrm`, `voice/ref.wav` and pet sheets; `assets/premade/ASSETS.sha256` (in git) lists each with its SHA-256 so a build knows it has the right ones. A backup of those files off this PC is the user's (proposed: a release on the private GitHub repo). The installer bundles each pack in the app-only packed format (D-087, K7-09). Amends D-041's `.gitignore` rule, which let `.vrm` and `.wav` in. Closes open question 4.


## Superseded

- D-007 TTS backend built by a separate agent → superseded by D-080 (the app sets it up)
- D-008 Paste-only persona box → superseded by D-077 (the model writes, the user edits)
- D-011 3D mode WASD; VR deferred → superseded by D-078 (apartment) and D-079 (VR long term)
- D-012 Agent mode deferred → superseded by D-079 (not planned)
- D-015 Licence MIT → superseded by D-040 (proprietary)
- D-088 Audience 16+ → superseded by D-090 (18+, after the B-9 research)
- D-018 Helper models in Settings → Advanced → superseded by D-072 (helpers follow the pick)
- D-027 Shell starts kernel and TTS in parallel → superseded by D-060 (lazy boot; port 8780 stays, D-017)
- D-030 Delivery by git bundle → superseded by D-076 (commits on the user's PC)
- D-032 Licence undecided, pushes held → superseded by D-040 (decided)
- D-046 Avatar swap by page reload → superseded by D-062 (widget deleted; K2 swaps in Stage)
- D-049 Flat and v1 messages side by side → superseded by D-062 (v1 only)
- D-052 Helpers kept loaded; boot warm-up → superseded by D-072 (one model in memory) and D-060 (lazy boot)
- D-061 Voice mode, a kernel-wide switch → superseded by D-097 (Read aloud and dictation)
- D-010 Pets baked from the VRM, D-014 desktop overlay → superseded by D-103 (chibi her in the window, from a pose sheet)
