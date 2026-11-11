# Yuri and Luna inventory (K0-02)

Findings from reading the code that Kōkyū will be seeded from. Written 2026-11-11 (session 1) before any porting, so the specs can be corrected against reality.

- **Yuri** `github.com/YatharthJorwal/Yuri` at `e32af4f710cdf4e8c141df667a18c53046557ea3` ("npm run dev starts the backend too; status indicator is a heart"), `main` HEAD on 2026-11-11.
- **Luna** `github.com/YatharthJorwal/Luna` at `2015462` ("Phase 13 step 3 …").
- **How it was read:** full clone; read Yuri's `HANDOFF.md`, `docs/DECISIONS.md` headings, `config.example.yaml`, and the source of `app.py` (turn runner), `bus.py`, `router/*`, `audio/tts.py`, `persona.py`, `settings.py`, `src-tauri/src/lib.rs` (function map), `tauri.conf.json`, `package.json`, `index.html` ids. **Not read in full:** `docs/ROUTING.md`, `docs/PHASES.md`, `docs/phases/*`, `memory/*` bodies, `senses/*` bodies, most of `src/*.ts`, Luna's code beyond a function map of `sandbox.ts`. Items below say when something is inferred.

## 1. Verified baseline (Linux sandbox, not the user's PC)

| Check | Result |
|---|---|
| `pytest orchestrator -q` | **641 passed** (about 4 s) |
| `npm run test:fe` | **65 passed** |
| `npx tsc --noEmit` | clean |
| `npm run build` (tsc + vite) | succeeded (chunk-size warning only) |
| `cargo check` | **not run** (no Tauri system libraries / Windows here) |
| Anything needing GPU, mic, speakers, display, Ollama, GPT-SoVITS | **not run** |

This matches Yuri's own handoff (641 pytest, 65 frontend).

## 2. Shape

- Python backend in `orchestrator/` (about 90 files; `app.py` 1645 lines, `config.py` 834, `llm.py` 727, `router/__init__.py` 508, `audio/tts.py` 278).
- **Flat imports.** `orchestrator/` is put on `sys.path` (`orchestrator/conftest.py` for tests, the launcher at runtime) and modules import each other as top-level names: `import llm`, `from audio import tts`, `from router import ...`, `from memory import store`. There is **no importable package** and no `import orchestrator`. Consequence: the kernel folder can be named `KASANE/` in any case without touching imports (D-024).
- Frontend: vanilla TypeScript, no framework, Vite 5, `three` ^0.185.1, `@pixiv/three-vrm` and `three-vrm-animation` ^3.5.5, `three-mesh-bvh`. 11 source files, about 3.9k lines including 849 of CSS; `main.ts` 1285 lines, `ws-client.ts` 430.
- Rust shell `src-tauri/src/lib.rs` (780 lines), Tauri 2, `win32job`, global-shortcut plugin.
- Frontend tests: `tests-fe/*.test.mjs`, run by `scripts/test-frontend.mjs` (esbuild bundles each test; Node's built-in test runner executes it; **pure logic only**, no DOM/WebGL). There is no `npm run check`; K0 creates it.
- Dev commands (`package.json`): `npm run dev` (starts the backend and the page for a browser tab), `npm run dev:ui` (page only; what `tauri dev` runs), `npm run tauri dev`, `npm run doctor`, `npm run build`, `npm run test:fe`, `npm run clean[:all]`.

## 3. Module map

| Yuri | What it does | Kōkyū fate |
|---|---|---|
| `app.py` | FastAPI app; `ws_endpoint` (~580 lines) owns a per-connection `history` list; `_run_turn` runs a turn | Split in K1 into a conversation manager plus thin WS layer |
| `config.py`, `config/config.example.yaml` | Config v2 (dataclasses; providers, models, roles, routing, privacy, budget, audit, llm, voice, tts, speech) | Config v3 (K0-06) |
| `bus.py` | In-process typed event bus: `Event(type, source, payload, trust, session, id, ts)`; `subscribe(pattern, handler)`; bounded replay (500); handlers awaited in subscription order | Keep as is |
| `router/` | `decide()` (10 ordered rules), `Router.complete/stream_text/stream_with_tools/describe_image`, providers `ollama_native` and `airouter`, catalog discovery, budget ledger, audit JSONL, redaction | Extend in K1 (D-025) |
| `llm.py` | Ollama and OpenAI-style streaming, tool calls, vision, warm-up, capability report | K1: take `model` and effort parameters |
| `persona.py` | `SYSTEM_PROMPT` constant, `apply_persona_pass()` regex cleanup, emotion tag helpers | K0-08: prompt becomes waifu data |
| `audio/` | `tts.py`, `speech.py` (speech-safe), `speech_stream.py` (clause pipeline), `chunking.py`, `arbiter.py`, `vad.py`, `stt.py`, `voice.py`, `latency.py` | Keep; `tts.py` per-waifu params (K0-11) |
| `memory/` | SQLite + sqlite-vec: facts, episodes, transcript log; writer, recall, decay, supersede/forget (never delete), profile card, CLI (`python -m memory`) | Keep; add speaker (K0-12) |
| `senses/`, `tools/vision.py` | camera, look-intent, OCR watch, task guide; `capture_screen`, `capture_camera`, `read_clipboard`, task tools | See §10 and D-029 |
| `settings.py` | `data/settings.json`, one key: `use_api_model` | Replaced by the model switcher (K1) |
| `check.py` | Config, key, catalog, spend health | Keep |
| `src/main.ts` etc. | Stage-first UI, lip-sync, eyes, idle motion, expression life, camera, upload, mic stream, VRM report | Engine reused; UI chrome rebuilt in K1/K2 |
| `src-tauri/` | Window, tray, F9 push-to-talk, Job Object, process spawn, graceful shutdown | Keep, retarget |

## 4. WebSocket protocol as it actually is

Endpoint `ws://127.0.0.1:8765/ws`. **Untyped JSON dicts** (no schema models). Names found by grep; payload shapes **not verified** except `speak`.

| Direction | Types |
|---|---|
| Client → server | `user_text`, `user_file`, `user_audio`, `audio_frame`, `audio_end`, `stop`, `set_temp_mode`, `set_ocr_watch`, `set_api_model`, `get_log`, `clear_log`, `camera_frame`, `scene_state` |
| Server → client | `speak`, `turn_end`, `transcript`, `speech_state`, `surface_status`, `settings`, `log`, `barge_in`, `request_camera_frame` |

- `speak` = `{type, text, audio_b64, mime: "audio/wav"}`, **one per clause**, already synthesized.
- **There are no token events.** The UI receives clauses as audio plus caption text and a final `turn_end`. Token streaming (FR-C-2) is new work.
- There is **no thread, no waifu and no model concept** in the protocol.
- Also an HTTP `POST /shutdown` used by the Rust shell for graceful shutdown.
- The bus (`bus.py`) is in-process only; it is not the WebSocket protocol.

## 5. How a turn runs (`_run_turn`)

1. Append the user text to the connection's `history` (index 0 is the system persona, **inferred** from the `history[1:]` comments); track a per-turn `temp` flag.
2. Latency row begins; arbiter notified; memory writer pre-empted; task-guide idle clock reset.
3. Unless Temp Chat: `forget.maybe_forget`, `task_guide.maybe_update_task`, `recall.build_recall_context`.
4. `look_intent.maybe_look` (explicit "look at my screen/camera" handled in Python).
5. One **ephemeral system message** (forget/task/look/memory hints plus scene context) is spliced just before the last user message; it is never stored in `history`.
6. `router.stream_with_tools("reflex", …)` for up to `MAX_TOOL_ROUNDS` rounds; text streams into a `SpeechStream` that synthesizes clause by clause; emotion tag `[word]` at the end of the reply is extracted.
7. On finish or stop: transcript row written (`memory/store.add_transcript_turn(user, assistant, temp=)`), history committed or rolled back, `turn_end` sent.

## 6. Router

- Roles: `reflex`, `vision`, `classifier`, `embed`, `memory_writer` (all `local_only: true`, validated at config load) and `mind` (chain `[airouter, local_ollama]`).
- `decide()` is pure; ten ordered rules with reason codes (role pinned local, secret privacy, **untrusted context blocks cloud**, cloud disabled, offline, budget, explicit escalation, background, complexity, default local).
- `routing.mode: shadow` (decide and log, do not enforce) with `enforce_roles: [mind]`. The API-model toggle only affects `mind`, and **nothing calls `mind` yet** (Phase 4 in Yuri).
- Providers: `local_ollama` (native API) and `airouter` (OpenAI-style SSE, Bearer key from `AIROUTER_API_KEY`, catalog at `https://api.airouter.in/v1/models`, cached 24 h).
- **Gap:** `OllamaNativeProvider.complete(request, *, model)` **ignores `model`** and uses the global `llm.CONFIG.llm.model`. Yuri's own handoff lists the same issue for `memory_writer`. Per-thread local model choice (FR-M) needs `llm.py` to accept a model and an effort/think setting.
- Tests stub `llm.<fn>` by module attribute and the router calls through the module; do not change that pattern.

## 7. Persona and emotion

- The persona is **code**: `persona.SYSTEM_PROMPT` (a long first-person companion prompt). `apply_persona_pass()` is a regex safety net (strips dashes, rewrites "you're").
- Emotion tags: replies end with `[happy|angry|sad|teasing|surprised|neutral]`, extracted by `extract_emotion_tag`. The convention is part of Yuri's prompt/pipeline, so in Kōkyū it belongs in the **shared app addendum**, not in each waifu's prompt (the creator's instruction template tells the LLM nothing about it).
- Luna and Yuri each have their own persona prompt in their repos; the seed script (K0-08) reads them from paths the user supplies.

## 8. Voice and TTS

- **Contract confirmed in use:** `POST http://127.0.0.1:9880/tts` with `{text, text_lang, ref_audio_path, prompt_text, prompt_lang}` returns raw WAV. Yuri launches `api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml` from a GPT-SoVITS v3lora install. Yuri already runs it **zero-shot** from one 8.52 s mono reference clip. (Confirmed from Yuri's code and config, not by running it.)
- `tts.synthesize(text)` takes **no voice argument**; the reference clip and transcript come from global config. Per-waifu voice (FR-V-1) is a signature change.
- `synthesize` **falls back to pyttsx3 automatically** when the server is unreachable. SPEC FR-V-7 requires the opposite default (text-only with a banner; pyttsx3 opt-in).
- Pipelined TTS (`speech_stream.py`): one request per clause, one clause of lookahead. Speech-safe normalization at one chokepoint (`_send_speak` / `speech.prepare`).
- Boot: the Rust shell starts GPT-SoVITS and the orchestrator **in parallel** and sets `YURI_SHELL_STARTS_TTS=1` so Python never launches TTS itself. Run by hand without that variable, `tts.ensure_server()` launches it.
- STT: faster-whisper `small` on CPU, int8; VAD energy-based with adaptive floor (config mentions Silero as an engine name); barge-in cancels the turn. Yuri's gate for real-mic measurements was **not done**.

## 9. Memory

- Facts and episodes with vectors (sqlite-vec, 768-dim `nomic-embed-text`), supersede/forget never delete (`--restore ID`), decay, profile card, relevance-gated budgeted recall, writer pass; `transcript_log` is the writer's durable buffer with a `temp` column.
- **No speaker column** anywhere: the transcript stores `user_text` and `assistant_text` pairs. FR-MEM-2 (name the speaking waifu) needs a migration (`memory/migrate.py`) and a writer-prompt change.
- Memory writes never go to the cloud (Yuri D-015).

## 10. Features inherited that the SPEC does not mention

| Feature | Where | Proposal (D-029) |
|---|---|---|
| **Temp Chat** (nothing read from or written to memory) | `set_temp_mode`, `temp_turn_flags` | **Keep**; add as FR-MEM-5 |
| Camera and screen look-intent, `capture_screen`, `capture_camera`, `read_clipboard` | `senses/`, `tools/vision.py` | **Keep** as the `＋` tray camera/screenshot |
| Emotion tags and expression driving | `persona.py`, `expression-life.ts` | **Keep**; FR-ST-7 already has hooks |
| Transcript log panel, quick-action menu | `index.html` | Rebuilt in K1 |
| **Task Guide mode** (tracks a user task, nudges when they drift) | `senses/task_guide.py`, `_task_guide_loop` | **Park**: keep code, disabled by config, hidden in v1 |
| **OCR watch / ambient remarks** (unprompted comments about the screen) | `senses/ocr_watch.py`, `_ocr_watch_loop` | **Park**, same |
| `scene_state` (client reports where she is, injected into the turn) | WS + `_scene_state` | Keep; it is the seed of FR-3D |
| API-model toggle badge | `qa-api-model`, tray | Replaced by the model switcher |

## 11. Frontend

- A **stage-first widget**: full-window avatar canvas, caption, input box, mic button, action button (`#stage-container`, `#avatar-canvas`, `#caption`, `#input-box`, `#mic-button`, `#action-button`), a quick-action menu (Temp Chat, Log, Emotion test, Camera, OCR watch, API model, Upload), a transcript log panel. This is very close to Kōkyū's **Stage view**; the **Chat view and sidebar do not exist**.
- Status heart: `#status-orb` (connecting = arc around the outline, connected = lavender, listening = pink and beating, working = fast arc), styled in `style.css`. Edit `index.html` by id (`tests-fe/index-html.test.mjs` guards it).
- Avatar code reusable as the engine: `lipsync.ts`, `eyes.ts` (gaze, micro-saccades, blinks), `idle-motion.ts`, `expression-life.ts`, `framing.ts` (frames from the model's top), `camera.ts`, `vrm-report.ts`, `file-upload.ts`, `mic-stream.ts` (20 ms PCM16 at 16 kHz), `ws-client.ts`.
- The VRM path is fixed: `public/vrm/yuri.vrm` (or `window.__YURI_MODEL_PATH__`); `scripts/doctor-lib.mjs` checks it. Per-waifu VRMs (FR-W-1) need loading from app data.
- No React, no state library, no CSP.

## 12. Rust shell (`lib.rs`)

- **Window:** 340×480, borderless, transparent, always on top, `skipTaskbar: false` (a desktop widget). Kōkyū needs a normal app window in K1.
- Job Object (`win32job`, kill-on-close), tray with camera indicator, F9 push-to-talk global shortcut, `anchor_bottom_right`, **`toggle_click_through` command** (useful for pets), `sync_cloud_toggle`.
- Reads `src-tauri/launcher.local.txt` (gitignored; example next to it) for machine paths; spawns the orchestrator **and** GPT-SoVITS in parallel; waits for ports; `kill_stale_listeners(9880, …)` and `(8765, …)`; graceful shutdown by `POST /shutdown`, then kill.
- Ports **8765** and **9880** are hard-coded in Rust and Python; the identifier is `com.yuri.companion.app`; `security.csp` is `null`; bundle target `nsis` is already set.
- `cargo check` was **not run** here.

## 13. Config surface (v2)

Blocks: `providers`, `models`, `roles`, `routing`, `privacy`, `budget`, `audit`, `llm`, `voice`, `tts`, `speech`, plus memory, senses and others further down (not read). `config.example.yaml` embeds **machine-specific Windows paths** (GPT-SoVITS install, reference clip) that must not be copied into Kōkyū's public example. Windows paths need single quotes.

## 14. Luna (for later phases)

- `src/sandbox.ts` (1641 lines): walk controller using authored VRMA clips (`world-walk`, start/stop variants), idle variants and gestures, wander controller with arrival radius, anchors, contact shadow. The apartment is a single prebuilt model loaded from `public/apartment/` (only a README is tracked). Luna's Phase 10 (sandbox apartment) is **frozen** by the user. This is the seed for K4 (pet baking: needs idle/sit/walk clips) and K5.
- Luna **tracks** an open-licensed VRMA pack in `public/vrm-animations/` with `LICENSES/` and `NOTICE.md`; Yuri tracks only the notices. Kōkyū's `.gitignore` currently excludes `*.vrma` (decide at K4).
- Luna's `CLAUDE.md` and `docs/DECISIONS.md` define the **bundle-based handoff** (commit in a sandbox, give the user a `git bundle`, user merges and pushes). Kōkyū follows it (D-030).

## 15. Gap table: SPEC versus Yuri

| SPEC | Yuri today | Work |
|---|---|---|
| FR-W (waifu = data) | Persona is a code constant; one VRM path | K0: pack model, registry, seed script |
| FR-W-3 invariance | No waifu concept; router has no persona input | K0: tests |
| FR-C-1 threads | One in-memory `history` per connection plus `transcript_log` | K1: SQLite threads, conversation manager |
| FR-C-2 token streaming, Stop | Clause-level `speak`; `stop` exists | K1: token events |
| FR-C-6, 7 sidebar, Chat/Stage | Stage-first widget only | K1, K2 |
| FR-M per-thread model, effort | Global model; local provider ignores `model`; toggle affects `mind` only | K1: `llm.py` parameters, `chat` role |
| FR-R-3 local-only roles | **Exists** (role `local_only`, startup invariant) | K0: map tests to FR-R-3 |
| FR-R-4 attachments to chosen API model | Untrusted content **blocks all cloud egress** | K1: policy change (D-025) |
| FR-R-5 no silent fallback | Router falls back local on offline/budget | K1 |
| FR-V-1 per-waifu voice | `synthesize(text)` uses global clip | K0-11 |
| FR-V-7 no silent pyttsx3 | Automatic fallback | K0-11 |
| FR-MEM-2 speaker names | No speaker column | K0-12 |
| FR-ST (stage) | **Mostly exists** | K2: auto-frame per waifu, captions, docked input |
| FR-P pets | `toggle_click_through` exists; no baker | K4 |
| FR-3D | Luna sandbox | K5 |
| FR-SET | One setting | K1 |
| FR-DIST | NSIS target set; CSP null; identifier Yuri's | K7 (CSP earlier, K1) |

## 16. Things that will bite (from Yuri's handoff and this reading)

- **Do not bulk-edit source with naive string replacement** (it once replaced every "a" with "w" in five files). Rename with targeted, reviewed edits; run tests after each step.
- `_send_speak` / `speech.prepare()` is the only place text becomes audio; new speech paths must use it.
- VAD frames must be exactly 640 bytes (20 ms at 16 kHz).
- STT transcription is awaited inside the WS receive loop (about a second of frames can queue).
- Port 1420 is shared by `npm run dev:ui` and `tauri dev`; never run both.
- The first `tauri dev` after a Cargo profile change recompiles every crate (minutes).
- Memory never deletes; anything reading `transcript_log` for memory must skip `temp=1` rows.
- The WebView2 autoplay policy was a past cause of silent speech; `additionalBrowserArgs` in `tauri.conf.json` carries the fix.

## 17. Open items from this inventory

1. Keep or park Task Guide and OCR watch (D-029 proposes park).
2. Confirm D-025 (router and egress policy) before K1.
3. Track the licensed VRMA pack or not (K4).
4. The user's machine facts are still unverified (K0-00): Node, Rust, Python versions, WebView2, `ollama list`, VRAM.
