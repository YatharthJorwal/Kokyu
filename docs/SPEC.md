# SPEC — Kōkyū

Requirements with stable IDs. TODO items, tests and commits reference these IDs. Overview: `SCOPE.md`. Design: `ARCHITECTURE.md`. Why: `DECISIONS.md`.

- **MUST / SHOULD / MAY** follow RFC 2119 usage.
- **TARGET** marks a number to be *measured and calibrated* in the named phase; it is not a verified fact.
- **Phase** column: when the requirement is delivered. Release 1.0, in delivery order (D-085, provisional): K0, K1, K1c, UI-1, K1b, K2, K3, W, K6, K7. Release 1.1: K4, K5 (Appendix B). Each phase ends with one checkpoint in the desktop app, ticked by the user (D-076).
- Version: **spec v1.1**, 2026-11-17. A decision that amends a row is rewritten into the row, with its D-ID; `DECISIONS.md` says why.

**Changelog v1.0 → v1.1**
- Folded in: D-059 (one API endpoint), D-064 (effort data), D-065, D-071 (VRAM checks), D-066 (failure card), D-067, D-070, D-073 (Settings, settings.json, appearance), D-068 (window layout), D-072 (one chat model in memory).
- Added: FR-MODE (D-074, D-075); FR-M-12 model names (D-084).
- Changed: FR-C-4 only working controls (D-082); FR-CR-5, 6 Write it for me (D-077); FR-R-2 unpriced models (D-083); FR-DIST one NSIS installer (D-081); FR-COMP, FR-WIZ automatic setup (D-080).
- Moved to Appendix B: FR-P, FR-3D (now the apartment, D-078). Removed: agent mode, VR (D-079), Track T (D-080).

## 1. Definitions

| Term | Meaning |
|---|---|
| **Companion** (internal: *waifu*) | Name, traits, system prompt, VRM, voice. Nothing else. UI text says "companion". |
| **Thread** | One conversation. Has one mode, one active companion, one chat model, one effort setting. |
| **Turn** | One user message and the reply it triggers. |
| **Chat model** | The single user-selected model for a thread. Local or API. |
| **Helper role** | A background role (classifier, memory writer, vision, embeddings, reflex). The user never picks its model; always local (D-018, D-072). |
| **Kernel** | KASANE, the Python process holding all logic (an internal word, never in UI text). |
| **Client** | The main window (pet overlay in 1.1). Renders kernel state, holds no business logic. |
| **Stage** | The view where the active companion's VRM stands in front of the user (K2). |
| **TTS backend** | The headless GPT-SoVITS server; its API contract is in `ARCHITECTURE.md` (D-080). |

## 2. Functional requirements

### 2.1 Companions (FR-W)

| ID | Requirement | Phase |
|---|---|---|
| FR-W-1 | A waifu MUST consist of exactly: `id`, `name`, `traits[]`, `prompt`, `vrm`, `voice{provider, provider-specific fields}`, plus a derived `pet/` atlas (1.1). | K0 |
| FR-W-2 | Waifus MUST live in the app-data directory (`waifus/<id>/`). They MUST be created, edited and deleted only through the app UI (K3). A dev seed script MAY import packs before the creator exists. | K0, K3 |
| FR-W-3 | **Invariance:** for the same thread state and input, switching the active waifu MUST NOT change model selection, effort, router decisions, available tools, permissions or memory recall results. Only the system prompt, TTS parameters, VRM and pet sprites differ. A parameterized test over two fixture waifus MUST enforce this. | K0 |
| FR-W-4 | `id` is an immutable slug (`[a-z0-9-]{2,32}`). The display `name` (1 to 32 chars) MAY be renamed. | K0 |
| FR-W-5 | Deleting a waifu MUST remove her pack and sprites. Existing messages keep a **snapshot of her name** and render as "(deleted)" if needed. | K3 |
| FR-W-6 | Packs MUST be validated on load; an invalid pack is skipped and reported in the UI and log, never crashing the kernel. | K0 |
| FR-W-7 | **Premade companions:** **Luna** and **Yuri** are built-in, read-only packs (`assets/premade/<id>/`, resolved through `KASANE/paths.py`), loaded together with user packs from `waifus/`. Ids are unique across both; a user pack cannot shadow a premade one. The user MAY duplicate a premade pack to edit it (D-041). | K0 |

### 2.2 Chat (FR-C)

| ID | Requirement | Phase |
|---|---|---|
| FR-C-1 | Threads MUST be creatable, renamable, deletable and searchable (title and message text). Stored in SQLite. | K1 |
| FR-C-2 | Replies MUST stream token by token. **Stop** MUST halt generation (TARGET ≤ 300 ms) and keep the partial reply. Audio stops with it (TARGET ≤ 200 ms). | K1 |
| FR-C-3 | The input box MUST be centered, multi-line (`Enter` sends, `Shift+Enter` newline), and accept pasted images and dropped files. | K1 |
| FR-C-4 | **Only working controls (D-082):** a control appears only when it works end to end, and a new control lands with its working code; no disabled placeholders or "coming soon". The `＋` tray (the paperclip, D-068) offers what works: upload file, Voice, Task Guide, OCR watch; camera, screenshot and paste image join when they work. The mic button stays hidden until voice input works. **Copy rule:** UI text uses plain words, never internal ones ("kernel", "waifu", phase codes such as K2). | K1, UI-1, K2 |
| FR-C-5 | The **heart** above the input box (D-063) MUST show idle, thinking and replying. It respects reduced motion. | K1 |
| FR-C-6 | The sidebar MUST show New chat and search at the top, history in the middle (grouped Today / Yesterday / Previous 7 days / Older, each with her badge), and **Settings** at the bottom. It does not list companions; she is picked with the companion chip (FR-S-1, D-068). | K1 |
| FR-C-7 | A **Chat / Stage** toggle MUST switch views of the same thread without losing state. | K2 |
| FR-C-8 | Replies MUST render Markdown (code blocks with a copy button), parsed in-house, never as HTML (D-055). What is *spoken* is the speech-safe version (FR-V-2). | K1 |
| FR-C-9 | Each assistant message SHOULD offer *Copy*, and the last one *Regenerate* (run in the kernel, D-055). | K1 |
| FR-C-10 | Messages MUST record: speaker waifu id and name snapshot, model ref, effort, timestamps, token counts where known. | K1 |

### 2.3 Companion switcher (FR-S)

| ID | Requirement | Phase |
|---|---|---|
| FR-S-1 | A chip in the top bar (D-068) MUST show the active companion's avatar and name. Its popover is a searchable list, plus **＋ New companion** once the creator works (K3, D-082). | K1 |
| FR-S-2 | Switching MUST insert a visible divider ("Switched to Luna"), apply from the **next** turn (a turn in flight finishes with the old companion), and keep prior messages on screen tagged with their speaker. | K1 |
| FR-S-3 | While voice is on, switching MUST send a short TTS **pre-warm** for the new companion so her first real line is not slower (D-061). | K2 |
| FR-S-4 | The Stage is entered from the top bar (the Chat / Stage toggle, FR-C-7); the exact control is designed in K2. The sidebar has no companion list to enter it from (D-068). Opening a history entry opens Chat view. | K2 |
| FR-S-5 | Switching MUST NOT alter the model chip, the effort slider or any permission (FR-W-3). | K0 |

### 2.4 Model switcher and effort (FR-M)

| ID | Requirement | Phase |
|---|---|---|
| FR-M-1 | There MUST be **one** model control: a chip under the input box (D-068) showing the model's short name (FR-M-12) and the effort label. | K1 |
| FR-M-2 | Its popover MUST have a search box and two clearly separated sections, **Local** and **API**, as one list (not a toggle). The current model carries a check mark. Picking a row is the whole action. | K1 |
| FR-M-3 | **Local** lists Ollama models (`GET /api/tags`, minus embedding models) plus the llama.cpp presets from `config.yaml` (`llamacpp.presets`, D-051, D-064). Each row shows size and a *fits / won't fit* hint from the VRAM manager (D-065); unknown shows nothing. | K1 |
| FR-M-4 | **API** lists the models of the **one active endpoint** (D-059): a preset (AI Router, OpenRouter, DeepSeek) or a custom base URL, through the generic OpenAI-compatible provider (D-037), from its `/models`, with the vendor as a sub-heading, capability badges and a price hint when the catalog has one. The catalog is cached; offline or after a failed refresh it shows the cache marked *cached*. A refresh button re-fetches. Rows without a key are listed greyed with the reason. | K1 |
| FR-M-5 | The selection is **per thread**; new threads inherit the last selection. It is independent of the companion. | K1 |
| FR-M-6 | **One chat model in memory (D-072):** picking a model unloads every other chat model (llama-server stops, other Ollama models unload); only the embedding model stays. With an Ollama pick the helper roles run on it; with a llama.cpp or API pick each helper loads for its call and leaves. Loading shows progress (the waking-up card, D-054). A local model that will not fit is refused before anything unloads, naming what holds the memory, with *Unload X* where it helps (D-065, D-071). | K1 |
| FR-M-7 | The chip MUST show a local or cloud icon. Spend so far against the cap appears in the popover footer. | K1 |
| FR-M-8 | **Effort slider**, inside the popover, with a short label on the chip. Discrete detents from the canonical set `off, low, medium, high, max`, **restricted to what the selected model supports** (FR-M-10). If none are supported, no slider is shown. | K1 |
| FR-M-9 | Motion is short and consistent: the slider and the chip show the level (a glow on the chip while generating); reduced motion makes all of it static. | K1 |
| FR-M-10 | Effort support is data (D-064): catalog tags for API models (`reasoning_effort` for low, medium, high), `config/models.yaml` over `config/models.example.yaml` for local models (thinking on or off, or a level). No thinking-token budget: neither local backend takes one. | K1 |
| FR-M-11 | Effort is remembered per model per thread. Reasoning text is never spoken and is not shown in the chat. | K1 |
| FR-M-12 | **Model names (D-084):** every model shows a short name ("Qwen3.5 9B", "Claude Sonnet 5.5") on every surface (chip, picker, loading card, VRAM messages, "Sent to"), computed in the kernel (`router/names.py`) so all surfaces agree. Rows carry `label` (short), `full` (the exact id, or a llama.cpp preset's file) and `detail` (the facts: backend, quant, parameters, context; the client adds file size, price and why a row cannot be picked). Name precedence: a `names:` override in `models.yaml`, then a llama.cpp preset label, then a deterministic derivation (strip `hf.co/<org>/`, `-GGUF` and the vendor prefix; quant, date, "instruct" and context move to facts; the API vendor is the group header). Two rows in one section with the same name get the quant appended. The full id and facts appear only on hover or keyboard focus, in muted text. | UI-1 |

### 2.5 Routing, API and privacy (FR-R)

| ID | Requirement | Phase |
|---|---|---|
| FR-R-1 | All model calls MUST go through `router.decide()` with a role (features call `router.stream_text`, `stream_with_tools` or `describe_image`, which decide). Roles: `chat` (the conversation, on the thread's pick), `reflex` (screen companions' remarks, `ambient.py`), `classifier`, `memory_writer`, `vision`, `embed`; all but `chat` are local only. Gaps today: embeddings call the local Ollama directly (`memory/embeddings.py`); the `mind` role is a leftover in config that no feature calls. | K0 |
| FR-R-2 | Every API call that may have been billed MUST get a row in the **spend ledger** (with the endpoint id) and the JSONL **audit log** (D-058, D-059). Configurable caps (hour, day, month) MUST be enforced: stop and tell the user, never overspend silently. A model with no catalog price runs while caps are on, labelled "price unknown, not counted against the cap", with a one-time notice (D-083). | K1, UI-1 |
| FR-R-3 | Camera frames, mic audio, screen captures and `memory_writer` jobs MUST be structurally refused by `decide()` for any non-local provider. | K0 |
| FR-R-4 | Selecting an API model is the user's explicit consent to send that thread's text (including recalled memory snippets injected into the prompt). Images the user explicitly attaches MAY go to a vision-capable API model, with a visible badge on that message. | K1, K2 |
| FR-R-5 | API failures (quota, auth, rate limit, timeout, provider error) MUST appear inline on the turn in plain words, with *Retry* and *Switch model* (D-066). **No silent fallback** to another model; a thread on an endpoint that is not active is blocked with its own message (D-059). | K1 |
| FR-R-6 | End-user API keys MUST be stored in the **Windows Credential Manager** (entered in the app), handed to the kernel by the shell at spawn and when changed (stdin), never sent over the socket, never logged, and redacted in the audit log (D-059). `.env` and `config/secrets.local.yaml` are developer-only. | K1 |
| FR-R-7 | **Egress policy (D-025):** content captured *ambiently* (camera, screen capture, OCR watch) MUST NOT reach a non-local model; if a turn needs it the user sees a message, never a silent reroute. Files and images the user explicitly *attaches* are untrusted for authorising actions but MAY go to the chosen API model, with a visible badge on that message. | K1 |

### 2.6 Voice (FR-V)

| ID | Requirement | Phase |
|---|---|---|
| FR-V-1 | TTS MUST go through the provider interface (FR-VP-1). The `gpt_sovits` provider sends every request with the **speaking companion's** `ref_audio_path`, `prompt_text`, `prompt_lang` (contract in `ARCHITECTURE.md`). No weight swapping. Today `synthesize()` picks its engine from `tts.engine`, not from her `voice.provider`; the interface is K2. | K0, K2 |
| FR-V-2 | Text sent to TTS MUST pass the speech-safe normalizer (`audio/speech.py`): no Markdown, emoji, URLs, code fences, reasoning text, stage directions. | K2 |
| FR-V-3 | TTS SHOULD be pipelined one clause ahead of the model's output. | K2 |
| FR-V-4 | One audio **arbiter** MUST ensure only one voice plays at a time; later lines queue. | K2 |
| FR-V-5 | **Barge-in:** speech from the user MUST cancel the current turn's audio and generation and tell the client to stop playback. | K2 |
| FR-V-6 | STT MUST use faster-whisper (default `small`, **CPU**) behind a VAD. Inputs: push-to-talk, a mic button (shown only when it works, FR-C-4) and a hands-free **live voice** mode. Voice starts only when used (D-061). | K2 |
| FR-V-7 | If voice cannot start or the TTS backend goes down, the UI MUST say so plainly and continue **text-only** (D-045, D-061). The `pyttsx3` fallback is an opt-in dev setting (`tts.fallback_engine`, default `none`) because it breaks voice identity. | K0, K2 |
| FR-V-8 | Latency TARGETS (warm, local 9B Q4, TTS up): first token ≤ 1.5 s after send; first audio ≤ 2.5 s after the first sentence is complete; companion switch ready (pre-warm done) ≤ 2 s. Calibrate in K2. | K2 |

### 2.7 Stage view (FR-ST)

| ID | Requirement | Phase |
|---|---|---|
| FR-ST-1 | The stage MUST show the active companion's VRM **in front of the user**, bust-up, centered, dark neutral backdrop (reference: xAI's Ani). | K2 |
| FR-ST-2 | Framing MUST be computed from the VRM's head and chest bones and bounding box. No per-model camera constants. | K2 |
| FR-ST-3 | The avatar MUST have spring-bone physics (hair, ears, accessories), procedural breathing, blinking, glances, eye contact toward the camera with subtle drift, and audio-driven lip-sync (`aa`). | K2 |
| FR-ST-4 | Overlay: live **captions** of her speech, the same input box docked at the bottom, and a chat log that slides in from the side. | K2 |
| FR-ST-5 | If the VRM is missing or invalid, the stage MUST show an instruction panel instead of a blank canvas. | K2 |
| FR-ST-6 | TARGET: 60 fps at 1080p with one companion while the LLM is idle; no worse than 30 fps while generating. Calibrate in K2. | K2 |
| FR-ST-7 | Expression hooks MUST exist on the avatar API. The existing emotion tags (`happy`, `angry`, `sad`, `teasing`, `surprised`, `neutral`) and expression life are kept; new emotion detection is out of scope. | K2 |

### 2.8 Companion creator (FR-CR)

**＋ New companion** is one form. Nothing outside the app is needed (FR-W-2). D-077 supersedes D-008's paste-only box.

| ID | Requirement | Phase |
|---|---|---|
| FR-CR-1 | **Name** (1 to 32 chars), unique slug derived and shown. | K3 |
| FR-CR-2 | **VRM upload**, validated: loads with three-vrm, humanoid bones present (hips, spine, neck, head, both arms and legs), expressions `aa` and `blink` present. WARN (not block) above 150k triangles or 80 MB. A live preview in Stage framing. | K3 |
| FR-CR-3 | **Voice** for the `gpt_sovits` provider: a WAV of **about 8 s** (accepted 3 to 10 s). Checks: duration, clipping (less than 1% of samples at full scale), level, leading/trailing silence, with human-readable messages. The app **auto-transcribes** it with faster-whisper into an editable transcript and detects `ref_lang`. **Test voice** speaks a sample line. Other providers' fields follow FR-VP (the 1.0 voice for buyers is an open question). | K3 |
| FR-CR-4 | **Personality traits** entered as adjective chips (1 to 12, each 2 to 24 chars). | K3 |
| FR-CR-5 | **Write it for me** fills Appendix A with the name and traits and sends it through `router.decide()` as role `chat` with the selected model, so an API pick is never swapped (D-077); the result fills an ordinary **editable** persona box. The user MAY edit it or write it by hand. Failures show like any model failure (FR-R-5). An optional **Copy instruction** gives the same text for use in another LLM. | K3 |
| FR-CR-6 | Validation on save and as the box changes: strip surrounding code fences; reject empty text or leftover `{{placeholders}}`; show a token count; WARN above 1,000 tokens, reject above 4,000. | K3 |
| FR-CR-7 | An optional **Test chat** sends one preview message with the current chat model and the new voice before saving. | K3 |
| FR-CR-8 | **Save** creates the pack atomically (sprite baking joins with pets in 1.1, in the background, failure non-fatal). | K3 |

### 2.9 Desktop pets (FR-P) and 2.10 3D apartment (FR-3D)

Release 1.1, not specified in detail: Appendix B.

### 2.11 Memory (FR-MEM)

| ID | Requirement | Phase |
|---|---|---|
| FR-MEM-1 | Memory is **app-level and shared by all companions** (D-005). It MUST NOT be namespaced or filtered by waifu. | K0 |
| FR-MEM-2 | Message and episode records MUST carry the **speaking companion's name**, and episode summaries MUST name her ("Luna and the user talked about X"), so another companion recalling it does not mistake it for her own experience. | K0 |
| FR-MEM-3 | Memory-writer jobs run on a local model only (FR-R-3). Facts and episodes are superseded, never hard-deleted, restorable, and decay without disappearing. | K0 |
| FR-MEM-4 | The user MUST be able to view, correct and forget remembered facts in Settings → Memory (D-067). | K1 |
| FR-MEM-5 | **Temp Chat:** a per-thread flag (a switch in the top bar, D-068); while on, nothing is read from or written to persistent memory and the memory writer skips those turns. | K1 |

### 2.12 Settings (FR-SET)

| ID | Requirement | Phase |
|---|---|---|
| FR-SET-1 | Sections: **Models** (default model, local rows, Ollama address, API key status, a custom endpoint, budget), **Appearance** (D-073), **Screen** (screen companions now and at start, D-070), **Memory**, **Doctor**, **About** (D-067). Voice and Companions arrive with K2 and K3; a section appears only when it works (D-082). | K1, K2, K3 |
| FR-SET-2 | Settings persist in `settings.json` in app data and apply at once, with no restart (D-070). It wins over `config/config.yaml`, which wins over the code defaults, key by key. Appearance is kept by the page, not in `settings.json` (D-073). | K1 |
| FR-SET-3 | A **Doctor** panel MUST report, each with a fix hint: kernel, Ollama, default local model, embeddings, llama.cpp, voice, speech to text, GPU memory, API models (D-067). Checks are read-only; fix actions arrive with W (FR-COMP-4). | K1, W |

### 2.13 Distribution (FR-DIST)

| ID | Requirement | Phase |
|---|---|---|
| FR-DIST-1 | Ship **one installer**: a per-user NSIS `.exe` built by Tauri's bundler. No portable zip, no `setup.ps1`, no MSIX (D-081). | K1b, K7 |
| FR-DIST-2 | The kernel MUST ship as a **sidecar** (frozen or embedded Python) so end users need no Python or Node. | K7 |
| FR-DIST-3 | Model weights, Ollama and GPT-SoVITS are not inside the installer. The first run sets them up (FR-COMP-2, 3). | W |
| FR-DIST-4 | User data lives in `%APPDATA%\Kokyu` and survives upgrades and uninstall (uninstall asks before removing it). | K7 |
| FR-DIST-5 | The WebView2 runtime MUST be detected; the installer includes the bootstrapper. | K7 |
| FR-DIST-6 | Releases include `docs/THIRD-PARTY.md` (all dependency licenses and shipped-asset rights records) and SHA-256 checksums. | K7 |
| FR-DIST-7 | **Updater:** signed updates (Tauri updater) with a manifest hosted statically; the user is told before an update installs. | K7 |
| FR-DIST-8 | **Diagnostics:** an *Export diagnostics* button zips redacted logs, versions and component states for support. No telemetry by default. | K7 |
| FR-DIST-9 | The installer needs **no admin rights**, is signed, and offers an uninstall that asks before removing user data. | K1b, K7 |
| FR-DIST-10 | **License key:** a signed key (public key compiled into the app) is verified offline and stored in app data; the app explains plainly what an invalid or missing key does. Details depend on the payment provider. | K7 |
| FR-DIST-11 | The application MUST run correctly on a clean Windows machine with no Python, Node, Rust or Git installed. | K1b, K7 |

### 2.14 Components and setup (FR-COMP)

D-080: small setup modules, one per component the app installs itself; no generic component plugin framework.

| ID | Requirement | Phase |
|---|---|---|
| FR-COMP-1 | The kernel MUST detect and health-check each component (Ollama, llama.cpp server, GPT-SoVITS backend, STT model) and report its state, version and size. | K1 (Doctor), W |
| FR-COMP-2 | **Automatic setup at first run** for GPT-SoVITS and the STT model: each has a pinned manifest (URLs, SHA-256, sizes, versions), shows progress, is cancellable and resumable, needs no terminal, and writes only inside the app-data directory. | W |
| FR-COMP-3 | **Ollama** is installed through its official installer, which the app opens with the user's consent. Components the app starts are children under the Job Object; externally managed ones (Ollama as a service) are only monitored. | W |
| FR-COMP-4 | Everything else is detected and repaired through Doctor: every problem maps to a plain-language message with one primary action (*Open the installer*, *Start*, *Retry*). | W |
| FR-COMP-5 | The Doctor panel (FR-SET-3) is the UI for components. Development keeps the existing GPT-SoVITS install (D-042). | K1, W |

### 2.15 First run (FR-WIZ)

| ID | Requirement | Phase |
|---|---|---|
| FR-WIZ-1 | First launch MUST open a short graphical first-run flow; it can be re-run from Settings. | W |
| FR-WIZ-2 | Steps: model or key → companion (premade or create) → setup (FR-COMP-2, 3) → done. | W |
| FR-WIZ-3 | Only a working **model** is mandatory. Voice setup shows progress and can be skipped or finished later; a first text conversation never waits for it. | W |
| FR-WIZ-4 | The model step reports GPU, VRAM and RAM and recommends API-only, a small local model or full local. It never blocks. | W |
| FR-WIZ-5 | The key step explains what a key is and what it costs, links to the provider's key page, has a **Test key** button, and stores the key in the Credential Manager. | W |
| FR-WIZ-6 | No terminal and no manual file editing anywhere in the first run. | W |
| FR-WIZ-7 | TARGET: on a clean machine, installer to first reply on the API path in under 10 minutes excluding downloads. Measured at the W checkpoint. | W |

### 2.16 Voice providers (FR-VP)

| ID | Requirement | Phase |
|---|---|---|
| FR-VP-1 | Voice MUST go through a provider interface `synthesize(text, voice) → audio stream` with providers `builtin`, `gpt_sovits` and `elevenlabs` (D-036). | K2 |
| FR-VP-2 | A companion's `voice` block names its provider and that provider's parameters; no other field changes (FR-W-3 holds). | K0, K2 |
| FR-VP-3 | Cloud providers are **opt-in**; choosing one is consent for the spoken text to leave the machine, shown with a cloud badge. Mic audio and camera frames never leave (FR-R-3). | K2 |
| FR-VP-4 | Provider failure shows a message and continues text-only (FR-V-7). | K2 |
| FR-VP-5 | The default provider on a fresh install is `builtin`, so the first conversation never waits for a download; its model is chosen in a K2 spike (license, quality, CPU latency). How buyers get the premades' voices is open (ties to D-080). | K2 |

### 2.17 Screen companions (FR-SC) — D-048

**Task Guide** (the user names a task; she nudges when the screen drifts away from it) and **OCR watch** (rare, unprompted remarks about something notable on screen).

| ID | Requirement | Phase |
|---|---|---|
| FR-SC-1 | Both modes are **opt-in and off by default** on every launch unless the user turned them on at start in Settings → Screen (D-070); each is toggled from the `＋` tray and Settings. | K1 |
| FR-SC-2 | While either mode is on, a **visible indicator** (a chip under the input box, D-069) shows which one is watching the screen, and one click stops it. | K1 |
| FR-SC-3 | Screen captures for these modes are **ambient content**: processed by local models only, never sent to an API model (FR-R-7). Without a local vision model the mode refuses to start with a plain message (D-056). | K1 |
| FR-SC-4 | Task Guide: the user states a task in words; the kernel checks the screen on an interval and, when the user has drifted for the configured time, the **active companion** says a short nudge in her own persona. Ending or replacing the task is one action. | K1 |
| FR-SC-5 | OCR watch: remarks are rare by design (configurable minimum interval, default no more than one every few minutes) and skipped while the user is typing or a turn is running. | K1 |
| FR-SC-6 | Remarks are spoken through the arbiter like any reply (never over the user or another reply) and appear in the current thread marked as unprompted; they follow Temp Chat (FR-MEM-5). | K2 |

### 2.18 Conversation modes (FR-MODE) — D-074

Two independent choices: what kind of conversation a **thread** is (Chat or Roleplay), and whether **voice** is on in the window (D-061; the Stage joins it in K2). A mode belongs to the thread, never to a companion (D-003): every companion does every mode with the same model, tools and permissions. Six answers in D-074 were assumed and await the user's confirmation.

| ID | Requirement | Phase |
|---|---|---|
| FR-MODE-1 | Every thread has a **mode**, `chat` or `roleplay`, chosen when it is created and fixed for its life. Threads that existed before modes are `chat`. Search, rename, delete, model, effort and Temp Chat work the same in both. | K1c |
| FR-MODE-2 | The system message is built from layers, in order: **persona** (the companion's prompt: who she is, never format or length rules), the **mode layer** (one text per mode, the same for every companion), the **delivery layer** (only while voice is on), then the app addendum (emotion tag, honesty about abilities; the tool guidance only in modes that offer tools). | K1c |
| FR-MODE-3 | **Chat:** she answers as herself but plainly, in about 3 to 4 lines, longer only when the task needs it (code, steps, a list asked for); Markdown when it helps; no action narration. Tools are offered as before. App memory (FR-MEM) is read and written as before. | K1c |
| FR-MODE-4 | **Roleplay:** she stays in character and writes in the roleplay format: `*action or narration*`, dialogue as plain or quoted text, `**emphasis**`, `(OOC: …)` or `((…))` out of character; a paragraph or two per reply. **No tools are offered.** The user's name and profile are read from app memory, but **nothing from a roleplay thread is written to app memory**. | K1c |
| FR-MODE-5 | **Story memory:** each roleplay thread keeps a running summary, written locally by the memory-writer role (D-015) after replies and fed into every turn of that thread, so a long story keeps its beginning. It never leaves the thread; Temp Chat keeps none. | K1c |
| FR-MODE-6 | **New roleplay** starts from a **scenario card**: title, setting, who the user is, who she is to the user, the opening message, and optional rules; every field may be empty (*Blank roleplay*). The opening message, when given, is stored as her first message. Cards are saved locally and can be started again, edited or deleted. | K1c |
| FR-MODE-7 | In roleplay threads the client shows `*…*` in italic and softer, `**…**` in bold and out-of-character asides small and muted; chat threads keep ordinary Markdown (FR-C-8), so parentheses there stay plain text. A roleplay thread is marked in the sidebar. | K1c |
| FR-MODE-8 | While voice is on, the delivery layer asks for short spoken lines without lists, Markdown, symbols, quotes or dashes; and in roleplay threads **only her dialogue is spoken**: actions, narration and out-of-character text are removed by code before speech, whatever the model wrote. | K1c |
| FR-MODE-9 | Screen companions (FR-SC-4, 5) never post remarks into a roleplay thread; they stay quiet while one is open. | K1c |
| FR-MODE-10 | In K2 a roleplay action may drive the avatar (an expression or gesture named in the action). | K2 |

## 3. Data formats

### 3.1 `waifu.yaml` (schema 1)

```yaml
schema: 1
id: yuri                  # [a-z0-9-]{2,32}, immutable
name: Yuri                # 1–32 chars
traits: [calm, teasing, curious]   # 1–12 adjectives
vrm: model.vrm
prompt: persona.md        # the persona: written in the creator (FR-CR-5); premades point at persona.md (D-074)
voice:
  provider: gpt_sovits    # builtin | gpt_sovits | elevenlabs
  ref_audio: voice/ref.wav                    # gpt_sovits only
  ref_text: "exact transcript of the clip"    # gpt_sovits only
  ref_lang: en                                # gpt_sovits only
  # builtin: `voice: <name>`    elevenlabs: `voice_id: <id>` (key is in the credential store, never here)
created: 2026-11-11T12:00:00Z
```

There are deliberately **no** `models`, `tools`, `permissions`, `memory` or `scene` keys.

### 3.2 Room data (1.1)

The room format is open (Appendix B, D-078). The v1.0 `scene.yaml` draft is withdrawn.

### 3.3 `settings.json`

Lives in the app data folder and holds only what Settings edits, in `config.yaml`'s own layout (D-070): `llm.base_url` and `providers.local_ollama.base_url`; `budget.enabled`, `budget.hourly_usd`, `daily_usd`, `monthly_usd` (-1 = no cap); a custom endpoint under `providers.airouter.*`; `task_guide.on_at_start` and `ocr_watch.on_at_start`. Secrets are **not** stored here (FR-R-6). Appearance (theme, accent, message style, text size) is the page's own, kept in `localStorage` as `kokyu.theme` (D-073).

### 3.4 Model references

`<kind>:<backend>/<id>`, for example `local:ollama/qwen3.5:9b`, `local:llamacpp/<preset id>`, `api:<endpoint id>/<catalog-id>` (D-059; old `api:airouter/…` refs keep working).

### 3.5 Threads database (`threads.db`, SQLite, schema 5)

```
threads(id TEXT PK, title, created_at, updated_at, active_waifu_id, model_ref, effort, temp, archived,
        efforts JSON, mode TEXT DEFAULT 'chat', scenario JSON)          -- efforts: D-064; mode, scenario: D-074
story_memory(thread_id TEXT PK, summary, through_message_id, updated_at)  -- FR-MODE-5, roleplay only
scenarios(id TEXT PK, title, card JSON, created_at, updated_at)         -- FR-MODE-6, saved cards
messages(id INTEGER PK, thread_id, ts, role,            -- user | assistant | divider
         speaker_waifu_id, speaker_name, content, model_ref, effort,
         tokens_in, tokens_out, meta JSON)
attachments(id INTEGER PK, message_id, kind, path, mime, size)
kv(key TEXT PK, value)
```

Memory lives in a **separate** database (`memory.db`, schema 3, sqlite-vec) and is untouched by waifu ids.

## 4. Non-functional requirements

### 4.1 Performance and resources (TARGETS, 12 GB VRAM)

| Item | TARGET | Calibrate |
|---|---|---|
| Idle kernel RAM | under 600 MB | K6 |
| Stage + 9B Q4 + TTS + embeddings resident | fits in 12 GB with at least 1 GB headroom | K2 |
| Local to local model switch (same backend) | progress within 100 ms, ready in 15 s cold | K6 |

The VRAM manager reads the GPU through the driver's NVML (D-065). Estimates in docs are planning numbers; measured values replace them in `STATE.md`.

### 4.2 Reliability

- Graceful shutdown: tray Quit asks the kernel to finish memory consolidation, then closes children; hard kill after about 5 s.
- All file writes (settings, packs) are atomic (write temp, then rename).
- A crashed child process (TTS backend, llama-server) is reported and restartable from the UI; it never takes the kernel down.

### 4.3 Privacy and security

- Local-first; the only outbound traffic is the user's chosen API calls and the model-catalog refresh (and first-run downloads, FR-COMP-2).
- Tauri CSP locks the webview to the bundled app and the loopback kernel; no remote scripts.
- Keys never in the repo, logs, audit log or crash reports.
- The kernel binds to **127.0.0.1** only; its socket refuses other origins (D-057).
- Untrusted content (file text, OCR, web) is marked untrusted on the bus and can never authorise an action by itself.

### 4.4 Accessibility and UX

Reduced-motion setting; keyboard-reachable controls; visible focus; contrast at least WCAG AA for UI text; English only in v1. UI strings are written inline in the components (not centralized); the copy rule in FR-C-4 applies to all of them.

### 4.5 Observability

Logs in `logs/` (kernel, backends), a per-turn **latency row** (model first token, TTS first audio, total), the router audit log, and the spend ledger.

### 4.6 Portability (packaging-ready from day one)

No absolute paths; all locations from `KASANE/paths.py`; no assumption that a repo checkout or dev tools exist at runtime; config layering: code defaults, then `config.yaml`, then `settings.json` (D-070). Environment variables only for developer keys and the data and resource folders.

## 5. Error and empty states

| Situation | Behaviour |
|---|---|
| No companion installed (a fresh clone: premade packs are untracked assets) | The chip says "No companion"; a neutral built-in persona answers (D-062) |
| No local models | The Local section is empty with the reason; API works if a key is saved (D-054) |
| No API key | API rows listed greyed, "needs an API key"; *Key* in the API heading saves one (D-059) |
| Voice cannot start | The voice chip under the input box says why, with *Try again*; replies continue text-only (D-061, FR-V-7) |
| Model will not fit or fails to load | The waking-up card names what holds the memory, with *Unload X* where offered, *Try again* and *Switch model* (D-065, D-071) |
| API quota or error | A card under the turn in plain words, with *Details*, *Retry*, *Switch model* (FR-R-5, D-066) |
| Thread on an endpoint that is not active | Blocked with its own message, never sent to another provider (D-059) |
| Connection lost | Today the sidebar status reads "Kernel offline". UI-1: a plain banner with *Reconnect*, no internal words (FR-C-4) |
| VRM missing (K2) | Stage instruction panel (FR-ST-5) |
| Mic permission denied (K2) | A message with how to enable it in Windows settings |

## 6. Out of scope

Agent mode is not planned; VR is deferred long term (D-079).
Also out: mobile, web hosting, multi-user; fine-tuned GPT-SoVITS weights; Live2D; marketplace or companion sharing; shell execution; emotion detection (hooks only); per-companion models, tools or permissions.

## 7. Phase acceptance matrix

In delivery order (D-085, amended by D-086; provisional). A checkpoint is open until the user ticks it in `STATE.md` (D-076).

| Phase | Requirements delivered | Checkpoint |
|---|---|---|
| K0 | FR-W-1..4, 6, 7; FR-S-5; FR-R-1, 3; FR-V-1 (gpt_sovits per companion), FR-V-7 (text-only); FR-MEM-1..3 | Open (window and voice not run) |
| K1 | FR-C-1..6, 8..10; FR-S-1, 2; FR-M-1..11; FR-R-1, 2, 4..7; FR-MEM-4, 5; FR-SET-1..3; FR-SC-1..5 | Open |
| K1c | FR-MODE-1..9 (D-074, D-075) | Open (the user ran the build 2026-11-17; items not ticked) |
| UI-1 | FR-M-12 (done, `883f4f7`); FR-C-4 (only working controls, copy rule) and §5 connection banner (done, `a412120`); FR-R-2 (unpriced models, D-083) | In progress |
| UI-2 | The design standard (D-086): `DESIGN.md`, tokens, primitives, applied to every surface | Not started |
| K1b | FR-DIST-1, 9, 11 (walking-skeleton installer on a clean machine) | Not started |
| K2 | FR-C-4 (camera, screenshot, paste image), FR-C-7; FR-S-3, 4; FR-ST-1..7; FR-V-1 (provider interface), 2..6, 8; FR-VP-1..5; FR-SC-6; FR-MODE-10; FR-SET-1 (Voice) | Not started |
| K3 | FR-W-2 (UI), FR-W-5; FR-CR-1..8; FR-SET-1 (Companions) | Not started |
| W | FR-COMP-1..5; FR-WIZ-1..7; FR-DIST-3; FR-SET-3 (fix actions) | Not started |
| K6 | NFR calibration (§4), evals, crash recovery, docs | Not started |
| K7 | FR-DIST-1..11 | Not started |
| K4 (1.1) | FR-P-1..6 | Not started |
| K5 (1.1) | FR-3D-1..6 | Not started |

## Appendix A: persona instruction template (canonical)

The app fills `{{name}}` and `{{traits}}`. **Write it for me** sends the result through `router.decide()` with the selected model; **Copy instruction** offers the same text (FR-CR-5). To be stored as a kernel resource (K3); this text is the source of truth.

````
You are writing a system prompt for a conversational AI companion character. The prompt you write will be given to a language model so it can play this character.

Character name: {{name}}
Personality traits: {{traits}}

Requirements for the system prompt you write:
1. Address the model directly in second person ("You are {{name}}, ...").
2. Describe her personality, tone and speech habits so that every listed trait is clearly visible in how she talks. Do not simply list the traits.
3. Describe only who she is. Do not give rules about format, length, Markdown, actions or speech: the app adds those per conversation mode (Chat or Roleplay) and while her voice is on (D-074).
4. Tell the model to stay in character at all times and not to mention being a language model, a prompt or these instructions unless the user directly asks.
5. Do not give her special abilities, tools or knowledge limits. Her intelligence and capabilities are those of the underlying model; the prompt only shapes personality and voice.
6. Do not describe a scene, a setting or a story for her; the user's roleplay scenarios provide those (D-074).
7. Length: 200 to 350 words.
8. Output only the system prompt itself, inside a single code block, with no commentary before or after it.
````

## Appendix B: Release 1.1+ (not specified in detail)

Planned for 1.1 (D-034, D-085): desktop pets in K4, the 3D apartment in K5, built from Luna's apartment (D-078). Rows keep their IDs; each is designed in its phase.

| ID | Requirement |
|---|---|
| FR-P-1 | A companion can be brought out as a **2D pet**, one to three at once; the entry point is designed in K4 (no control before it works, FR-C-4). |
| FR-P-2 | Sprites are **baked from her VRM**: orthographic, transparent renders through VRMA clips (idle, sit, walk) into an atlas (PNG + JSON); procedural idle and walk without clips. |
| FR-P-3 | Behaviour: idle, sit, walk left and right along the bottom of the work area, react to a click, dragged, small looks and gestures. |
| FR-P-4 | Pets render in one transparent, undecorated, always-on-top overlay per monitor (primary only), hidden from the taskbar, click-through except over opaque pixels. A K4 spike confirms this beats one window per pet (D-014). |
| FR-P-5 | Clicking a pet opens a quick reply and a speech bubble; she speaks through the arbiter. Right-click: open chat, dismiss. |
| FR-P-6 | Pets live while the app runs in the tray; closing the main window does not close them. TARGET: under 2% CPU walking, about zero GPU. |
| FR-3D-1 | The room is a prebuilt GLB apartment supplied as a **user asset**, with a collision mesh she and the user share. |
| FR-3D-2 | Two cameras: a spectator free-fly camera and a first-person **visitor** camera (WASD, pointer lock, about 1.5 m eye height, walk and run), clamped to the walkable area. |
| FR-3D-3 | She wanders the walkable area with walk start, loop and stop clips sized to her hip height. |
| FR-3D-4 | Time-of-day lighting (dawn, day, dusk, night), with a light that follows her. |
| FR-3D-5 | Conversation by voice or a text overlay; one voice at a time (FR-V-4). |
| FR-3D-6 | Two companions in one room: open (below). |

**Open, to design later:** real room and anchor data (Luna's floorplan is one placeholder rectangle); the rights to a room that can ship; VRAM beside the LLM and TTS; two-companion scenes (who speaks next, both reacting to what the user says).
