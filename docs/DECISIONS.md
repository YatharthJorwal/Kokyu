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
| 1 | Design references: which apps and screens the look follows. UI-2 starts by collecting them (D-086). | UI-2 |
| 2 | The voice a buyer hears. The premades ship their clips and transcripts (D-087) and GPT-SoVITS is set up automatically (D-080). Open: buyers without an NVIDIA GPU (D-036); the ElevenLabs plan's commercial rights for the clips (D-041). | K2, W, K7 |
| 3 | Premade personas: explicit or not? The audience is 18+ (D-090), but every payment provider checked bans sexual products whatever the age; the report recommends non-explicit premades. Also open: a written yes from a provider, UK sales (Ofcom), a lawyer's read on California SB 243. | K7, B-3 |
| 4 | Premade packs in git. Claude's recommendation: track `persona.md`, `waifu.yaml` and the clip transcripts in the private repo; keep VRM and WAV out of git (size, invariant 5) with a separate backup. | Every commit |
| 5 | An API key for testing the API path. | K1 checkpoint |
| 6 | Closed: her face is the VRM's own thumbnail, changeable in her profile (D-091). | — |
| 7 | D-074's six assumed answers: mode fixed at thread start; Chat replies about 3 to 4 lines; no tools in Roleplay; voice speaks only dialogue in Roleplay; no premade scenario cards; persona-only `persona.md` for Luna and Yuri. | K1c checkpoint |
| 8 | D-057's per-launch WebSocket token. | K7 |
| 9 | Delete `KASANE/vrm/` (C-1b, the user's action). | Nothing |

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

**D-041 The premades are Luna and Yuri, with the user's own assets** · Accepted · User · 2026-11-12
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

**D-065 VRAM manager v1** · Accepted · Claude · 2026-11-15
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

**D-036 Voice providers** · Provisional · Claude · 2026-11-11
Providers `gpt_sovits` (local), `builtin` (small local default, chosen in a K2 spike) and `elevenlabs` (cloud, opt-in, badged). None of the interface is built yet; see open question 2.

**D-042 GPT-SoVITS install for development** · Accepted · User · 2026-11-12
Development uses `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (quote the space). Its path lives in `config.yaml` (D-060); Track T is retired (D-080).

**D-061 Voice starts only when it is used** · Accepted · User · 2026-11-15
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

**D-010 Desktop pets are 2D sprites baked from the VRM** · Accepted · User (2D), Claude (baking) · 2026-11-11
Orthographic sprite atlases baked through VRMA clips, played as 2D animation (K4, release 1.1).

**D-013 Frontend stack** · Accepted · Claude · 2026-11-11
Tauri 2, Vite, strict TypeScript, three.js with `@pixiv/three-vrm`, React for chrome, Zustand, plain CSS variables. Confirmed by D-053.

**D-014 Pets in one overlay window per monitor** · Provisional · Claude · 2026-11-11
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

**D-082 Only working controls** · Accepted · User · 2026-11-17
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

**D-096 Thinking beside her face, typed replies, a compact loading strip, a dragged slider** · Accepted · User · 2026-11-18
"the heart must be right to her pfp in chat, must show animation when model thinks along with some more creative text … must stop when response comes in a typing animation (not fat chunks)". While she thinks, her face, the heart and one short animated word (the user's list plus more in its voice, none from the waking lines) sit where her reply will appear; nothing above the input box. Replies type out letter by letter, catching up with any model. The model loading card becomes one line above the input box ("compact and professional"). The effort slider follows the pointer and settles on the nearest level on release ("i need smoothness"; no new component). "Waifu-mode-engaging" is left out under D-082. Amends D-063, FR-C-5, FR-M-6, FR-M-8.

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
