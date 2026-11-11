# STATE — Kōkyū

**Living document.** The truth *right now*. Rewrite it at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. Narrative of what happened lives in `HANDOFF.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-11, session 0
- **Current phase:** Docs complete; **K0 not started** (waiting on DOC-1 review and DOC-2 first commit)
- **Repo:** `github.com/YatharthJorwal/Kokyu`, public, **empty** at 2026-11-11 (checked). First commit will be this doc set.
- **Seed:** Yuri commit not yet chosen (`____`), to be recorded at K0-03.
- **Last green run:** n/a (no code)

## 1. What exists

| Area | State |
|---|---|
| Docs (SCOPE, SPEC, ARCHITECTURE, RULES, DECISIONS, TODO, STATE, HANDOFF, TTS-BACKEND) | Written, uncommitted, **unreviewed by the user** |
| README, LICENSE (MIT), `.gitignore`, `.env.example` | Written, uncommitted |
| Kernel, shell, UI, tests | Nothing yet |
| TTS backend | Not started (Track T) |
| Waifu packs | None (Luna and Yuri to be seeded in K0-08) |

## 2. Environment

### Stated by the user

| Item | Value |
|---|---|
| GPU | RTX 3060 12 GB |
| CPU / RAM | i5-14400F; 32 GB (2×16) DDR5-4800 |
| OS | Windows (PowerShell) |
| Ollama models | `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L` (9.4 GB), `qwen3.5:9b` (6.6 GB), `qwen3.5:4b` (3.4 GB), `nomic-embed-text` (274 MB) |
| llama.cpp | Qwen3.5-35B-A3B Q4 available |
| API | AI Router key (DeepSeek, Qwen cloud, Gemini, ChatGPT, Grok, Claude) |
| VR headset | None |
| Existing projects | Luna (`github.com/YatharthJorwal/Luna`), Yuri (`github.com/YatharthJorwal/Yuri`) |

### Unknown (verify in K0-00)

Node version, Rust toolchain, Python version, WebView2 runtime, whether Ollama runs as a service, location of the Luna/Yuri VRM files and voice clips, state of the user's existing GPT-SoVITS folder (described as cramped).

## 3. Verification status

| Claim | Status |
|---|---|
| Kokyu repo is empty and public | **Verified** (fetched 2026-11-11) |
| Luna and Yuri READMEs were read | **Verified** (2026-11-11) |
| Yuri's code, `docs/` and tests were read | **Not verified / not read** |
| The heart animation exists in Yuri | Stated by the user, **not located** |
| Yuri's WebSocket message and bus event names | **Unknown**; `ARCHITECTURE.md` §5 is a draft |
| GPT-SoVITS API parameters listed in `TTS-BACKEND.md` | **From memory, not verified** against an install |
| VRAM figures in `ARCHITECTURE.md` §13 | **Estimates** except the model file sizes the user gave |
| Latency/fps numbers in `SPEC.md` | **Targets**, nothing measured |
| Whether WebView2 supports WebXR | **Unknown**, irrelevant until VR returns |
| Overlay vs per-pet window for pets | **Unvalidated** (spike K4-01) |

## 4. Known issues and risks

### Inherited from Luna/Yuri (from their READMEs as read on 2026-11-11; re-verify in K0-02)

- faster-whisper on CUDA failed on this machine with a missing `cublas64_12.dll`, so STT runs on CPU.
- Yuri's own README lists a real desktop launch (which needs a VRM file), the tray toggle in a running build and anything needing a microphone as not yet verified.
- Ports 1420 (Vite) shared by `tauri dev` and `dev`; Luna's kernel uses 8765.
- Killing the process instead of tray Quit loses that session's memory consolidation.

### New risks (see `SCOPE.md` §13)

1. 12 GB VRAM shared by LLM, TTS and rendering. Q6_K_L 9B likely too large next to TTS; measure.
2. Effort levels differ per model; the slider shows only supported detents.
3. Persona bleed in two-waifu scenes with small models.
4. TTS setup lives outside the repo and can drift; contract plus smoke test mitigate.
5. Zero-shot quality depends on the clip; creator validates and offers Test voice.
6. Paste-only prompt box may frustrate small edits; revisit if it hurts.
7. Overlay approach for pets may misbehave with fullscreen games or focus; fallback is window-per-pet.

## 5. Recent issues log

Newest first. Format: `date · area · symptom · cause (if known) · status`.

| Date | Area | Issue | Status |
|---|---|---|---|
| (none yet) | | | |

## 6. Manual gate sign-offs

| Gate | Date | Evidence | Signed by |
|---|---|---|---|
| (none yet) | | | |

## 7. Update checklist (end of every session)

- [ ] Snapshot header (date, phase, repo, last green run) rewritten
- [ ] "What exists" matches the repo
- [ ] Verification table: every claim marked verified / not verified honestly
- [ ] New issues logged; fixed ones marked
- [ ] Gate sign-offs recorded if any
