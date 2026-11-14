# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** If the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-14 (evening)
- **Session:** 3, second half (normal window, llama.cpp + the 35B MoE as the chat model, boot warm-up)
- **Written by:** Claude, with the user (Yatharth)

## 1. The project in ten lines

1. Kōkyū: a Windows chat app for a roster of AI companions; KASANE (`KASANE/`) is the Python kernel; Tauri + three.js shell.
2. A waifu is a **voice and a persona only**; she never changes the model, intelligence or capabilities. Memory is shared. (D-003, D-005)
3. **Luna and Yuri ship as the two premade companions** with the user's own assets (D-041).
4. The code is **proprietary**, not open source (D-040); keep the repo private.
5. Zero-shot voices: each request carries the speaking waifu's clip and transcript (D-006). Development uses the existing GPT-SoVITS at `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (D-042).
6. Seeded from Yuri (verbatim commit `0cd2d20`), renamed to `KASANE/`, port 8780.
7. Commercial and release work (Dodo, website, signing) is deferred until the product is developed (D-043).
8. Spec v1.0 baseline is final (D-044). Changes go through new decisions.
9. Since session 3, Claude works **directly on the user's Windows PC** (`D:\AI\Kokyu.ai`, via the Claude desktop app, often while the user is away) and commits and pushes `main` itself. Rust, Node, the venv, Ollama and the GPU are there; Claude cannot see the window or hear audio, so visual/audio results stay "not verified" until the user looks.
10. Plan: `TODO.md`; K1 in progress (K1-00 to K1-00d, K1-01, K1-01b done; next K1-02).

## 2. How the user works

Solo developer, casual, wants direct commands (no manual file shuffling), phases with gates, honesty about verified vs not. Session 3: "work on the next phase, commit for me and push", item by item, pushing after each green `npm run check`. Treats the feature list as growing ("we will discover features"); the phase plan stays. Asked for "a better model": the **Qwen3.6-35B-A3B on llama.cpp** is now the default chat model on this PC.

## 3. What happened

### Session 3 (2026-11-14)
- **Run on the user's PC for the first time.** `npm run check` (with cargo) was red on Windows only because of a path-separator test bug; fixed (`baa0b54`).
- **Decided by the user:** D-025 approved (D-047). Task Guide and OCR watch become real features, "screen companions" (D-048, SPEC §2.17 FR-SC-1..6, TODO K1-05b). K1 starts without the K0 manual gate; deliver item by item.
- **Built, first half:** K1-00 threads store + conversation manager (`5deb6b6`); K1-00b typed protocol v1 + token streaming (`32d9bef`, D-049); K1-00c per-thread model/effort, `chat` role, D-025 egress rules (`5c7a9ce`, D-050), checked live against Ollama.
- **Built, second half:**
  - K1-00d (`3865ccd`): normal 1200×800 decorated window, centred; explicit CSP for build and dev; a frontend test guards both. Temp Chat per thread already existed (K1-00). **The window was not looked at.**
  - K1-01 (`e05154e`, D-051): spike, then a real `llamacpp` provider. The kernel starts `llama-server` (Ollama's bundled copy) per preset from `config.yaml` `llamacpp.presets`; `chat.default_model_ref` picks the default. Spike: all experts on the CPU (`--n-cpu-moe 40`) + 10 threads = ~3 GB VRAM, ~23 tok/s generation, 19.5 GB RAM mapped. Per-turn system notes ride on the user message so the server's prompt cache hits (second turn: 23 tokens re-read, first token 0.8 s).
  - K1-01b (`bd1de6d`, D-052): boot warm-up of the default chat model; **fixed an inherited bug**: the Ollama provider ignored the routed model, so the classifier and memory writer always ran on the 9B (and the audit log lied). Helpers now use their configured model; `null` = the reflex model (new default, so a 9B-only PC keeps one model in VRAM); `llama-server` start keeps the helpers loaded; tray Quit stops `llama-server`.
  - **Live result in the real kernel:** after the background warm-up (~2 min 20 s), the first WebSocket message got its first token in **1.7 s** (it was 49.7 s before the fix, 74 to 111 s without warm-up). VRAM 8.4 GB.
- **The user's `config/config.yaml` now exists** (gitignored, a copy of the example plus: the 35B preset, `chat.default_model_ref: 'local:llamacpp/qwen3.6-35b-a3b'`, helpers on `qwen3.5:4b`).

### Session 2 (2026-11-12)
- **Decided by the user:** not open source; Luna and Yuri are the defaults (self-made VRMs, ElevenLabs-generated voices); Dodo and release work wait; the SoVITS path; "finalize the spec and proceed" (D-040 to D-044).
- **Built (Phase 0):** verbatim Yuri seed; rename to `KASANE/`; `paths.py`; waifu packs and registry; prompt addendum; per-waifu TTS; `switch_waifu`; speaker-tagged memory; invariance tests; `scripts/build_premade.py`; Companion picker; `npm run check`; `THIRD-PARTY.md`.

## 4. Where we stopped

K1-00d, K1-01 and K1-01b are done, green (`npm run check`: test:fe 83, cargo check, pytest 811) and pushed. **Next is K1-02 (React shell on the v1 protocol).** It is a large change, so its plan was put to the user for approval before any code; check the conversation or ask which option they chose. Nothing new is visible in the window yet: it still shows Yuri's widget, just in a normal window.

## 5. Next session: start here

1. `git log -5`, `git status`, `npm run check` (`KOKYU_PYTHON` = `.venv\Scripts\python.exe`).
2. K1-02 per the approved plan. Then K1-03 sidebar, K1-04 thread view, K1-05 input + tray, K1-05b screen companions.
3. The K0 manual gate is still open (`STATE.md` §6): the premade packs need the user's VRM/wav paths and traits.

**Commands the user may want (PowerShell, in the repo folder):**

```powershell
npm run check
npm run tauri dev
# premade companions (paths and traits are the user's):
.\.venv\Scripts\python.exe scripts\build_premade.py --yuri-vrm "C:\path\yuri.vrm" --luna-vrm "C:\path\luna.vrm" --luna-repo "C:\path\to\Luna" --yuri-traits "trait1,trait2" --luna-traits "trait1,trait2"
```

## 6. Open questions for the user

- K1-02 layout (asked this session): see the conversation.
- Which traits describe Luna and Yuri (the build script needs 1 to 12 adjectives each)?
- Track the licensed VRMA animation pack in git (K4)?

## 7. Traps and gotchas

- **No bulk string replacement** in source (Yuri once corrupted five files that way); targeted edits, tests after each.
- **Python edit scripts and backslashes:** a Windows path inside a normal Python string turns `\a`, `\b`, `\t` into control characters (it happened to `config.yaml` this session and to this file's PowerShell line in an earlier one). Use raw strings or `\\`, and scan for control characters after editing.
- Kernel modules are **flat**: `import paths`, `from audio import tts`. Tests have **no `__init__.py`**.
- Tests stub `llm.<fn>`, `tts.synthesize` and `router.stream_with_tools` by module attribute. **Stubs of `llm.stream_reply` / `stream_reply_with_tools` must accept keyword arguments** (`model=` is always passed now, D-052).
- `_run_turn` must never mention a waifu (a test enforces it).
- Ports: kernel **8780**, GPT-SoVITS **9880**, Vite **1420**, **llama-server 8080** (`llamacpp.port`). A busy 8080 at start is refused with a message (usually a leftover `llama-server.exe` from a killed kernel: end it in Task Manager). **Ollama's own runners are also called `llama-server.exe`**, so check the port, not the process name.
- **`KOKYU_DATA_DIR` also moves where `config.yaml` is read** (`<dir>\config\config.yaml`); without one there, the example config loads (no 35B default). Copy it in for live tests in a scratch folder.
- **Tests read the user's `config/config.yaml`** when it exists. The suite passes with the 35B default, but keep new tests independent of local config (patch `CONFIG`).
- Quit via the tray (or `POST /shutdown`); killing loses memory consolidation and, outside Tauri's Job Object, leaves `llama-server` running.
- The 35B maps ~19.5 GB of RAM. With other heavy apps open, generation slows (one spike run: 7 tok/s).
- TestClient WebSocket tests: patch `app._shutdown_event` with a fresh `asyncio.Event()`, `app._driver` and `app._conversation_manager` to None, and set `KOKYU_DATA_DIR` to tmp.
- Git Bash on this PC: `python3` exists; use the venv Python for edit scripts; write long scripts to the scratchpad instead of inline heredocs with fallbacks.

## 8. Deliberately not done

- Real-window, audio and visual verification (Claude cannot see or hear the PC).
- A "loading model" UI state (moved to K1-10, the model chip).
- A pinned llama.cpp download (W-03); presets move to `models.yaml` with K1-07; the VRAM manager is K1-09.
- Hiding Task Guide and OCR watch; renaming Cargo/binary/log names; a `kernel.port` config key.
- Yuri's old memory is not imported into the new `memory.db`.

## 9. Update checklist (end of every session)

- [ ] Date, session, author
- [ ] §3 new entry; §4 exact stopping point; §5 first actions; §6 open questions only
- [ ] §7 new traps; §8 skipped items
