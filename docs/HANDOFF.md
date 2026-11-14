# HANDOFF — Kōkyū

**Read this at the start of every session. Rewrite it thoroughly at the end.** If the date below is old, trust `git log` over this file and ask the user. Status and numbers are in `STATE.md`; the plan is `TODO.md`.

- **Last updated:** 2026-11-15, about 01:30 (the user went to sleep; the PC had been on since 13:00)
- **Session:** 3, a long one (14 to 15 November): K1-03 to K1-08b
- **Written by:** Claude, with the user (Yatharth)

## 1. The project in ten lines

1. Kōkyū: a Windows chat app for a roster of AI companions; KASANE (`KASANE/`) is the Python kernel; Tauri + React + three.js client.
2. A waifu is a **voice and a persona only**; she never changes the model, intelligence or capabilities. Memory is shared. (D-003, D-005)
3. **Luna and Yuri ship as the two premade companions** with the user's own assets (D-041). Their personas come from `persona.py` / `persona.ts` in the user's Luna and Yuri GitHub repos.
4. The code is **proprietary** (D-040); keep the repo private.
5. Zero-shot voices through the existing GPT-SoVITS at `D:\AI\GPT SoVITS\GPT-SoVITS-v3lora-20250228` (D-042).
6. Kernel on 127.0.0.1:8780; llama-server 8080; GPT-SoVITS 9880; Vite 1420.
7. Default chat model on this PC: **Qwen3.6-35B-A3B on llama.cpp** (D-051), warmed at boot (D-052); about 2 minutes to load.
8. Spec v1.0 is the baseline (D-044); changes go through new decisions, and **every commit and decision cites its FR/D IDs** (the user checks this).
9. Claude works **directly on the user's Windows PC** (`D:\AI\Kokyu.ai`, Claude desktop app), often while the user is away, and commits and pushes `main` item by item after a green `npm run check`. Claude cannot see the Tauri window or hear audio: those results stay "not verified" until the user looks.
10. Plan: `TODO.md`. K1 is most of the way done (§4).

## 2. How the user works

Solo developer, casual, wants direct commands and no manual file shuffling, phases with gates, honesty about verified vs not. Standing goal for this stretch: **"continue till K1 is done"**, with the note that loading the 35B is slow, so keep the model selector as documented and offer other models (done in K1-10 and K1-08b). Commit and push item by item. "Ultracode" is often on: run Workflow reviews (find, then adversarially verify) on substantive changes; they have found real bugs every time. The user sometimes toggles a "ponytail" mode (smallest complete change; end replies with what was skipped and the risks).

## 3. What happened

### Session 3 (14 to 15 November 2026)
- **First half (14th):** ran on the PC for the first time; K1-00 to K1-02 (threads, protocol, per-thread model, window, llama.cpp 35B, warm-up, React chat window). See `git log` up to `4d72af6`.
- **Then, in order (all pushed):**
  - **K1-10 + K1-07a** (`c2b1832`, review fix `fb83d52`; D-054): the model chip and popover in the input row, one background loader with a "waking up" card (the user asked for a creative loading message: "Yuri is waking up…", "Rubbing the sleep out of Yuri's eyes…"), Try again / Switch model.
  - **K1-03** sidebar (`9acb83f`); **K1-04** Markdown, Copy, kernel-side Regenerate/Retry (`ba4669b`, D-055); **K1-05** tray, attach, heart (`2d5c6c2`); **K1-05b** screen companions (`9d7ee4d`, D-056); **K1-06** companion chip and dividers (`5097f37`).
  - **Review rounds** fixed real bugs: `c1a222b`, `460aa1f` (ambient content reached API models, and the websocket accepted any Origin; D-057), `54bbcbd`, `af1aa0d`, `2daa022`.
  - **K1-08** (`c54a938`, D-058): the AI Router provider bills, caps and audits every call truthfully (tool rounds, Stop, failures; reservations for calls in flight; PRICE_UNKNOWN while a cap is on).
  - **K1-08b** (`5b04a30`, D-059): the user chose **one API endpoint at a time** (AI Router, OpenRouter or DeepSeek preset, or a custom one in config). The end-user key goes into the Windows Credential Manager through the Rust shell (`src-tauri/src/credentials.rs`, `Kokyu/api-key/<id>`). The shell hands it to the kernel at spawn (`KOKYU_API_KEYS`, removed at import by `KASANE/shell_keys.py`) and sends live changes as JSON lines on the kernel's stdin. The model menu's API heading has a **Key** button with a small form. The review found 8 real problems, all fixed with tests before the commit. The worst: changing only `preset:` in a copied config would have sent the new provider's key to AI Router's URL.
- **Peer sessions (the user ran others in parallel):**
  - built the premade packs in `assets/premade/{luna,yuri}/` (untracked);
  - wrote `KASANE/vram.py` (K1-09) and the effort slider files (K1-11), untracked and not integrated;
  - relayed the user's answer on K1-07b (below);
  - wrote GPT Image prompts. The user's generated images are now in `docs/reference-images/` (chat UI, stage view, app icon).
- **User answers this session:**
  - D-025 approved (D-047).
  - K1-08b: one endpoint at a time.
  - K1-07b (relayed by a peer): "whichever out of config/model is appropriate". The chosen split: per-model capability/effort data in `config/models.yaml` as SPEC says, and the llama.cpp presets stay in `config.yaml`.

## 4. Where we stopped

K1-08b is committed and pushed (`5b04a30`). This docs commit closes the session. **K1 items left, in TODO order:**

1. **K1-04b** Token counts per message (FR-C-10): small.
2. **K1-07b** Capability registry in `config/models.yaml` (FR-M-10), with a DECISIONS entry superseding D-054's "Proposed" bullet and quoting the user's answer. It lands together with K1-11.
3. **K1-09** VRAM manager v1 (FR-M-6): integrate the peer's `KASANE/vram.py` (NVML via ctypes) into `model_loader.py`, `router/listing.py` (fits hints) and `app.py`. Add config keys `vram.headroom_mb: 512`, `vram.margin_mb: 512`, `vram.large_model_mb: 4096` and `vram.kv_mb_per_1k_ctx: 96`. Open design points:
   - cache the measurement per `ref@ctx`;
   - put a sanity cap on the measured delta.

   Deviations to record: multi-GPU counts as unknown; an unknown never refuses a load; a model that spilled to the CPU is never recorded.
4. **K1-11** Effort slider (FR-M-8, 9, 11): integrate the peer's `src/app/effort-slider.ts`, `ui/EffortSlider.tsx` and CSS, and add "max" to the `Effort` type and the kernel's EFFORTS.
5. **K1-12** Inline API failure UX with Retry / Switch model (FR-R-5), including error classes.
6. **K1-13** Settings (FR-SET-1, 2), Doctor (FR-SET-3), Memory viewer (FR-MEM-4). This is the big one. It also gets the custom API endpoint form (D-059).
7. **K1-14** Tests and the STATE/HANDOFF update.
8. **Gate K1:**
   - chat with one local and one API model;
   - change model, effort and companion mid-thread;
   - a forced API error shows the failure UX;
   - the user signs off on the layout against the reference (now `docs/reference-images/chat-ui.webp`).

Rough size: K1-04b and K1-07b are small. K1-09, K1-11 and K1-12 are medium, with two of them half-written by the peer. K1-13 is the largest. Expect one to two more long sessions to finish K1.

## 5. Next session: start here

1. `git log -5`, `git status`, then `KOKYU_PYTHON="$PWD/.venv/Scripts/python.exe" npm run check` (Git Bash) from `D:\AI\Kokyu.ai`.
2. Ask the user to run `npm run tauri dev` once. Ask them to check:
   - the window opens;
   - a voice line plays;
   - **model menu → API → Key**: save an AI Router key, pick an API model, send a message.

   Nothing Tauri-side and nothing API-side has been seen live yet.
3. Then K1-04b, K1-07b with K1-11, and K1-09, in TODO order (§4).

```powershell
npm run check
npm run tauri dev
```

## 6. Open questions for the user

- **D-058:** models with no published price (DeepSeek's) are **blocked** while a spending cap is on. Keep blocking, or allow them with a warning?
- **D-055:** the persona prompts say "no markdown", but replies now render Markdown. Relax that rule?
- **D-057:** move the websocket token check earlier (before the Origin check)?
- **Speaker tags** in memory: keep as they are?
- **Premade packs:** commit `assets/premade/` (the VRM and WAV files are large; D-041 un-ignores the folder on purpose), or keep them local?
- **App icon:** the new icon in `docs/reference-images/icon/` has opaque black corners. A transparent 1024×1024 PNG is needed before `npm run tauri icon`. One more reference image may still be coming: a peer said three references and one icon, and two references and one icon arrived.

## 7. Traps and gotchas

- **Stage explicit paths.** Untracked peer files (`vram.py`, effort-slider files, `assets/premade/` with VRM/WAV) sit in the tree; `git add -A` would commit them.
- **Bash heredocs mangle escapes:** `\\n` becomes a real newline and `'''` can break the heredoc. For edit scripts, write the file with the Write tool and run it with `.venv/Scripts/python.exe`. Use raw strings for Windows paths.
- **No bulk string replacement** in source; use single-match edits (`assert s.count(old) == 1`).
- Kernel modules are **flat** (`import paths`, `from audio import tts`); tests have **no `__init__.py`**.
- Tests stub `llm.<fn>`, `tts.synthesize`, `router.stream_with_tools` and `config.resolve_api_key` **by module attribute**. Stubs of `llm.stream_reply*` must accept keyword arguments.
- `_run_turn` must never mention a waifu (a test enforces it).
- **Keys:**
  - `shell_keys` holds at most one app key; the conftest fixture clears it around every test.
  - A preset's URLs cannot be overridden (D-059). A developer key with spaces is ignored.
  - The live Credential Manager tests are opt-in: `cd src-tauri && cargo test --offline --lib -- --ignored --test-threads=1`. Afterwards, check `cmdkey /list:Kokyu/*` shows NONE.
- **Router billing:** a call captures `catalog` and `api_id` when it starts. `_bill`, `_record` and `_settle` take them as arguments; do not read `self.catalog` there.
- **Ports:** 8780 kernel, 8080 llama-server (Ollama's own runners are also `llama-server.exe`: check the port, not the name), 1420 Vite, 9880 GPT-SoVITS.
- **`KOKYU_DATA_DIR`** also moves where `config.yaml` is read. For live tests in a scratch folder, copy the config in.
- **Tests read the user's `config/config.yaml`** when it exists; keep new tests independent of it (patch `CONFIG`).
- **Quit via the tray** (or `POST /shutdown`). Killing loses memory consolidation and can leave `llama-server` running.
- **TestClient** opens each socket on its own loop. For WebSocket tests, patch `app._shutdown_event`, `app._driver` and `app._conversation_manager`, and set `KOKYU_DATA_DIR` to tmp.
- **Live UI tests:** run the kernel with a scratch `KOKYU_DATA_DIR`, run `npx vite --port 1420`, and drive the page in the built-in browser. Stopping the background shell does not stop Vite's `node.exe`: end it by PID.
- Open only one of `index.html` / `widget.html`: the second becomes an observer.

## 8. Deliberately not done

- Real-window, audio, API and visual verification (needs the user or a key).
- Custom API endpoint UI (K1-13); per-provider headings in the picker (one endpoint at a time).
- A pinned llama.cpp download (W-03); renaming Cargo/binary/log names; a `kernel.port` config key.
- Yuri's old memory is not imported into the new `memory.db`.
- The new app icon is not applied (needs a transparent PNG).

## 9. Update checklist (end of every session)

- [x] Date, session, author
- [x] §3 new entry; §4 exact stopping point; §5 first actions; §6 open questions only
- [x] §7 new traps; §8 skipped items
