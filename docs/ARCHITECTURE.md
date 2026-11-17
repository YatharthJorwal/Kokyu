# ARCHITECTURE — Kōkyū

How Kōkyū is built today. Requirements are in `SPEC.md`, the reasons in `DECISIONS.md`. Anything not built yet is marked **Planned**. Checked against the code on 2026-11-17 (commit 7c16e95).

## 1. Overview

One **kernel** (KASANE, Python) holds all logic and state. The **client** (the Tauri window, or a browser tab in development) renders what the kernel sends and sends the user's intents. Model runtimes and the voice server are **backends** the kernel reaches over HTTP. A companion is data the kernel loads; no component has companion-specific code.

```
Tauri window (React, src/app) ⇄ WebSocket, protocol v1 ⇄ KASANE kernel on 127.0.0.1:8780
  session + hub → turns → router → Ollama :11434 | llama-server :8080 | the API endpoint
                        → memory.db, threads.db
                        → audio → GPT-SoVITS :9880
```

**Design principles**

1. **Waifu = data.** A pack is a persona prompt, voice parameters and a VRM (pet sprites later). Nothing else may depend on which companion is active (FR-W-3; `KASANE/tests/test_invariance.py`).
2. **Thin clients.** State lives in the kernel. Clients subscribe to frames and send intents. The Tauri window and a browser tab speak the same protocol.
3. **One door for models.** Every model call goes through the router with a role, and `router/decision.py` `decide()` picks the provider (FR-R-1).
4. **VRAM is the scarce resource.** One chat model in memory, and a check before every local load (D-065, D-072).
5. **Packaging-ready.** Every path comes from `KASANE/paths.py`; no dev-only assumptions in the kernel at runtime (RULES §9). The shell still has dev-only paths (§12).

## 2. Processes and lifecycle

| Process | Started by | When | Port and notes |
|---|---|---|---|
| Tauri shell (`src-tauri/src/lib.rs`) | the user | launch | One window (`main`) and a tray with Show/Hide and Quit. Closing the window hides it. |
| Kernel (`KASANE/app.py` on `.venv` Python) | the shell, on its own thread | launch, after a stale-kernel sweep | `127.0.0.1:8780` (D-027). Hidden window, log `logs/kernel.log`. |
| Ollama | the user (external service) | already running | `11434`. The kernel only talks HTTP to it. |
| `llama-server` | the kernel (`router/providers/llamacpp.py`) | only when the user picks a llama.cpp model or messages a thread that uses one (D-060) | `8080` (`llamacpp.port`). One at a time, for the picked preset; the binary is configured, else the one inside Ollama. Log `logs/llama-server.log`. |
| GPT-SoVITS (`api_v2.py`) | the kernel (`audio/tts.py` `ensure_server`) | when the user turns voice mode on (D-061); stopped `tts.idle_stop_s` (300 s) after it goes off | `9880`, from `tts.gpt_sovits.api_url`; folder in `tts.gpt_sovits.launch`. A server already answering on the port is used, never a second. Log `logs/gpt_sovits.log`. |
| Vite | `npm run tauri dev` (`dev:ui`) or `npm run dev` | development only | `1420`, `strictPort`. |

**Job Object.** Before any child starts, the shell puts itself in a kill-on-close Job Object. Every child (kernel, `llama-server`, GPT-SoVITS) ends with the app, however it ends.

**Startup (D-060).** The shell sweeps a stale `python.exe` holding 8780, then starts the kernel with the saved API key in `KOKYU_API_KEYS` and a stdin pipe for later key changes (D-059). The kernel also takes over a stale kernel through `logs/kernel.pid`. It lays `settings.json` over `config.yaml` (D-070), opens its port at once and reads the router's cached catalog. After the first window connects, one at a time: the chat model (Ollama or API; a llama.cpp model waits to be picked), the screen companions set to start with the app, the memory catch-up pass. Voice is not part of boot (D-061). Code: `KASANE/boot.py`.

**Shutdown.** Tray Quit sends `POST /shutdown`. Every window's session closes and runs its memory pass (`/shutdown` waits for windows still closing, D-062). The kernel then stops the memory writer with a final pass, voice mode, GPT-SoVITS, the model loader and `llama-server`. The shell kills the kernel if it has not exited after 5 s. There is no HTTP health endpoint: the Doctor runs over the socket (`doctor` → `doctor_report`, `KASANE/doctor.py`, D-067).

## 3. Kernel modules

The `KASANE/` folder is on `sys.path` and modules import each other by top-level name (`import llm`, `from audio import tts`). There is no `kasane` package (D-024). There is no `models/` package either: model lifecycle lives in `vram.py`, `model_loader.py`, `boot.py`, `router/capabilities.py` and `router/providers/llamacpp.py`.

| Module | Responsibility |
|---|---|
| `app.py` | The FastAPI server: `/ws` (origin-checked), `GET /waifus/{id}/vrm`, `POST /shutdown`; the lifespan starts boot and the memory writer and stops every child. |
| `session.py` | One `Session` per window; one `on_<type>` handler per client message type (a test checks every type has one). |
| `hub.py` | Open windows, which one drives turns (the first; others observe), broadcasts, the shutdown event. |
| `turns.py` | One model turn: memory reads, the ephemeral note, the router stream, tool calls, speech, saving. |
| `boot.py` | Start-up order (D-060), loading a chat model with the VRAM check and the unloads (D-072), stale-kernel takeover. |
| `model_loader.py` | One background loader for the chat model; newest request wins; `model_status` to every window (D-054). Voice mode reuses it. |
| `companions.py` | The window's active companion: persona text and voice parameters, nothing more. |
| `conversation.py` | Threads for a window: history from stored messages, the thread's prompt layers, recording each exchange. |
| `prompting.py` | The system prompt layers and the per-turn note texts (D-074). |
| `story.py` | Story memory for roleplay threads (FR-MODE-5, D-075). |
| `persona.py` | Text rules shared by every companion: the emotion tag and speech safety nets. |
| `ambient.py` | The screen companions: Task Guide and OCR watch (FR-SC-1..5). |
| `vram.py` | GPU memory through NVML or `nvidia-smi`, measured model sizes, fits hints and the load check (D-065). |
| `doctor.py` | The Doctor's read-only checks, one row per component (D-067). |
| `settings_file.py` | `settings.json` over `config.yaml`, applied live (D-070). |
| `config.py`, `check.py` | The config loader (code defaults, YAML, the settings overlay, API key lookup); `check.py` checks config, key, catalog and spend from the command line. |
| `paths.py` | Every filesystem location (dev `./data`, packaged `%APPDATA%\Kokyu`, `KOKYU_DATA_DIR` for tests). |
| `llm.py`, `context_budget.py` | The Ollama client (native and OpenAI-compatible wire formats, capability reports, load and unload); keeping every call inside the model's context window. |
| `provider_presets.py`, `shell_keys.py` | The named API endpoints: AI Router, OpenRouter, DeepSeek (D-037); API keys handed over by the shell (D-059). |
| `bus.py` | An in-process typed event bus with a `trust` field. No kernel module uses it yet; only its tests. |
| `router/` | The only way to a model: `decision.py` (pure rules), providers (`ollama_native`, `llamacpp`, `airouter`), `capabilities.py` (effort), `discovery.py` (API catalog), `listing.py` (picker rows, load check), `budget.py`, `audit.py`, `redact.py`, `model_ref.py`. |
| `memory/` | `memory.db`: facts, episodes, events, the profile card, `transcript_log`; the writer pass, recall, forget, decay, contradiction, embeddings, the Settings viewer, migrations, a CLI (`python -m memory`). |
| `threads/` | `threads.db`, the store behind the sidebar. |
| `audio/` | Speech out: `chunking`, `speech` (speech-safe text, `DialogueFilter`), `speech_stream`, `tts`, `voice_mode`, `arbiter`, `latency`. Speech in: `vad`, `stt`, `voice` (built and tested, not wired to the protocol). |
| `senses/` | `camera`, `look_intent` (deterministic "look at X"), `ocr_watch`, `task_guide`. |
| `tools/` | The tools a chat turn may offer: `capture_screen`, `read_clipboard`, `set_active_task`, `capture_camera`. |
| `waifus/` | Pack parsing and validation (`pack.py`), the registry of premade and user packs. |
| `protocol/` | The v1 envelope, client message models, the server type list, error codes. |

Also: `tests/` and `conftest.py` (§13); `voice_files/`, the clips `scripts/build_premade.py` reads (`.wav` gitignored); `vrm/`, two leftover VRM files (gitignored) whose deletion is the user's action (C-1b).

**Planned kernel pieces:** `router/names.py` (short model names, D-084); first-run setup modules (D-080, §8); voice input wiring (an `audio_frame` message and a handler that runs STT off the receive loop, RULES invariant 7); the 3D apartment's kernel side (K5, D-078).

## 4. One turn

```
client send {text}
 → Session.on_send → turns.run_turn(history, mode, story, model_ref, effort)
 → wait for a pending model load; memory reads; build the ephemeral note      → turn_start
 → router.stream_with_tools("chat", …) → Router.route() → decision.decide() → provider stream
 → tokens (tool calls run and loop back)                                       → token, token, …
 → clauses → speech → tts.synthesize                                           → speak per clause
 → save the exchange in threads.db; transcript_log (chat only)                 → turn_done
```

Only the driving window starts turns; an observer that sends gets `error {code: "observer"}`.

### 4.1 Prompt assembly

```
system    = persona          the companion's prompt: who she is, no format or length rules
          + mode layer       CHAT_LAYER or ROLEPLAY_LAYER, from the thread
          [+ scenario card]  roleplay only: the card's filled-in fields, the opening line last
          + APP_ADDENDUM     every mode: the emotion tag, honesty about abilities
          [+ TOOL_GUIDANCE]  chat only
history   = earlier user and assistant lines (no dividers, screen remarks or roleplay opening)
ephemeral = forget, task and look hints (chat only)
          + recall (chat: facts and episodes; roleplay: the profile card alone)
          [+ the story so far]  roleplay only
          [+ delivery layer]    while voice mode is on
user      = the new line (with an attachment's text or image description)
```

- The system message is `prompting.build_system_prompt()`, reached through `companions.system_message()`. Only the persona differs between companions; the mode and the scenario come from the thread. It stays the same for the life of a thread, so `llama-server`'s cached prefix holds (D-074).
- The ephemeral note is one system message spliced before the last user message and never stored. The llama.cpp provider moves it into that user message, for the same cache (D-051). Temp Chat reads nothing: no recall, no profile card, no story.
- The reply ends with an emotion tag (`[happy]` … `[neutral]`). It is cut from history, the saved message and `turn_done.text`, and is never spoken.

### 4.2 What differs in a roleplay (details: D-074, D-075)

- **Fiction stays in the thread.** No forget, no Task Guide, no look intent, no tools offered, and the exchange is not written to `transcript_log`, so nothing from a story reaches `memory.db` (FR-MODE-4). The router role is `chat` in both modes.
- **Only her dialogue is spoken.** `speech.DialogueFilter` cuts actions, asides and narration from the speech side; history keeps the whole reply (FR-MODE-8). The screen companions stay quiet while a roleplay thread is open (FR-MODE-9).
- **Story memory.** `story.KEEPER` folds older lines into one running summary per thread (`story_memory` in `threads.db`) with the local `memory_writer` role, in the background, only while the arbiter is idle and no model is loading. The summary joins the ephemeral note (FR-MODE-5).

## 5. Protocol

### 5.1 Envelope

One WebSocket at `ws://127.0.0.1:8780/ws`. Every frame, both ways:

```
{ "v": 1, "type": "...", "id": "...", "thread": "<thread id>" | null, "data": { ... } }
```

The kernel validates client frames with pydantic models (`KASANE/protocol/__init__.py`). A bad frame, an unknown type or a flat message gets `error {code: "bad_message"}`; another version gets `protocol_version`. The TypeScript mirror is `src/net/protocol.ts`. `KASANE/tests/test_protocol.py` checks that the two type lists are equal and that every client type has a `Session.on_<type>` handler.

### 5.2 Errors

`error {code, message, reply_to}` with the codes `bad_message`, `protocol_version`, `unknown_thread`, `unknown_waifu`, `turn_running`, `threads_unavailable`, `model_blocked`, `model_failed`, `vision_unavailable`, `observer`. A failed chat model (FR-R-5) adds `reason`, `model_ref`, `detail` and `actions: ["retry", "switch_model"]`.

### 5.3 Message types (C→K: client to kernel; K→C: kernel to client)

| Type | Dir | Purpose |
|---|---|---|
| `hello` | both | Client kind (`main`, `pet`, `dev`) and version; the answer adds the default model ref and effort |
| `send` | C→K | A typed line starts a turn (FR-C-1) |
| `send_file` | C→K | An image or text file, with a caption, starts a turn (FR-C-4) |
| `stop` | C→K | Stop the reply in flight (FR-C-2) |
| `regenerate` | C→K | Run the last exchange again: Regenerate and Retry (FR-C-9) |
| `turn_start`, `token`, `turn_done` | K→C | A reply: start, streamed text, final text and whether it was stopped (FR-C-2) |
| `speak` | K→C | One spoken clause: caption text and a WAV; empty audio when voice is off or down (FR-V-7) |
| `thread_list`, `thread_search` | both | The sidebar history, or threads matching a query; answered with `thread_list` |
| `thread_new` | C→K | A new thread: `mode` chat or roleplay, fixed for its life, and a roleplay's scenario card (FR-MODE-1, 6) |
| `thread_open`, `thread_delete`, `thread_rename` | C→K | Change, delete or rename a thread; refused with `turn_running` during a reply |
| `thread_opened` | K→C | The open thread and its messages, on connect and after every open, new or delete |
| `thread_updated` | K→C | The open thread's row after a change of model, effort or Temp Chat |
| `thread_message` | K→C | One stored line added outside a turn: a companion-change divider (FR-S-2), a screen remark |
| `set_model`, `set_effort`, `set_temp` | C→K | The thread's model ref and effort (FR-M-5, FR-M-8); Temp Chat on or off (FR-MEM-5) |
| `model_list` | both | The picker's rows, local and API, with the spend footer; `refresh` re-fetches the catalog (FR-M-3, 4, 7) |
| `model_load`, `model_unload` | C→K | Try again after a failed load; *Unload X* on the graphics-memory card, then try again (D-071) |
| `model_status` | K→C | The chat model's load state: idle, loading, ready, failed (FR-M-6, D-054) |
| `switch_waifu`, `waifu_state` | both | Change the active companion, persona and voice only (FR-S-1); the roster, the active one, a switch waiting for the running turn |
| `surface_status` | K→C | Whether this window drives turns or observes |
| `voice_mode`, `voice_status` | both | Voice on or off, started only when turned on (D-061); its state and how its start is going |
| `screen_companion`, `screen_companions` | both | Task Guide or OCR watch on or off (FR-SC-1..4); what is watching the screen |
| `typing` | C→K | The user is typing; OCR watch keeps quiet (FR-SC-5) |
| `camera_request`, `camera_frame` | both | The kernel asks for one webcam frame and the window answers; the window side is not wired yet (K2-08) |
| `doctor`, `doctor_report` | both | Run the Doctor's checks; one row per component with a fix hint (FR-SET-3) |
| `memory_list`, `memory_facts` | both | The remembered facts, live then forgotten (FR-MEM-4) |
| `memory_edit`, `memory_forget`, `memory_restore` | C→K | Correct a fact (the old one is superseded), forget it, bring it back; answered with `memory_facts` |
| `settings_get`, `settings_set`, `settings` | both | The editable settings; a change is saved to `settings.json` and applied at once (FR-SET-2, D-070) |
| `scenario_list`, `scenario_save`, `scenario_delete`, `scenarios` | both | Saved scenario cards, app-level, never tied to a companion (FR-MODE-6); every answer is the full list, newest first, and a save's answer names the saved card |

HTTP beside the socket: `GET /waifus/{id}/vrm` (a registered companion's avatar; loopback page origins, GET only) and `POST /shutdown` (the shell's Quit).

**Planned** with the features that need them: voice input frames (K2), pets (K4), the apartment (K5), the creator (K3).

## 6. Data and storage

All paths come from `paths.py`. Development: `./data`, `./logs` and `./config` in the checkout. Packaged: `%APPDATA%\Kokyu` (FR-DIST-4).

```
data/
  settings.json         what Settings changed (D-070)
  threads.db            threads, messages, attachments, story_memory, scenarios, kv (schema 5)
  memory.db             facts, episodes, events, profile card, transcript_log, sqlite-vec tables
  spend.db              the API spend ledger
  vram_measured.json    what each model really took (D-065)
  active_waifu.txt      the companion used last
  <endpoint>_models.json  cached API catalogs
  waifus/<id>/          user-made companions (the creator is K3)
logs/                   kernel.log, llama-server.log, gpt_sovits.log, audit.jsonl, latency.jsonl
assets/premade/<id>/    Luna and Yuri: waifu.yaml, prompt.md, model.vrm, voice/ref.wav (read-only, untracked, D-041)
```

- **`memory.db`** is shared by every companion, not namespaced (D-005); writes name the speaker. The writer pass reads `transcript_log` on a timer, at session end and at shutdown, and never runs during a reply.
- **`threads.db`** holds each thread's `mode` and `scenario`, the roleplay `story_memory` (deleted with its thread) and the saved `scenarios`. It never touches `memory.db`.
- **Temp Chat** is a flag on the thread. The thread is kept in `threads.db`, but its turns read no memory and its `transcript_log` rows are flagged, so the writer skips them.
- **Fiction never reaches `memory.db`:** roleplay exchanges are not written to `transcript_log` (§4.2).
- **Config** layers: code defaults, then `config/config.yaml` (else `config.example.yaml`), then `settings.json`. Secrets are never in YAML: the shell's key first; in a developer checkout only, the environment, `secrets.local.yaml` and `.env`.

## 7. Models

### 7.1 Roles

A role is a capability slot in `config.yaml` `roles`. A `local_only` role whose chain names a cloud provider is a startup error.

| Role | Used for | Where it may run |
|---|---|---|
| `chat` | Every conversation turn, on the thread's `model_ref`. The selection is the consent (D-025); a refused or failed API model is shown with Retry and Switch model, never swapped (FR-R-5). | local or API |
| `reflex` | Screen companion remarks; also the default local model name for a role with no entry of its own | local |
| `classifier` | Task Guide's task check | local |
| `memory_writer` | The memory writer pass and story folds | local |
| `vision` | Camera, screen checks, image uploads | local |
| `embed` | Recall embeddings (`nomic-embed-text`) | local |
| `mind` | Cloud-eligible; nothing calls it | local or API |

### 7.2 Providers and effort

- Model refs are `local:ollama/<tag>`, `local:llamacpp/<preset>` and `api:<endpoint>/<model>`.
- **Providers:** `ollama_native`, `llamacpp` (presets in `config.yaml` `llamacpp.presets`, D-051, D-054) and `airouter`. `airouter` is the one API slot, an OpenAI-compatible SSE client; it runs whichever named endpoint is active (`provider_presets.py`, D-059).
- **Effort is data** (D-064): `config/models.yaml` (the user's, optional), then the shipped `config/models.example.yaml`, map effort levels to a local model's `think` value. API models get low, medium and high when the catalog marks them as reasoning.

### 7.3 One model in memory and the VRAM check

- **One chat model in memory** (D-072). Picking an Ollama model stops `llama-server` and unloads every other Ollama model except the embedding model. Picking a llama.cpp model unloads Ollama's models except the embedding model. Picking an API model frees both. With an Ollama model picked, `classifier`, `memory_writer` and `vision` run on it (`router/decision.py` `FOLLOW_PICKED`); otherwise they load for their call.
- **VRAM check before a load** (D-065). `vram.py` reads the GPU through NVML (the driver's `nvml.dll`), else `nvidia-smi`, else "unknown". It remembers what each model really took. `router/listing.py` `load_check` refuses a local model that would not fit beside the embedding model once the other chat model is gone, and names what holds the memory. An unknown answer never refuses.
- **Measured on the dev PC:** Qwen3.6-35B-A3B Q4 on llama.cpp with every expert in RAM takes about 3 GB VRAM and 19.5 GB RAM (`docs/STATE.md`). GPT-SoVITS and the renderer are not measured yet.

### 7.4 Model names (Planned, D-084, FR-M-12)

Today `router/listing.py` `label_for` gives a preset's label or the raw model id, and the client shortens refs again (`src/app/models.ts` `shortRef`). **Planned:** `router/names.py` computes one short name per model in the kernel. Rows carry `label`, `full` and `facts`, shown muted on hover or focus. Precedence: a `names:` override in `models.yaml`, then a llama.cpp preset label, then a deterministic derivation. `shortRef` then goes away.

## 8. Voice

```
model stream ─> token frames (the chat shows the raw text)
             └> [roleplay: DialogueFilter] → chunker (clauses; holds back a trailing [tag])
                → persona pass → speech.prepare (speech-safe text) → SpeechStream (one clause ahead)
                → tts.synthesize → speak {text, audio_b64, mime} → src/app/voice.ts plays in order
```

- **Voice mode** (D-061) is kernel-wide and starts off. Turning it on starts GPT-SoVITS (or uses one already answering) and loads faster-whisper on the CPU; every window sees the start like a model load. While it is off, `speak` frames carry empty audio.
- **GPT-SoVITS contract.** `audio/tts.py` sends `POST {tts.gpt_sovits.api_url}` (default `http://127.0.0.1:9880/tts`) with a JSON body of five fields: `text`, `text_lang`, `ref_audio_path`, `prompt_text`, `prompt_lang`. It expects whole WAV bytes per clause. The reference clip and its transcript come from the speaking companion's pack on every request, so a switch changes parameters only (D-006). Any other answer counts as down. RULES R-12: depend only on this contract.
- **Backend down.** The reply stays text-only and the caption still shows (FR-V-7). `tts.fallback_engine` is `none` by default; `pyttsx3` is opt-in.
- **Cold start.** GPT-SoVITS took 47 s to answer after voice mode was turned on (dev PC, `docs/STATE.md`). A line spoken meanwhile waits up to 8 s, then goes caption-only. Audible playback in Kōkyū is not verified yet.
- **Arbiter** (`audio/arbiter.py`): idle, listening, thinking, speaking, interrupting. The memory writer's timer pass and story folds wait for idle.
- **Lip-sync** belongs to the client and comes with the Stage view (K2); `src/engine/lipsync.ts` exists but nothing uses it yet.
- **Planned: automatic first-run setup** (D-080). On a fresh install, the first run sets up what voice needs, with progress and no terminal: GPT-SoVITS and the speech-to-text model. One small setup module per component the app installs itself, each with a pinned manifest (URLs, SHA-256, sizes, versions). Ollama goes through its official installer. Everything else is detected and repaired through the Doctor's checks with fix actions (open the installer, start, retry). No generic component framework. Development keeps the existing GPT-SoVITS install (D-042).

## 9. Client

- **`src/app/`**: the React window (D-053). `store.ts` is a Zustand store (D-013) around the pure reducer in `chat-state.ts`; components read with `useChat(selector)` and act through `actions.*`. `ui/` holds 15 components (Sidebar, TopBar, ThreadView, Composer, ModelChip, EffortSlider, SettingsDialog, RoleplayDialog, …). `theme.ts` holds the themes, kept in the window's localStorage (D-073). `markdown.ts` is an in-house parser that returns a tree, so model output never reaches the page as HTML (D-055). `voice.ts` plays `speak` clips. Other pure helpers: `models.ts`, `history.ts`, `scenario.ts`, `file-upload.ts`, `effort-slider.ts`.
- **`src/net/`**: `kernel.ts` (one WebSocket with reconnect backoff; no state) and `protocol.ts` (the typed mirror of §5).
- **`src/engine/`**: pure-logic avatar parts from Yuri waiting for the K2 Stage (idle motion, eyes, expression life, lip-sync, framing, a VRM report), plus mic and camera capture. The VRM loader and the stage itself are not in the repo yet.
- **Rule:** clients hold no business logic. The window renders kernel state and sends intents; decisions about models, memory and speech are the kernel's.
- **Open:** a written design standard (type scale, spacing, motion, empty, loading and error states). `DESIGN.md` is planned at the start of UI-1.

## 10. Security and trust

- The kernel binds loopback. `/ws` refuses a browser origin other than Kōkyū's own pages; there is no token check yet (D-057, open). `src-tauri/tauri.conf.json` sets a CSP: `self` plus the kernel on loopback.
- End-user API keys live in the Windows Credential Manager. The shell passes them to the kernel in the environment at spawn (removed at import) and later on stdin, never on the WebSocket or the command line (FR-R-6, D-059).
- Screen and camera content is ambient and never goes to an API model (FR-R-7, FR-SC-3). Redaction (`router/redact.py`) applies before any cloud call and in the audit log.

## 11. Planned features

- **Stage view (K2).** The avatar in the main window: VRM loading, framing, idle motion, lip-sync from the played audio, look-at. Voice input (VAD and STT exist in `audio/`) gets wired here.
- **Desktop pets (release 1.1, K4).** 2D sprites baked from the VRM, in a transparent overlay window per monitor. Click-through and alpha hit-testing start from zero; Yuri's hooks were removed with the widget (D-062).
- **3D apartment (release 1.1, K5, D-078),** built from Luna's apartment (`github.com/YatharthJorwal/Luna`: `src/apartment/`, `src/camera-modes.ts`, `src/sandbox.ts`). A prebuilt GLB apartment supplied as a user asset, with BVH collision (`three-mesh-bvh`, already a dependency); a spectator free-fly camera and a first-person visitor camera (WASD, pointer lock) clamped to her walkable area; her wandering with walk start, loop and stop clips; time-of-day lighting plus a light that follows her. Open, to design later: real room and anchor data, the rights to a shipped room asset, VRAM beside the LLM and TTS, and two-companion scenes (who speaks next, both reacting to what the user says).
- **Not planned:** an agent mode for file reading and writing; VR is deferred long term (D-079).

## 12. Packaging questions (K1b)

1. **Kernel packaging.** A PyInstaller one-folder build shipped as app resources, or an embedded CPython with prebuilt site-packages. The user installs neither Python nor Node. Choose by installer size, antivirus behaviour (unsigned PyInstaller executables are a known false-positive trigger) and updates. Tauri's `externalBin` expects one executable, so a one-folder build needs resource bundling.
2. **Installer.** One per-user NSIS `.exe`: no admin rights, with the WebView2 bootstrapper (D-081). The bundle target is already `nsis`; the per-user install mode is to be set and checked. No MSIX, portable zip or `setup.ps1`.
3. **Updater.** The Tauri updater with its own signing key, separate from the code-signing certificate; a static update manifest.
4. **Code signing.** Research certificate options; sign the installer and the kernel executable. Expect SmartScreen friction for a new publisher.
5. **License key.** A public key compiled into the app verifies a signed key offline (FR-DIST-10).
6. **Diagnostics.** An export zip with redacted logs, versions and component states (FR-DIST-8).
7. **Shell paths are dev-only.** `spawn_kernel` in `src-tauri/src/lib.rs` uses `../.venv/Scripts/python.exe`, `../KASANE` and `../logs`, relative to `src-tauri/`.
8. **The kernel port is hard-coded** in three places: `KASANE/app.py` (`PORT = 8780`), `src/net/kernel.ts` (`KERNEL_WS_URL`) and `src-tauri/src/lib.rs` (`KERNEL_ADDR`, `KERNEL_PORT`, and the `Host` header of the shutdown request). It also appears in the CSP in `src-tauri/tauri.conf.json`, the kernel's allowed origins (for 1420), and `scripts/dev.mjs` and `scripts/doctor-lib.mjs`.

## 13. Testing

| Layer | Tool | Notes |
|---|---|---|
| Kernel | pytest (`KASANE/tests/`) | Fakes for models, TTS and STT; real SQLite on throwaway files. Autouse fixtures in `KASANE/conftest.py` and `KASANE/tests/conftest.py`: `KOKYU_DATA_DIR` in a temp folder, no real model loads, no GPU, no saved keys, voice off, no picked model, no real Ollama unload, a story keeper that never runs. |
| Invariance | `test_invariance.py` | FR-W-3: fixture packs (`waifu_fixtures.make_pack`); everything but the persona and voice must match, in chat and in roleplay threads. |
| Protocol | `test_protocol.py`, `tests-fe/protocol.test.mjs` | Python and TypeScript are tested separately; the Python test compares the two type lists and checks a handler per client type. There are no shared JSON fixtures. |
| Frontend | `npm run test:fe` | esbuild bundles `tests-fe/*.test.mjs`, Node's test runner runs them. Pure logic only: no DOM, WebGL or audio. |
| Type and build | `tsc --noEmit`, `vite build`, `cargo check` | `npm run check` runs all of these plus both test suites. |
| By hand | the phase checkpoint (D-076) | Run in the desktop app with a real model; anything needing a GPU, mic or display. |

No automated test may need a GPU, network, API key or display.
