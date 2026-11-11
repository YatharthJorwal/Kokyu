# SPEC — Kōkyū

Requirements with stable IDs. TODO items, tests and commits reference these IDs. Overview: `SCOPE.md`. Design: `ARCHITECTURE.md`.

- **MUST / SHOULD / MAY** follow RFC 2119 usage.
- **TARGET** marks a number that is a goal to be *measured and calibrated* in the named phase; it is not a verified fact.
- **Phase** column says when the requirement is delivered (T, K0 to K7; D = deferred).
- Version: spec v0.1, 2026-11-11.

## 1. Definitions

| Term | Meaning |
|---|---|
| **Waifu** | A companion defined by: name, traits, system prompt, VRM, voice clip. Nothing else. |
| **Thread** | One conversation. Has one active waifu, one chat model, one effort setting. |
| **Turn** | One user message and the reply it triggers. |
| **Chat model** | The single user-selected model for a thread. Local or API. |
| **Helper model** | A background model (classifier, memory writer, embeddings, vision). Never user-facing, always local. |
| **Kernel** | KASANE, the Python process holding all logic. |
| **Client** | Main window or pet overlay. Renders kernel state, holds no business logic. |
| **Stage** | The view where the active waifu's VRM stands in front of the user. |
| **Pet** | A 2D sprite of a waifu living on the desktop. |
| **Scene** | A 3D space (apartment, garden) the user walks in with WASD. |
| **TTS backend** | The external headless GPT-SoVITS server (see `TTS-BACKEND.md`). |

## 2. Functional requirements

### 2.1 Waifus (FR-W)

| ID | Requirement | Phase |
|---|---|---|
| FR-W-1 | A waifu MUST consist of exactly: `id`, `name`, `traits[]`, `prompt`, `vrm`, `voice{ref_audio, ref_text, ref_lang}`, plus a derived `pet/` atlas. | K0 |
| FR-W-2 | Waifus MUST live in the app-data directory (`waifus/<id>/`). They MUST be created, edited and deleted only through the app UI (K3). A dev seed script MAY import Luna and Yuri before the creator exists. | K0, K3 |
| FR-W-3 | **Invariance:** for the same thread state and input, switching the active waifu MUST NOT change model selection, effort, router decisions, available tools, permissions or memory recall results. Only the system prompt, TTS parameters, VRM and pet sprites differ. A parameterized test over two fixture waifus MUST enforce this. | K0 |
| FR-W-4 | `id` is an immutable slug (`[a-z0-9-]{2,32}`). The display `name` (1 to 32 chars) MAY be renamed. | K0 |
| FR-W-5 | Deleting a waifu MUST remove her pack and sprites. Existing messages keep a **snapshot of her name** and render as "(deleted)" if needed. | K3 |
| FR-W-6 | Waifu packs MUST be validated on load; an invalid pack is skipped and reported in the UI and log, never crashing the kernel. | K0 |

### 2.2 Chat (FR-C)

| ID | Requirement | Phase |
|---|---|---|
| FR-C-1 | Threads MUST be creatable, renamable, deletable and searchable (title and message text). Stored in SQLite. | K1 |
| FR-C-2 | Replies MUST stream token by token. **Stop** MUST halt generation (TARGET ≤ 300 ms) and keep the partial reply. Audio stops with it (TARGET ≤ 200 ms). | K1 |
| FR-C-3 | The input box MUST be centered, multi-line (`Enter` sends, `Shift+Enter` newline), accept pasted images and dragged files. | K1 |
| FR-C-4 | The `＋` tray MUST offer: upload file, camera, voice, screenshot, paste image. Items not yet implemented are visibly disabled, not hidden. | K1 stubs, K2 live |
| FR-C-5 | The **heart animation** (ported from Yuri) MUST show three states: idle, thinking, replying. It respects the reduced-motion setting. | K1 |
| FR-C-6 | The sidebar MUST show waifus at top, history in the middle (grouped Today / Yesterday / Previous 7 days / Older, with the waifu's avatar badge), and **Settings** at the bottom. | K1 |
| FR-C-7 | A **Chat / Stage** toggle MUST switch views of the same thread without losing state. | K2 |
| FR-C-8 | Replies MUST render Markdown (code blocks with a copy button). What is *spoken* is the speech-safe version (FR-V-2). | K1 |
| FR-C-9 | Each assistant message SHOULD offer *Copy* and *Regenerate*. | K1 |
| FR-C-10 | Messages MUST record: speaker waifu id and name snapshot, model ref, effort, timestamps, token counts where known. | K1 |

### 2.3 Waifu switcher (FR-S)

| ID | Requirement | Phase |
|---|---|---|
| FR-S-1 | A chip in the input row MUST show the active waifu's avatar and name. Its popover is a searchable list plus "＋ New waifu". | K1 |
| FR-S-2 | Switching MUST insert a visible divider ("Switched to Luna"), apply from the **next** turn (a turn in flight finishes with the old waifu), and keep prior messages on screen tagged with their speaker. | K1 |
| FR-S-3 | Switching MUST send a short TTS **pre-warm** for the new waifu so the first real line is not slower. | K2 |
| FR-S-4 | Clicking a waifu in the sidebar MUST open or continue a thread with her in **Stage** view. Clicking a history entry MUST open **Chat** view. | K2 |
| FR-S-5 | Switching MUST NOT alter the model chip, the effort slider or any permission (see FR-W-3). | K0 |

### 2.4 Model switcher and effort (FR-M)

| ID | Requirement | Phase |
|---|---|---|
| FR-M-1 | There MUST be **one** model control: a chip in the input row showing the current model and effort label. | K1 |
| FR-M-2 | Its popover MUST have a search box and two clearly separated sections, **Local** and **API**, as one list (not a toggle). The current model carries a check mark. Picking a row is the whole action. | K1 |
| FR-M-3 | **Local** lists Ollama models (`GET /api/tags`) plus llama.cpp presets from `config/models.yaml`. Each row shows size and a *fits / won't fit* hint from the VRAM manager. | K1 |
| FR-M-4 | **API** lists the AI Router catalog (`/v1/models`), grouped by provider, with variant badges and a price hint when the catalog provides one. The catalog is cached; offline it shows the cache marked *stale*. A refresh button re-fetches. | K1 |
| FR-M-5 | The selection is **per thread**; new threads inherit the last selection. It is independent of the waifu. | K1 |
| FR-M-6 | Selecting a local model on a different backend MUST unload the other backend's large model first (VRAM manager) and show progress on the chip. Load failures are shown inline. | K1 |
| FR-M-7 | The chip MUST show a local or cloud icon. Spend so far and the budget cap appear in the popover footer. | K1 |
| FR-M-8 | **Effort slider**, inside the popover, with a short label on the chip. Discrete detents drawn from the canonical set `off, low, medium, high, max`, **restricted to what the selected model supports** (FR-M-10). If none are supported, no slider is shown. | K1 |
| FR-M-9 | The slider MUST be animated: the thumb glides between detents with a short spring; the track fill and a soft pulsing glow scale in intensity and speed with the level; during generation the glow runs on the chip. Reduced-motion turns this into a static fill. | K1 |
| FR-M-10 | Effort support is data: from catalog flags for API models and from `config/models.yaml` for local models. Mapping: API → the provider's reasoning-effort parameter; local → thinking on/off plus a thinking-token budget per detent where the model/backend supports it. | K1 |
| FR-M-11 | Effort is remembered per model per thread. Reasoning text is never spoken and is hidden from the chat by default (collapsible *Thoughts* block MAY be added later). | K1 |

### 2.5 Routing, API and privacy (FR-R)

| ID | Requirement | Phase |
|---|---|---|
| FR-R-1 | All model calls MUST go through `router.decide(role, request, config, state)`. Roles: `chat`, `classifier`, `memory_writer`, `embed`, `vision`. | K0 |
| FR-R-2 | The AI Router provider MUST record every call in a **spend ledger** and a JSONL **audit log**, and MUST enforce a configurable budget cap (stop and tell the user; never overspend silently). | K1 |
| FR-R-3 | Camera frames, mic audio, screen captures and `memory_writer` jobs MUST be structurally refused by `decide()` for any non-local provider. | K0 |
| FR-R-4 | Selecting an API model is the user's explicit consent to send that thread's text (including recalled memory snippets injected into the prompt). Images the user explicitly attaches MAY go to a vision-capable API model, with a visible badge on that message. | K1, K2 |
| FR-R-5 | API failures (quota, auth, rate limit, timeout, provider error) MUST appear inline on the turn with *Retry* and *Switch model*. **No silent fallback** to another model. | K1 |
| FR-R-6 | The API key MUST come from `.env` or `config/secrets.local.yaml`, never be logged, and be redacted in the audit log. | K1 |
| FR-R-7 | **Egress policy (D-025):** content captured *ambiently* (camera, screen capture, OCR watch) MUST NOT reach a non-local model; if a turn needs it the user sees a message, never a silent reroute. Files and images the user explicitly *attaches* are untrusted for authorising actions but MAY go to the user's chosen API model, with a visible badge on that message. | K1 |

### 2.6 Voice (FR-V)

| ID | Requirement | Phase |
|---|---|---|
| FR-V-1 | TTS MUST go through a single adapter that speaks the contract in `TTS-BACKEND.md`: every request carries `ref_audio_path`, `prompt_text`, `prompt_lang` of the **speaking waifu**. No weight swapping. | K0, K2 |
| FR-V-2 | Text sent to TTS MUST pass the speech-safe normalizer (ported from Yuri's `audio/speech.py`): no markdown, emoji, URLs, code fences, reasoning text, stage directions. | K2 |
| FR-V-3 | TTS SHOULD be pipelined one clause ahead of the model's output. | K2 |
| FR-V-4 | One audio **arbiter** MUST ensure only one voice plays at a time; later lines queue. | K2 |
| FR-V-5 | **Barge-in:** speech from the user MUST cancel the current turn's audio and generation and tell the client to stop playback. | K2 |
| FR-V-6 | STT MUST use faster-whisper (default `small`, **CPU**) behind a VAD. Inputs: push-to-talk (global hotkey, default F9), a mic toggle, and a hands-free **live voice** mode. | K2 |
| FR-V-7 | If the TTS backend is unreachable the UI MUST show a clear banner and continue **text-only**. The `pyttsx3` fallback exists only as an opt-in dev setting (default off), because it breaks voice identity. (Yuri's current default is the opposite; K0-11 flips it.) | K0, K2 |
| FR-V-8 | Latency TARGETS (warm, local 9B Q4, TTS up): first token ≤ 1.5 s after send; first audio ≤ 2.5 s after the first sentence is complete; waifu switch ready (pre-warm done) ≤ 2 s. Calibrate in K2. | K2 |

### 2.7 Stage view (FR-ST)

| ID | Requirement | Phase |
|---|---|---|
| FR-ST-1 | The stage MUST show the active waifu's VRM **in front of the user**, bust-up, centered, dark neutral backdrop (reference: xAI's Ani). | K2 |
| FR-ST-2 | Framing MUST be computed from the VRM's head and chest bones and bounding box. No per-model camera constants. | K2 |
| FR-ST-3 | The avatar MUST have spring-bone physics (hair, ears, accessories), procedural breathing, blinking, glances, eye contact toward the camera with subtle drift, and audio-driven lip-sync (`aa`). | K2 |
| FR-ST-4 | Overlay: live **captions** of her speech, the same input box docked at the bottom with a mic button, and a chat log that slides in from the side. | K2 |
| FR-ST-5 | If the VRM is missing or invalid, the stage MUST show an instruction panel instead of a blank canvas. | K2 |
| FR-ST-6 | TARGET: 60 fps at 1080p with one waifu while the LLM is idle; no worse than 30 fps while generating. Calibrate in K2. | K2 |
| FR-ST-7 | Expression hooks MUST exist on the avatar API. Yuri's existing emotion tags (`happy`, `angry`, `sad`, `teasing`, `surprised`, `neutral`) and expression life are kept; new emotion detection is out of scope for v1. | K2 |

### 2.8 Waifu creator (FR-CR)

"＋ New waifu" is one form. Nothing outside the app is needed (FR-W-2).

| ID | Requirement | Phase |
|---|---|---|
| FR-CR-1 | **Name** (1 to 32 chars), unique slug derived and shown. | K3 |
| FR-CR-2 | **VRM upload**, validated: loads with three-vrm, humanoid bones present (hips, spine, neck, head, both arms and legs), expressions `aa` and `blink` present. WARN (not block) above 150k triangles or 80 MB. A live preview in Stage framing. | K3 |
| FR-CR-3 | **Voice upload**: WAV, **about 8 s** (accepted 3 to 10 s). Checks: duration, clipping (less than 1% of samples at full scale), level, leading/trailing silence, with human-readable messages. The app **auto-transcribes** it with faster-whisper into an editable *transcript* field (required by GPT-SoVITS) and detects `ref_lang`. A **Test voice** button speaks a sample line through the TTS backend. | K3 |
| FR-CR-4 | **Personality traits** entered as adjective chips (1 to 12, each 2 to 24 chars). | K3 |
| FR-CR-5 | **System prompt box** is **paste-only**: typing is disabled; only the *Paste* button and `Ctrl+V` fill it. Above it, an **Instruction block** is generated from the name and traits (Appendix A) with a **Copy instruction** button. Flow: copy the instruction → paste into any LLM → copy the LLM's prompt → paste into the box. | K3 |
| FR-CR-6 | On paste: strip surrounding code fences; reject empty text or leftover `{{placeholders}}`; show a token count; WARN above 1,000 tokens, reject above 4,000. **Clear** resets the box; changing the prompt means re-pasting. | K3 |
| FR-CR-7 | An optional **Test chat** sends one preview message with the current chat model and the new voice before saving. | K3 |
| FR-CR-8 | **Save** creates the pack and bakes pet sprites in the background (progress shown, failure non-fatal). | K3 |

### 2.9 Desktop pets (FR-P)

| ID | Requirement | Phase |
|---|---|---|
| FR-P-1 | A waifu MUST be bringable out as a **2D pet** from the chat header or the sidebar's right-click menu. One to three pets at once. | K4 |
| FR-P-2 | Pet sprites MUST be **baked from her VRM**: orthographic, transparent-background renders through VRMA clips (idle, sit, walk) into an atlas (PNG + JSON). Without VRMA clips, procedural idle/walk are baked. | K4 |
| FR-P-3 | Behaviour state machine: idle, sit, walk left/right (mirrored), react to click, dragged, small looks and gestures. She walks along the bottom of the work area and MAY sit on its edge. | K4 |
| FR-P-4 | Pets render in **one transparent, undecorated, always-on-top overlay window per monitor** (primary monitor only in v1), hidden from the taskbar, **click-through except over opaque pixels** (alpha hit-testing). A K4 spike MUST confirm this beats one-window-per-pet (see D-014). | K4 |
| FR-P-5 | Clicking a pet opens a compact quick-reply box and speech bubble. She speaks through the normal arbiter. Right-click menu: open chat, send to 3D scene, dismiss. | K4 |
| FR-P-6 | Pets MUST live while the kernel runs (tray); closing the main window does not close them. TARGET: under 2% CPU walking, about zero GPU, measured in K4. | K4 |

### 2.10 3D mode (FR-3D)

| ID | Requirement | Phase |
|---|---|---|
| FR-3D-1 | A "3D" button on the stage MUST place the user in a scene. Movement: first-person **WASD**, mouse look (pointer lock), Shift sprint, `Esc` releases the cursor. Collision from per-scene collider data. | K5 |
| FR-3D-2 | Scenes MUST be packs (`scenes/<id>/scene.glb` + `scene.yaml`) switchable from a menu **without restart**. v1 ships **apartment** and **garden**. | K5 |
| FR-3D-3 | The user MUST be able to bring **one or two** waifus in. Each spawns at an anchor, idles, wanders along waypoints, turns to face the user and walks over when addressed. | K5 |
| FR-3D-4 | With two waifus, a helper classifier picks who answers (addressed by name, else relevance); one voice at a time. Each reply is generated with **only that waifu's prompt**; the other's lines are passed as quoted context to prevent persona bleed. | K5 |
| FR-3D-5 | Conversation in 3D is by voice or a text overlay. | K5 |
| FR-3D-6 | Budget TARGETS: at most about 300k triangles per scene, baked lighting. The renderer MUST stay XR-compatible (no XR code in v1). | K5 |

### 2.11 Memory (FR-MEM)

| ID | Requirement | Phase |
|---|---|---|
| FR-MEM-1 | Memory is **app-level and shared by all waifus** (D-005). It MUST NOT be namespaced or filtered by waifu. | K0 |
| FR-MEM-2 | Message and episode records MUST carry the **speaking waifu's name**, and episode summaries MUST name her ("Luna and the user talked about X"), so another waifu recalling it does not mistake it for her own experience. | K0 |
| FR-MEM-3 | Memory-writer jobs run on a local helper model only (FR-R-3). Facts and episodes follow Yuri's memory v2 behaviour: supersede, never hard-delete, restorable, decay without disappearing. | K0 |
| FR-MEM-4 | The user MUST be able to view, correct and delete remembered facts in Settings → Memory. | K1 |
| FR-MEM-5 | **Temp Chat** (inherited from Yuri): a per-thread flag; while on, nothing is read from or written to persistent memory and the memory writer skips those turns. | K1 |

### 2.12 Settings (FR-SET)

| ID | Requirement | Phase |
|---|---|---|
| FR-SET-1 | Sections: **Models** (Ollama URL, llama.cpp presets, AI Router key status and budget), **Voice** (TTS backend path/URL, STT model and device, hotkey, devices), **Waifus** (manage), **Scenes**, **Pets**, **Memory**, **Advanced** (helper models, logging, dev fallbacks), **About** (versions, licenses). | K1+ |
| FR-SET-2 | Settings persist in `settings.json` in app data and apply without restart wherever possible. | K1 |
| FR-SET-3 | A **Doctor** panel MUST report: kernel health, Ollama reachable, llama.cpp reachable, TTS backend health, STT ready, GPU/VRAM, API key and catalog status, each with a fix hint. | K1 |

### 2.13 Distribution (FR-DIST) — later

| ID | Requirement | Phase |
|---|---|---|
| FR-DIST-1 | Ship a **Windows installer** (NSIS via Tauri bundler) *and* a **portable bundle** with `setup.ps1` and README setup instructions. | K7 |
| FR-DIST-2 | The kernel MUST ship as a **sidecar** (frozen or embedded Python) so end users need no Python or Node. | K7 |
| FR-DIST-3 | Model weights and the GPT-SoVITS backend are **not bundled**. First-run checklist detects them and links to install steps. | K7 |
| FR-DIST-4 | User data lives in `%APPDATA%\Kokyu` and survives upgrades and uninstall (uninstall asks before removing it). | K7 |
| FR-DIST-5 | The WebView2 runtime MUST be detected; the installer includes the bootstrapper. | K7 |
| FR-DIST-6 | Releases include `docs/THIRD-PARTY.md` (all dependency licenses) and SHA-256 checksums. | K7 |

## 3. Data formats

### 3.1 `waifu.yaml` (schema 1)

```yaml
schema: 1
id: yuri                  # [a-z0-9-]{2,32}, immutable
name: Yuri                # 1–32 chars
traits: [calm, teasing, curious]   # 1–12 adjectives
vrm: model.vrm
prompt: prompt.md         # system prompt, pasted in the creator
voice:
  ref_audio: voice/ref.wav
  ref_text: "exact transcript of the clip"
  ref_lang: en            # tag understood by the TTS backend
created: 2026-11-11T12:00:00Z
```

There are deliberately **no** `models`, `tools`, `permissions`, `memory` or `scene` keys.

### 3.2 `scene.yaml` (schema 1)

```yaml
schema: 1
id: apartment
name: Apartment
glb: scene.glb
spawn: { position: [0, 0, 2], yaw: 180 }
bounds: { min: [-4, 0, -4], max: [4, 3, 4] }
colliders: [ { box: [0, 0.5, 0, 1.2, 1.0, 0.6] } ]   # center xyz, size xyz
anchors:
  - { id: sofa, position: [-2, 0, -1], yaw: 90, kind: sit }
waypoints: [ [0, 0, 0], [2, 0, -1] ]
lighting: { hdri: null, ambient: 0.4 }
```

### 3.3 `settings.json` (top-level keys)

`ui`, `models` (last selection, per-model effort), `voice`, `pets`, `scenes`, `advanced`. Secrets are **not** stored here.

### 3.4 Model references

`<kind>:<backend>/<id>`, for example `local:ollama/qwen3.5:9b`, `local:llamacpp/qwen3.5-35b-a3b-q4`, `api:airouter/<catalog-id>`.

### 3.5 Threads database (`threads.db`, SQLite)

```
threads(id TEXT PK, title, created_at, updated_at, active_waifu_id, model_ref, effort, archived)
messages(id INTEGER PK, thread_id, ts, role,            -- user | assistant | divider
         speaker_waifu_id, speaker_name, content, model_ref, effort,
         tokens_in, tokens_out, meta JSON)
attachments(id INTEGER PK, message_id, kind, path, mime, size)
```

Memory lives in a **separate** database (`memory.db`, Yuri's schema v2, sqlite-vec) and is untouched by waifu ids.

## 4. Non-functional requirements

### 4.1 Performance and resources (TARGETS, 12 GB VRAM)

| Item | TARGET | Calibrate |
|---|---|---|
| Idle kernel RAM | under 600 MB | K1 |
| Stage + 9B Q4 + TTS + embeddings resident | fits in 12 GB with at least 1 GB headroom | K2 |
| Local to local model switch (same backend) | spinner within 100 ms, ready in 15 s cold | K1 |
| Pet overlay | under 2% CPU, about zero GPU | K4 |
| Scene | at most 300k triangles, 60 fps with one waifu | K5 |

The VRAM manager reads NVML. Estimates in docs are planning numbers; measured values replace them in `STATE.md`.

### 4.2 Reliability

- Graceful shutdown: tray Quit asks the kernel to finish memory consolidation, then closes children; hard kill after about 5 s.
- All file writes (settings, packs) are atomic (write temp, then rename).
- A crashed child process (TTS backend, llama-server) is reported and restartable from the UI; it never takes the kernel down.

### 4.3 Privacy and security

- Local-first; the only outbound traffic is the user's chosen API calls and model-catalog refresh.
- Tauri CSP locks the webview to the bundled app and the loopback kernel; no remote scripts.
- Keys never in the repo, logs, audit log or crash reports.
- The kernel binds to **127.0.0.1** only.
- Untrusted content (file text, OCR, web) carries `trust=false` on the bus and can never authorise an action by itself (matters for agent mode later).

### 4.4 Accessibility and UX

Reduced-motion setting; keyboard-reachable controls; visible focus; contrast at least WCAG AA for UI text; UI strings centralized (English only in v1).

### 4.5 Observability

Logs in `logs/` (kernel, backends), a per-turn **latency row** (model first token, TTS first audio, total), the router audit log, and the spend ledger.

### 4.6 Portability (packaging-ready from day one)

No absolute paths; all locations from `KASANE/paths.py`; no assumption that a repo checkout or dev tools exist at runtime; config layering (defaults, then `config.yaml`, then env, then `settings.json`).

## 5. Error and empty states

| Situation | Behaviour |
|---|---|
| No waifus | Sidebar shows "＋ New waifu"; chat disabled with a call to action |
| No local models | Local section shows install hint; API section works if a key exists |
| No API key | API section disabled with "Add your AI Router key" |
| TTS backend down | Banner, text-only continues |
| VRM missing | Stage instruction panel (FR-ST-5) |
| Model fails to load (VRAM) | Inline error naming the blocker with *Unload X* / *Pick smaller model* |
| API quota or error | Inline on the turn: *Retry*, *Switch model* (FR-R-5) |
| Mic permission denied | Toast with how to enable it in Windows settings |
| Kernel not reachable | Full-window reconnect screen with log link |

## 6. Out of scope for v1

Agent mode and VR (deferred, see `SCOPE.md` §12); mobile, web hosting, multi-user; fine-tuned GPT-SoVITS weights; Live2D; marketplace or waifu sharing; shell execution; emotion detection (hooks only); per-waifu models, tools or permissions.

## 7. Phase acceptance matrix

| Phase | Requirements delivered |
|---|---|
| T | TTS backend contract (`TTS-BACKEND.md`) |
| K0 | FR-W-1..4, 6; FR-S-5; FR-R-3 (mapped to existing tests); FR-V-1, 7 (adapter); FR-MEM-1..3 |
| K1 | FR-C-1..6, 8..10; FR-S-1, 2; FR-M-1..11; FR-R-1, 2, 4..7; FR-MEM-4, 5; FR-SET-1..3 |
| K2 | FR-C-7; FR-S-3, 4; FR-ST-1..7; FR-V-2..6, 8; FR-C-4 live |
| K3 | FR-W-2 (UI), FR-W-5; FR-CR-1..8 |
| K4 | FR-P-1..6 |
| K5 | FR-3D-1..6 |
| K6 | NFR calibration, evals, crash recovery, docs |
| K7 | FR-DIST-1..6 |

## Appendix A: system-prompt instruction template (canonical)

The app fills `{{name}}` and `{{traits}}` and places the result behind **Copy instruction** (FR-CR-5). Stored as a kernel resource; this text is the source of truth.

````
You are writing a system prompt for a conversational AI companion character. The prompt you write will be given to a language model so it can play this character.

Character name: {{name}}
Personality traits: {{traits}}

Requirements for the system prompt you write:
1. Address the model directly in second person ("You are {{name}}, ...").
2. Describe her personality, tone and speech habits so that every listed trait is clearly visible in how she talks. Do not simply list the traits.
3. Her replies are spoken aloud by a text-to-speech voice. Tell the model to use short, natural spoken sentences and never to use markdown, emoji, asterisk actions, stage directions or lists, and not to read out URLs or code unless the user asks.
4. Tell the model to stay in character at all times and not to mention being a language model, a prompt or these instructions unless the user directly asks.
5. Do not give her special abilities, tools or knowledge limits. Her intelligence and capabilities are those of the underlying model; the prompt only shapes personality and voice.
6. Tell the model to keep replies brief by default (one to three sentences) and to go longer only when the user asks for more detail.
7. Length: 200 to 350 words.
8. Output only the system prompt itself, inside a single code block, with no commentary before or after it.
````
