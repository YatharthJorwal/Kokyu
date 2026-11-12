# Kōkyū — Scope

> **Kōkyū** (後宮, "the inner palace"; ASCII *Kokyu* for paths and identifiers) is the app. **KASANE** (*Kernel for Adaptive Synthetic Agents, Networks and Embodiments*) is the kernel inside it.
> Status: scope v0.4 (2026-11-11). One-page overview; product direction and release boundaries are in `PRODUCT.md`, requirements in `SPEC.md`, design in `ARCHITECTURE.md`, decisions in `DECISIONS.md`. Successor to Luna and Yuri. Local-first Windows desktop app.

## 1. What this is

A desktop chat app for a roster of AI companions ("waifus"). It looks and behaves like a modern chatbot UI: one input box, one model picker, a history sidebar. Around that core sit an Ani-style stage where her VRM stands in front of you, 2D desktop pets, and a walkable 3D space.

Two rules shape everything:

1. **A waifu is a voice and a persona, nothing more.** Switching her never changes the model, its intelligence, its capabilities or its permissions. Those belong to the app and the thread.
2. **Core first.** Chat, stage, voice and the waifu creator ship before pets and 3D. Agent mode and VR come later (§12).

Axes of the KASANE acronym:

| Axis | Meaning here |
|---|---|
| **Agents** | Waifu registry, conversation manager, (later) the agent loop |
| **Networks** | Event bus, model router (local and API), thin clients |
| **Embodiments** | VRM stage, 2D desktop pets, 3D scenes (VR later) |

### Lineage

Fork **Yuri**, not Luna. Yuri already provides the role-based model router (spend caps, audit log, redaction), the typed event bus with a `trust` flag, the audio arbiter with VAD and barge-in, memory v2, the heart reply animation and the tray shell. Luna contributes the full-body sandbox (`sandbox.html`: room, fly camera, wandering), which is the seed of the 3D scenes. Luna and Yuri become the first two waifus.

## 2. Goals

1. One chat app, many waifus, switchable in one click; switching changes only voice and persona.
2. **One model switcher** with a clear Local / API split, plus an animated thinking-effort slider.
3. Per-waifu **zero-shot GPT-SoVITS voice** with seamless switching, served by a headless TTS backend that a CLI agent sets up against a fixed contract (§7.2).
4. A **stage view** where the waifu's VRM is in front of you (Ani-style).
5. Create a new waifu **entirely inside the app**.
6. 2D desktop pets and a walkable 3D space with one or two waifus.
7. Ship as a one-time-purchase Windows app: a signed installer plus a first-run wizard that sets up the rest (§14, `PRODUCT.md`).

## 3. Non-goals

- **Deferred (designed, not scheduled):** agent mode and VR (§12).
- Mobile, web-hosted, multi-user or cloud-sync versions.
- Fine-tuned GPT-SoVITS weights (zero-shot only).
- Integrating the GPT-SoVITS WebUI.
- Per-waifu models, tools, permissions or capabilities.
- Live2D, and any marketplace or sharing format.
- Sending camera frames, mic audio or screen captures to a cloud model.

## 4. Architecture

### 4.1 Waifu pack

Created and edited only through the app; it lives in app data.

```
waifus/<id>/
  waifu.yaml     name, traits, voice settings
  prompt.md      system prompt (pasted in the creator)
  model.vrm      avatar
  voice/ref.wav  zero-shot reference clip (~8 s)
  pet/           baked 2D sprites (generated)
```

```yaml
id: yuri
name: Yuri
traits: [calm, teasing, curious]
vrm: model.vrm
prompt: prompt.md
voice:
  ref_audio: voice/ref.wav
  ref_text: "exact transcript of the clip"
  ref_lang: en
```

There are deliberately **no** `models`, `tools` or `permissions` keys.

### 4.2 Kernel services (Python, FastAPI/WebSocket)

| Service | Responsibility |
|---|---|
| Waifu registry | Load and validate packs; create and delete via the app |
| Conversation manager | A thread has the user plus 1..n waifus. The "active waifu" only selects which prompt and voice are used |
| Model router | One user-selected chat model per thread; helper roles (§6.4); VRAM manager; AI Router provider |
| Memory | sqlite-vec, app-level and **shared by all waifus** (D-005); messages and episodes name the speaking waifu |
| Audio | STT, VAD, barge-in, TTS adapter, one arbiter so only one voice plays at a time |
| Scene director | Places embodiments, drives locomotion and gaze |
| Event bus | Typed events with a trust flag |

### 4.3 Clients

All clients speak the same WebSocket protocol to the kernel and hold no business logic.

- **Main window** (Tauri): chat, stage and 3D views.
- **Pet overlay** (Tauri): one transparent always-on-top window per monitor.

### 4.4 Tech stack

Tauri 2, Vite, TypeScript, `three` with `@pixiv/three-vrm`, React for UI chrome (the three.js engine stays an imperative module outside React state), FastAPI orchestrator, Ollama and llama.cpp backends, GPT-SoVITS (headless), faster-whisper, sqlite-vec.

## 5. The chat UI

### 5.1 Layout

```
┌───────────────┬───────────────────────────────────────────────┐
│ WAIFUS        │  [ Chat | Stage ]                             │
│  ◉ Luna       │                                               │
│  ◉ Yuri       │            conversation  /  stage             │
│  ＋ New       │                                               │
├───────────────┤                                               │
│ HISTORY       │      ┌─────────────────────────────────┐      │
│  Today        │      │ message…                        │      │
│   · thread    │      │ ＋          ♥ Yuri ▾  Model ▾  ➤ │      │
│  Yesterday    │      └─────────────────────────────────┘      │
│   · thread    │                                               │
├───────────────┤                                               │
│ ⚙ Settings    │                                               │
└───────────────┴───────────────────────────────────────────────┘
```

### 5.2 Sidebar

- **Top: waifus.** Click one to open a thread with her in **Stage view**. "＋ New" opens the creator (§8).
- **Middle: chat history**, grouped by date, with waifu avatar badges, search, rename and delete. Clicking an entry opens it in Chat view.
- **Bottom: Settings** (models, AI Router key and budget, audio devices, TTS backend path, pets, scenes, memory).

### 5.3 Input area

- Centered input box, multi-line; `Enter` sends, `Shift+Enter` adds a newline.
- **Bottom row inside the box.** Left: **＋ tray** (upload file, camera, voice, screenshot, paste image). Right: **waifu switcher**, **model switcher** (with effort), **send** (becomes **stop** while generating).
- **Heart animation** (from Yuri) while she thinks and replies.
- **Waifu switcher:** a chip with her avatar and name; the popover is a searchable list plus "＋ New waifu". Switching changes voice and persona only; model, effort and everything else stay as they are.

### 5.4 Stage view

The reference is Ani from xAI: she stands in front of you.

- **Framing:** bust-up, centered, dark neutral backdrop, facing the camera, derived automatically from the VRM's head and chest bones so no per-model camera constants.
- **Life:** spring-bone physics (hair, ears), procedural breathing, blinking and glances, eye contact toward the camera with subtle drift, lip-sync from her audio.
- **Overlay:** captions of what she is saying; the same input box docked at the bottom with a mic button for live voice; the chat log slides in from the side.
- **Chat | Stage** is a toggle on the same thread. Both views share all state.

### 5.5 Switching waifus mid-thread

Switching inserts a visible "Switched to Luna" divider, keeps the history on screen (each message tagged with its speaker), and from the next turn uses the new waifu's prompt and voice. Earlier lines are passed as context with speaker tags.

## 6. Models and routing

### 6.1 The model switcher

One control in the input row: a chip showing the current model and effort. It opens a popover:

- **Search box** at the top.
- Two clearly separated sections, **Local** and **API**. This is a list with two sections, not a toggle: picking a model from a section is the whole action, and the current model carries a check mark.
  - **Local:** installed Ollama models (`ollama list`) and llama.cpp presets (e.g. Qwen3.5-35B-A3B Q4). Each row shows its size and a fits/won't-fit hint from the VRAM manager.
  - **API:** the AI Router catalog (DeepSeek, Qwen cloud, Gemini, ChatGPT, Grok, Claude, and so on), grouped by provider with variant badges, plus a price hint where the catalog has one.
- The chip carries a local or cloud icon. Spend so far and the budget cap appear in the popover footer and in Settings.
- Selection is **per thread** (new threads inherit the last choice) and is independent of the waifu.
- **Failures are visible:** if an API model fails (for example "Request quota exhausted"), the turn shows the error inline with *Retry* and *Switch model*. There is no silent fallback to a different model.

### 6.2 Thinking-effort slider

Part of the same popover (and shown as a short label on the chip).

- A **slider with discrete detents**. The detents are the levels the selected model supports (for example Off, Low, Medium, High, Max). Unsupported levels are hidden; a model with no reasoning control shows no slider.
- **Animated:** the thumb glides between detents with a short spring; the track fill and a soft pulsing glow scale in intensity and speed with the level; while a reply is being generated the glow runs on the chip. A reduced-motion setting turns this into a static fill.
- **Mapping:** for API models it maps to the provider's reasoning-effort parameter where the catalog says it is supported; for local models it maps to thinking on/off and a thinking-token budget where the model and backend support one.
- Remembered **per model**, per thread. Independent of the waifu. Reasoning text is never spoken.

### 6.3 API Router, spend and privacy

- Uses Yuri's router: AI Router provider, `/v1/models` catalog, spend ledger, audit log, redaction.
- Choosing an API model is the user's explicit consent for that thread's text, including any recalled memory snippets injected into the prompt.
- **Always local, no exceptions:** camera frames, mic audio, screen captures, memory-writer jobs.
- The API key lives in `.env` or `config/secrets.local.yaml` (gitignored), never in a waifu pack or a thread.

### 6.4 Helper models

The user sees one chat model. Background helpers are configured in Settings → Advanced, run locally, and never appear in the switcher: classifier (speaker choice in two-waifu scenes), memory writer, embeddings (`nomic-embed-text`) and vision (camera and image attach).

### 6.5 VRAM (RTX 3060 12GB, 32GB DDR5-4800)

All figures are estimates; the VRAM manager measures with NVML.

| Item | Default | Notes |
|---|---|---|
| Local chat models | `qwen3.5:9b` Q4 (~6.6GB), `qwen3.5:4b` (~3.4GB), Q6_K_L 9B (~9.4GB) | Q6_K_L leaves little room next to TTS and rendering |
| Large local model | Qwen3.5-35B-A3B Q4 on llama.cpp, MoE experts on CPU | ~20GB in system RAM; needs a speed spike |
| Embeddings | `nomic-embed-text` | Always resident |
| STT | faster-whisper `small`, CPU | Keeps VRAM free |
| TTS | One headless GPT-SoVITS server, all waifus | §7 |

Ollama and llama.cpp cannot both hold large models at once, so selecting a model on the other backend makes the manager unload the first (`keep_alive: 0`) before loading the second. The user sees a spinner on the model chip.

## 7. Voice

### 7.1 Zero-shot voice per waifu

- Each waifu has her own reference clip (about 8 s WAV) and its exact transcript. GPT-SoVITS runs on **one base model** for everybody, and the clip and transcript are sent **with every request**.
- No weights are swapped, so switching waifus changes only request parameters: no reload, no wait.
- On waifu select the kernel sends a short **pre-warm** synthesis so the first real line is not slower.

### 7.2 TTS backend (delegated to a CLI agent)

The GPT-SoVITS install is set up outside this repo by a CLI agent, not through its WebUI. The app depends only on this contract:

- A **headless API server** in its own clean folder with its own virtual environment, GPU enabled, **no WebUI**, English-language README and logs.
- Started and stopped by the kernel as a child process (Job Object, as in Yuri); the folder path is set once in Settings.
- **API (api_v2-style):** `POST /tts` with `text`, `text_lang`, `ref_audio_path`, `prompt_text`, `prompt_lang`, streaming or chunked output; plus a health endpoint. The agent confirms the exact parameters against the installed version and writes them into the README.
- **Required behaviour:** a different reference clip on every request with **no restart and no weight swap**.
- **Agent deliverables:** one start command, one stop command, and a smoke-test script that synthesizes one sentence with two different clips back-to-back and prints the latency of each.
- **Gate (track T):** the smoke test passes on this machine.
- App side: `tts/gpt_sovits.py` speaks only this contract.

### 7.3 Speech input

faster-whisper (CPU) behind Yuri's VAD, with barge-in: speaking over her cancels the turn and stops playback. Push-to-talk via the global hotkey and a mic toggle in the UI.

## 8. Create new waifu (in-app only)

"＋ New waifu" opens a single form. Nothing outside the app is needed.

1. **Name.**
2. **VRM:** upload. Validated for humanoid bones and the `aa` and `blink` expressions; a live preview in Stage framing.
3. **Voice:** upload an **~8 s WAV** (accepted range 3–10 s). The app checks length, clipping, leading and trailing silence and level, then **auto-transcribes it** with faster-whisper and shows the transcript for correction (GPT-SoVITS needs the exact text). A **Test voice** button speaks a sample line.
4. **Personality traits:** adjectives entered as chips.
5. **System prompt:** a box the user **pastes into** (typing is disabled; Paste button and `Ctrl+V` only). Above it, an **Instruction block** is generated by the app from the name and traits, with a **Copy instruction** button. The flow is: copy the instruction, paste it into any LLM, copy the LLM's system prompt, paste it into the box (Appendix A has the template).
   - On paste the app strips code fences, rejects empty or placeholder text, and shows a token count.
   - **Clear** resets the box; to change the prompt the user re-pastes.
6. **Test chat:** an optional preview message with the current model and the new voice before saving.
7. **Save:** creates the pack and bakes the pet sprites in the background.

Deleting a waifu is also done in the app, with a confirmation.

## 9. Desktop pets (2D)

A waifu can be brought out of the chat as a small 2D companion on the desktop.

- **Bring out:** from the chat header or the sidebar's right-click menu. One to three at once.
- **Look:** 2D sprites **baked from her VRM** by an orthographic, transparent-background render through VRMA clips (idle, sit, walk). The atlas is stored in `pet/`. Without VRMA clips, the procedural idle and walk are baked instead.
- **Behaviour (state machine):** idle, sit, walk left or right (mirrored), react to click, be dragged, small looks and gestures. She walks along the bottom of the work area and can sit on its edge.
- **Window:** one transparent, undecorated, always-on-top **overlay per monitor** (primary only in v1) hosting all pets, hidden from the taskbar, **click-through except over opaque pixels**. A K4 spike validates this against one window per pet (D-014).
- **Interaction:** click opens a compact quick-reply box and speech bubble; she speaks through the normal audio arbiter. Right-click menu: open chat, send to 3D scene, dismiss.
- **Cost:** sprite animation rather than live 3D, so GPU use is close to zero.
- **Lifecycle:** pets live while the kernel runs (tray). Closing the main window does not close them.

## 10. 3D mode

A "3D" button on the stage puts the user inside a 3D space with their waifus.

- **Movement:** first-person walk with **WASD**, mouse look (pointer lock), Shift to sprint, `Esc` to release the cursor. Simple collision from per-scene collider data.
- **Scenes:** switchable from a menu without a restart. v1 ships **apartment** and **garden**.

```
scenes/<id>/
  scene.glb      geometry, baked lighting
  scene.yaml     spawn point, bounds, colliders, anchors (sofa, bed, bench…), lights/HDRI
```

- **Bringing waifus in:** pick **one or two**. Each spawns at a scene anchor, idles, wanders within waypoints, turns to face the user and walks over when addressed. Conversation is by voice or a text overlay.
- **Two waifus:** the helper classifier picks who answers (addressed by name, otherwise by relevance), one voice at a time. Each reply is generated with only that waifu's prompt, with the other's lines passed as quoted context to prevent persona bleed.
- **Budget targets:** at most about 300k triangles per scene with baked lighting, so rendering stays smooth beside the LLM and TTS.
- The renderer is kept XR-compatible but no XR work is done in v1.

## 11. Roadmap

Each phase has a gate that must pass before the next starts.

| Phase | Deliverable | Gate |
|---|---|---|
| **T (parallel)** TTS backend | CLI agent builds the headless GPT-SoVITS server to the §7.2 contract | Smoke test: two clips back-to-back, no restart |
| **K0** Skeleton | New repo from Yuri; waifu pack format; Luna and Yuri as waifus | Waifu box switches persona text and voice; model and effort unchanged |
| **K1** Chat shell | Sidebar, threads, input box, ＋ tray, heart animation, waifu switcher, model switcher (Local/API), effort slider | Chat with one local and one API model; change model, effort and waifu mid-thread independently |
| **K1b** Installer skeleton | Thin NSIS installer with the kernel sidecar, tested on a clean machine | Clean-machine install reaches an API chat |
| **K2** Stage and voice | Ani-style stage, lip-sync, zero-shot voice through the TTS contract, STT, barge-in, camera and file attach | Alternate two waifus mid-conversation: voice and persona change, no reload or audible delay |
| **K3** Waifu creator | The full in-app form (§8) | A new waifu created end-to-end without touching any file |
| **W** Components and wizard | Component manager, Doctor, Welcome to Kōkyū wizard, premade companions | Clean machine: installer to first reply |
| **K4** Desktop pets | Sprite baking, pet windows, state machine, click-through, quick reply | Two pets idle and walk for an hour; overhead measured |
| **K5** 3D mode | WASD, apartment and garden, scene switcher, one or two waifus with the turn arbiter | Walk, switch scene, talk to two waifus with no persona bleed |
| **K6** Hardening | Evals, perf budgets, crash recovery, docs | Soak test; docs complete |
| **K7** Release engineering | Signing, updater, license key, diagnostics, CI (§14) | Signed installer from a tagged release works on a clean machine |

Release boundaries (`PRODUCT.md` §4): **1.0** = T, K0 to K3, K1b, W, K6, K7; **1.1** = K4 and K5; **2.x** = agent mode and VR.

## 12. Deferred

**Agent mode** (after the core app). Planned as a Codex/DeepSeek-style harness inside the normal chat UI: the user grants a workspace folder; permission levels are read-only, write with approval (default) and write automatically; tools are list, read, search, create, edit and delete (delete always asks); every step appears in a collapsible timeline with accept/reject diffs; a backup is taken before each write with one-click undo; an audit log is kept; file contents carry `trust=false` so they can never authorise a write on their own; no shell execution at first. It runs on whatever model the switcher has selected, and the waifu stays a voice and persona on top.

**VR** (no headset available). When it comes back: a WebXR spike to find out whether it works inside WebView2, with fallback to a browser page served by the kernel.

## 13. Risks and open questions

**Risks**

1. **VRAM pressure:** LLM, TTS and rendering share 12GB. Mitigation: VRAM manager, fits/won't-fit hints, STT on CPU, baked 2D pets.
2. **Effort mapping differs by model.** Mitigation: show only the detents a model supports.
3. **Persona bleed** with small models in two-waifu scenes. Mitigation: per-speaker generation with only that waifu's prompt.
4. **TTS setup drift** because it lives outside the repo. Mitigation: the contract and the smoke test.
5. **Zero-shot clip quality** varies a lot. Mitigation: clip checks, auto-transcript, test voice.
6. **Paste-only prompt box** may frustrate small edits. Mitigation: re-open the instruction and re-paste; revisit if it hurts.
7. **VRM variety:** framing, missing expressions and heavy materials differ per model. Mitigation: auto-framing and validation at upload.

**Assumptions to confirm**

- "User cannot write it" means the prompt box is paste-only.
- Clicking a waifu opens Stage view; clicking a history entry opens Chat view; the effort slider lives inside the model popover.
- Helper models stay in Settings → Advanced and are not user-facing.

## 14. Distribution (planned)

See `PRODUCT.md` §4 to §6 for the release boundaries (1.0 / 1.1 / 2.x), commercial direction and asset checklist, and `ARCHITECTURE.md` §11 and §15 for the technical plan.

In short: a one-time-purchase Windows app sold from an official site, shipped as a signed per-user NSIS installer with the Python kernel as a sidecar (no Python or Node for the user). A **Welcome to Kōkyū** wizard detects and installs optional components (Ollama, llama.cpp, the GPT-SoVITS backend, the STT model) with the user's confirmation; model weights and large runtimes are never in the installer. User data lives in `%APPDATA%\Kokyu` and survives upgrades. The license is undecided and no code is published until it is (D-032).

## Appendix A: system-prompt instruction template

The canonical template lives in `SPEC.md` (Appendix A) so there is a single source of truth.
