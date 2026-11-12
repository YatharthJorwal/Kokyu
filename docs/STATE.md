# STATE — Kōkyū

**Living document.** The truth *right now*. Rewrite it at the end of every session (CLAUDE.md §2). If this file and reality disagree, tell the user first. Narrative lives in `HANDOFF.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-11, session 1
- **Current phase:** K0 in progress. K0-00 to K0-02 done (docs only). **K0-03 onward (code) is waiting for the user to approve the K0 plan** in `TODO.md` / `HANDOFF.md`.
- **Repo:** `github.com/YatharthJorwal/Kokyu`, public, `main` at `704c05d` (docs commit) plus the session-1 docs bundle (not yet merged by the user when this was written).
- **Seed:** Yuri `e32af4f710cdf4e8c141df667a18c53046557ea3` (proposed, D-028); nothing copied yet.
- **Last green run:** Yuri as-is, in the Linux sandbox only (see §3). Kokyū has no code.

## 1. What exists

| Area | State |
|---|---|
| Docs (SCOPE, SPEC, ARCHITECTURE, RULES, DECISIONS, TODO, STATE, HANDOFF, TTS-BACKEND), README, LICENSE, `.gitignore`, `.env.example` | Committed and pushed (`704c05d`) |
| `docs/notes/yuri-inventory.md`; corrections to ARCHITECTURE, SPEC, RULES, CLAUDE, README, TTS-BACKEND; decisions D-024 to D-031; rescoped K0 | In the session-1 bundle, **not yet merged** |
| `docs/PRODUCT.md`, `docs/notes/product-vision-handoff-2026-11-11.md`; D-032 to D-039; TODO restructured (LIC-1, Track B, K1b, W, release train); SPEC FR-COMP, FR-WIZ, FR-VP | In the same cumulative bundle, **not yet merged** |
| Kernel, shell, UI, tests | Nothing yet |
| TTS backend (Track T) | Not started. The user's existing GPT-SoVITS (v3lora) install can serve the K0 voice gate |
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
| API | AI Router key |
| VR headset | None |
| Local folder | `Kokyu.ai`; the kernel folder `KASANE` stays uppercase |

### Sandbox (Claude's session environment, not the PC)

Linux, Python 3.12.3, Node 22, npm 10. No Rust toolchain use, no GPU, no display, no Ollama, no GPT-SoVITS.

### Unknown on the user's PC (verify in K0-00)

Node, Rust, Python versions; WebView2; whether Ollama runs as a service; where the Luna and Yuri VRMs and reference clips are; the path of the existing GPT-SoVITS install (Yuri's example config shows a v3lora folder).

## 3. Verification status

| Claim | Status |
|---|---|
| Kokyu repo holds the docs commit `704c05d` | **Verified** (cloned 2026-11-11) |
| Yuri at `e32af4f`: `pytest orchestrator` | **641 passed** in the sandbox (Linux) |
| Yuri: `npm run test:fe` | **65 passed** in the sandbox |
| Yuri: `tsc --noEmit`, `npm run build` | **Pass** in the sandbox |
| Yuri: `cargo check` | **Not run** (no Tauri/Windows libraries in the sandbox) |
| Yuri running on the user's PC (window, audio, mic, GPT-SoVITS) | **Not verified by me**; Yuri's own handoff says a real mic/speaker gate was not done |
| Yuri/Luna READMEs, `HANDOFF.md`, decision headings, config, router, bus, TTS, persona, Rust function map | **Read** |
| Yuri's `ROUTING.md`, `PHASES.md`, `phases/*`, `memory/*` and `senses/*` bodies, most of `src/*.ts` | **Not read** |
| WebSocket payload shapes other than `speak` | **Not verified** (names only) |
| GPT-SoVITS `/tts` contract (`text`, `text_lang`, `ref_audio_path`, `prompt_text`, `prompt_lang` → WAV; port 9880) | **Confirmed from Yuri's code and config**, not re-run |
| Other GPT-SoVITS API parameters in `TTS-BACKEND.md` | **Not verified** |
| VRAM figures in `ARCHITECTURE.md` §13 | **Estimates** except model file sizes |
| Latency/fps numbers in `SPEC.md` | **Targets**, nothing measured |
| Pet overlay approach | **Unvalidated** (K4-01 spike) |
| Dodo Payments is a Merchant of Record; its acceptable-use rules cover a companion product | **Unverified** (Track B-3) |
| GPT-SoVITS Windows integrated package is officially distributed and scriptable to install | **Unverified** (Track T) |
| A small built-in voice model with a suitable license and quality exists | **Unverified** (K2 spike) |
| PyInstaller kernel triggers antivirus false positives | **Known general risk, not tested here** (K1b) |
| Ollama installer supports silent install | **Unverified** (W-02) |

## 4. Known issues and risks

### Findings from the inventory (gaps, not bugs; full table in `notes/yuri-inventory.md` §15)

- Persona is a code constant; no waifu concept; one VRM path (`public/vrm/yuri.vrm`).
- No threads, no token streaming, no model concept in the protocol; `ws_endpoint` is about 580 lines owning a per-connection history.
- The local provider ignores the `model` argument; the API toggle only affects `mind`, which nothing calls.
- Untrusted content blocks **all** cloud egress, which conflicts with attaching a file to a chosen API model (D-025).
- `tts.synthesize(text)` takes no voice argument and falls back to pyttsx3 automatically.
- `transcript_log` has no speaker column.
- Window is a 340×480 borderless widget; CSP is `null`; identifier is Yuri's; ports 8765/9880 are hard-coded.
- `config.example.yaml` contains machine-specific Windows paths.

### Inherited (from Luna/Yuri; re-verify on the PC)

- faster-whisper on CUDA failed on this machine (missing `cublas64_12.dll`); STT runs on CPU.
- Killing instead of tray Quit loses that session's memory consolidation.
- Port 1420 is shared by `dev:ui` and `tauri dev`.

### Risks (see `SCOPE.md` §13)

1. 12 GB VRAM shared by LLM, TTS and rendering.
2. Effort levels differ per model.
3. Persona bleed in two-waifu scenes.
4. TTS setup lives outside the repo and can drift.
5. Zero-shot clip quality varies.
6. Paste-only prompt box may frustrate small edits.
7. Overlay approach for pets may misbehave with fullscreen games.
8. The sandbox cannot verify Rust, audio or GUI work; those stay manual gates (D-030).
9. **License undecided while the repo is public** (D-032): pushing code would publish it under MIT.
10. Non-technical users need an API key or a capable GPU; the API-key step is the real onboarding wall (`PRODUCT.md` §3).

## 5. Recent issues log

Newest first. Format: `date · area · symptom · cause · status`.

| Date | Area | Issue | Status |
|---|---|---|---|
| 2026-11-11 | docs | Early docs assumed a `kasane` Python package, `npm run dev` = browser tab only, a draft protocol, and a kernel that starts TTS lazily. All wrong against the real code | Corrected in session 1 (D-024, D-027, `ARCHITECTURE.md`, `CLAUDE.md`) |

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
