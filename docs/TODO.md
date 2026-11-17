# TODO — Kōkyū

Phased plan with gates. Work **top to bottom inside the current phase**, one item at a time. Tick items with the commit hash: `- [x] K0-03 … (a1b2c3d)`. Do not start the next phase until its gate passed **and** the user approved (R-32). Requirement IDs refer to `SPEC.md`.

Last updated: 2026-11-15 (session 4: D-060 lazy boot, app icon; cleanup and UI plan proposed).

## Phase overview

Execution order (D-034): T (parallel), K0, K1, K1b, K2, K3, W, K6, K7, then K4 and K5. IDs are stable labels, not the order.

| Phase | Goal | Release | Status |
|---|---|---|---|
| Docs | Spec set, README, product direction | n/a | Done; session-1 bundle pending merge |
| ~~LIC-1~~ | License decided: proprietary (D-040) | done | **Done** |
| **T** | GPT-SoVITS component recipe by a CLI agent (parallel track) | 1.0 | Not started |
| **K0** | Skeleton: seed from Yuri, waifu pack, shared memory, invariance (rescoped, D-026) | 1.0 | **Code complete; waiting for the manual gate on the PC** (session 2) |
| K1 | Chat shell, waifu switcher, model switcher, API providers | 1.0 | Not started |
| **K1b** | Installer walking skeleton on a clean machine (D-035) | 1.0 | Not started |
| K2 | Stage view, voice providers, senses | 1.0 | Not started |
| K3 | In-app waifu creator | 1.0 | Not started |
| **W** | Component manager and Welcome wizard | 1.0 | Not started |
| K6 | Hardening | 1.0 | Not started |
| K7 | Release engineering: signing, updater, license key, diagnostics, CI | 1.0 | Not started |
| K4 | Desktop pets | 1.1 | Not started |
| K5 | 3D mode | 1.1 | Not started |
| D1, D2 | Agent mode, VR | 2.x | Deferred |

---

## Docs (session 0)

- [x] Scope v0.3, SPEC, ARCHITECTURE, RULES, DECISIONS, STATE, HANDOFF, TODO, TTS brief, README, LICENSE, `.gitignore`
- [x] DOC-1 User reviewed the docs (confirmed: shared memory, name Kōkyū, KASANE folder stays uppercase)
- [x] DOC-2 First commit pushed to `main` (`704c05d`)
- [x] LIC-1 License decided: proprietary, not open source (D-040)
- [x] PROD-1 Product direction and spec finalized as the baseline (D-044)

## Track T: TTS backend (parallel, separate agent) — brief: `TTS-BACKEND.md`

- [ ] T-1 Choose the install folder outside the repo; do not modify the old cluttered GPT-SoVITS folder
- [ ] T-2 Clean install of the newest stable GPT-SoVITS with zero-shot support; own venv; CUDA build matching the RTX 3060; record version/commit
- [ ] T-3 Headless API server, no WebUI, bound to 127.0.0.1, port configurable
- [ ] T-4 `start` and `stop` scripts, plus a health check
- [ ] T-5 `smoke_test` script: same sentence with two different reference clips back-to-back, no restart, prints latency per call
- [ ] T-6 English `INSTALL.md` and `README.md` in the backend folder; record exact API parameters actually accepted
- [ ] T-7 Measure VRAM use while idle and while synthesizing; report to the user (feeds `ARCHITECTURE.md` §13)
- [ ] T-8 `component.json` manifest so Kōkyū's component manager can reproduce the install: URLs, versions, SHA-256, sizes, Python/CUDA versions, start command, health URL, hardware requirements; the install must be scriptable and non-interactive
- **Gate T:** smoke test passes on this machine; parameters and VRAM numbers recorded in `STATE.md`.

## Track B: business and content (non-code, user-owned): DEFERRED (D-043)

Dodo Payments, website, pricing and release work come after the product is developed. Kept here so nothing is forgotten.

- [x] B-1 License decided (D-040)
- [ ] B-2 Price and free-trial policy (demo limits)
- [ ] B-3 Dodo Payments account; **read its acceptable-use and prohibited-business rules** against a companion product; confirm whether it is the Merchant of Record for VAT/sales tax
- [ ] B-4 Name and domain check for "Kokyu" / "Kōkyū" (basic trademark search)
- [ ] B-5 Premade companions: commission or create 2 to 3 VRMs and original voices with written rights (D-039)
- [ ] B-6 Code-signing options and cost (individual publisher eligibility)
- [ ] B-7 Website (separate repo): landing, screenshots, checkout, downloads, docs, support
- [ ] B-8 Privacy policy, terms (including intended audience age), refund policy, support channel
- [ ] B-9 Marketing plan (kept out of engineering docs; see the IP caution in `PRODUCT.md` §6)

## Phase K0: Skeleton (rescoped in session 1, D-026)

Goal: a running kernel and shell seeded from Yuri where **a waifu is a pack** and switching her changes only persona and voice. Everything marked "sandbox" can be verified by Claude (pytest, `test:fe`, `tsc`, `vite build`); everything touching Rust, a window, audio or a model needs the user (manual gate).

- [x] K0-00 Environment: sandbox baseline verified (Yuri: 641 pytest, 65 frontend, tsc, vite build). **User machine still unverified:** run the command block in `HANDOFF.md` §5 and paste the output into `STATE.md` §2
- [x] K0-01 Docs committed and pushed (`704c05d`)
- [x] K0-02 Yuri and Luna inventory: `docs/notes/yuri-inventory.md`; `ARCHITECTURE.md` §2, 3, 4.1, 5, 7.1, 9.1, 11 corrected; D-024 to D-031 recorded
- [x] K0-03 Seed commit: copy Yuri at `e32af4f` **verbatim** (excluded as in D-028); tests green in the sandbox as seeded (0cd2d20)
- [x] K0-04 Rename and rebrand in small reviewed steps (no bulk replace): `orchestrator/` → `KASANE/` (`git mv`), `conftest.py`, scripts, Rust paths; product name Kokyu, identifier `io.github.yatharthjorwal.kokyu`, window title, tray text, `YURI_*` → `KOKYU_*`, log prefixes, npm package name; kernel port 8765 → 8780 in Python, Rust, `ws-client.ts`; no hard-coded ports left in Rust (8a61fcd)
- [x] K0-05 `KASANE/paths.py` (dev `./data`, packaged `%APPDATA%\Kokyu`); replace `repo_path("data/…")` and other hard-coded locations; tests (cae608a)
- [x] K0-06 Config v3: strip machine paths from the example, move the TTS reference clip and transcript out of config (they become waifu data), add `waifus.dir` and `kernel.port`, TTS block becomes `tts.backend` (URL plus optional launch); update `config.example.yaml`; add `models.example.yaml` Done as: machine paths removed from code defaults and the example, legacy clip keys emptied; the waifu directory comes from `paths.py` and the kernel port stays the constant `PORT` in `app.py` (a `kernel.port` config key moved to the backlog). (4963246)
- [x] K0-07 `KASANE/waifus/`: pydantic model for `waifu.yaml` (FR-W-1, 4, 6), loader, validator, registry; unit tests (fda24ad)
- [x] K0-08 Persona as data (D-031): split Yuri's `SYSTEM_PROMPT` into personality (waifu prompt) and shared app addendum (emotion tags, speech rules); `scripts/seed_waifus.py` imports the Luna and Yuri prompts from paths the user supplies and writes `data/waifus/<id>/`; create `docs/THIRD-PARTY.md` Done as: premade packs are built by `scripts/build_premade.py` from the user's files; the persona prompts are copied **verbatim** and the emotion-tag rule lives in the shared addendum instead of splitting Yuri's prompt (D-045). `docs/THIRD-PARTY.md` created. (470c947)
- [x] K0-09 Active waifu in the existing single-history flow: per-connection active waifu; `switch_waifu` and `waifu_state` messages (`ARCHITECTURE.md` §5.2); system prompt swapped on switch; history kept (28f7f9e)
- [x] K0-10 `KASANE/prompting.py`: system assembly (persona + addendum), ephemeral blocks unchanged; unit tests (28f7f9e)
- [x] K0-11 TTS per waifu: `tts.synthesize(text, voice)` with the waifu's reference clip, transcript and language; backend URL from config; pre-warm; **pyttsx3 fallback off by default** (FR-V-7); typed error when the backend is down; tests with a fake server (4963246)
- [x] K0-12 Shared memory with speakers (FR-MEM-1, 2): `transcript_log` gains a speaker column through `memory/migrate.py`; `add_transcript_turn(..., speaker=)`; writer prompt and episode summaries name the waifu; migration and writer tests (65de8d5)
- [x] K0-13 **Invariance tests** (FR-W-3, FR-S-5): two fixture waifus; the `ModelRequest` messages differ only in the persona prompt; same role and model decision, same recall results, same tool schemas offered; only prompt and TTS parameters differ (28f7f9e)
- [x] K0-14 Map the existing local-only router tests to FR-R-3 (no behaviour change); add one test that no waifu field reaches `router.route` Done as structural guards: no waifu input in `router.decide`, `Router.complete`, `stream_with_tools` or `ModelRequest`; Yuri's existing role-pinning tests cover FR-R-3. (28f7f9e)
- [x] K0-15 Temporary waifu dropdown in the existing widget's quick-action menu, with a one-line debug readout (waifu, voice clip, model); no layout redesign (that is K1) Done as: Companion `<select>` in the quick-action menu, avatar swapped by one reload per switch (temporary until the K2 stage rework, D-046). (0a23332)
- [x] K0-16 `scripts/check.mjs` and `npm run check` (tsc, test:fe, build, cargo check, pytest; cargo skippable with a flag); green in the sandbox (ba7c2a3)
- [x] K0-17 Update `STATE`, `HANDOFF`, `TODO`, `DECISIONS` (this commit); the gate review is the user's manual checks below
- **Gate K0 (sandbox, automated): PASSED 2026-11-12** (pytest 718, test:fe 76, tsc, vite build; a real kernel plus websocket smoke test also passed).
- *Original wording:* invariance tests green; switching Luna ↔ Yuri changes only the persona prompt and TTS parameters (asserted); `pytest` + `test:fe` + `tsc` + `vite build` green.
- **Gate K0 (manual, user):** `npm run tauri dev` opens the Kokyu window; the dropdown switches waifus; replies differ in persona; the voice is audibly different per waifu using the **existing GPT-SoVITS install** (same `/tts` contract, so Track T is not required for this gate); `cargo check` passes on the PC.

## Phase K1: Chat shell

- [x] K1-00 Extract a **conversation manager** from `ws_endpoint` / `_run_turn`; SQLite **threads store** with `active_waifu_id`, per-thread `model_ref` and effort; divider messages (FR-C-1, 10, FR-S-2) (5deb6b6)
- [x] K1-00b Typed protocol (`KASANE/protocol/`, mirrored in `src/net/`), token streaming events, versioned frames (`ARCHITECTURE.md` §5.3) (32d9bef)
- [x] K1-00c `llm.py` takes a model and an effort/think parameter; `OllamaNativeProvider` honours `model`; `chat` role and the egress policy in `router/decision.py` with tests (D-025, FR-R-4, 5, 7) — **needs the user's OK on D-025 first** (5c7a9ce)
- [x] K1-00d Normal app window (replace the 340×480 widget window), CSP locked down, Temp Chat flag per thread (FR-MEM-5) (3865ccd; Temp Chat per thread landed in K1-00; the window itself not yet looked at)
- [x] K1-01 Spike: Qwen3.5-35B-A3B Q4 on llama.cpp with experts on CPU: VRAM, RAM, tokens/s; record numbers. Done with the user's **Qwen3.6**-35B-A3B, and extended into the `llamacpp` provider plus presets so it is the default chat model (D-051) (e05154e)
- [x] K1-01b Warm the default chat model at kernel start (load `llama-server`, read the system prompt once) so the first message does not wait 75 to 110 s (D-052; the "loading model" UI status moved to K1-10) (bd1de6d)
- [x] K1-02 Introduce React shell around the existing engine; Zustand store fed by WebSocket events (D-013). Chat window now; the avatar stays on widget.html until K2 (D-053) (2387abf)
- [x] K1-03 Sidebar: waifu list, history (grouped, search, rename, delete), Settings entry (FR-C-6) (9acb83f; Settings opens nothing until K1-13)
- [x] K1-04 Thread view with streaming, Markdown, copy/regenerate, Stop (FR-C-1, 2, 8, 9, 10) (ba4669b; token counts per message still missing: K1-04b)
- [x] K1-04b Record token counts per message where the backend reports them (FR-C-10) (953b682; Ollama and API counts; llama.cpp only if its stream reports usage; stored, not shown)
- [x] K1-05 Input box and `＋` tray with disabled stubs (FR-C-3, 4); port the heart animation (FR-C-5) (2d5c6c2; Upload file already live)
- [x] K1-05b Screen companions: Task Guide and OCR watch toggles in the `＋` tray and Settings, status chip with one-click stop, refuse to start without a local vision model (FR-SC-1..5, D-048) (9d7ee4d; the Settings switches land with K1-13)
- [x] K1-06 Waifu switcher chip and divider behaviour (FR-S-1, 2) (5097f37)
- [x] K1-07a Ollama/llama.cpp/API discovery for the picker (FR-M-3; D-054) (c2b1832)
- [x] K1-07b Capability registry (FR-M-10): per-model effort data in `config/models.yaml` (user) and `config/models.example.yaml` (shipped); llama.cpp presets stay in `config.yaml` (f69b1f6; D-064 settles D-054's open bullet)
- [x] K1-08 AI Router provider: catalog fetch/cache, SSE streaming, spend ledger, audit, budget cap, redaction (FR-M-4, FR-R-2, 6) (c54a938; D-058)
- [x] K1-08b Generic `openai_compat` provider (base URL plus key; AI Router, OpenRouter, DeepSeek presets); end-user keys in the Windows Credential Manager through the shell (D-037, FR-R-6) (5b04a30; D-059: one endpoint at a time, the user's choice; a custom endpoint is config-only until K1-13)
- [x] K1-09 VRAM manager v1 (NVML), exclusivity across backends, fits hints, load errors (FR-M-3, FR-M-6, ARCHITECTURE §7.3) (d7180b8; D-065; the peer's `vram.py` wired in; TTS and renderer not named residents yet; no *Unload X* button)
- [x] K1-09b *Unload X* on the VRAM refusal card (SPEC §5 "Model fails to load"): the card names the blockers (D-065) but offers only Try again / Switch model; unloading a named Ollama model is `keep_alive: 0` (a5fbe72; D-071: offered only for a model the kernel does not load again at once, not the classifier or the embedding model)
- [x] K1-10 Model chip + popover (search, Local/API sections, badges, footer meters) (FR-M-1, 2, 5, 7); a "loading model" state while the kernel warms or switches models (D-052, D-054) (c2b1832)
- [x] K1-11 Effort slider with animation and reduced-motion fallback (FR-M-8, 9, 11) (f69b1f6; per-model memory in `threads.efforts`; thinking gets `llm.reasoning_tokens` of room; an empty reply is an error, D-064)
- [x] K1-12 Inline API failure UX with Retry / Switch model (FR-R-5) (77c6c00; D-066: a card under the failed turn, plain words per failure kind, the provider's words under Details)
- [x] K1-13 Settings (FR-SET-1, 2), Doctor panel (FR-SET-3), Memory viewer (FR-MEM-4) (3e62a27; D-067: Models, Memory, Doctor, About; read-only but memory)
- [x] K1-13b Editable settings: `settings.json` applied without restart (FR-SET-2), screen-companion switches (K1-05b), custom API endpoint (K1-08b), Ollama URL (0222d2e; D-070: settings.json wins over config.yaml; Ollama on this PC only; screen companions "On now" and "On at start", FR-SC-1)
- [x] K1-14 Tests, `STATE`/`HANDOFF` update (session 4 close docs commit; tests landed with each item: pytest 971, frontend 120, `npm run check` green after b4f17b8)
- [x] K1-B1 Lazy boot (user request, D-060): nothing heavy before the window; llama.cpp only when picked; the kernel owns GPT-SoVITS; Vite ignores runtime folders (9a667ba)
- [x] K1-B2 App icon from the owner's reference, transparent corners (d89c094)
- [x] K1-B3 Voice starts only when it is used: a voice mode switch in the `＋` tray starts GPT-SoVITS and faster-whisper; nothing voice-related at launch (D-061) (2a31515)

### Session 4 plan (R-46, R-50)

The user asked (2026-11-15) for a cleaner, faster kernel than the Yuri copy, a tidy tree, K1 finished and the UI matched to `docs/reference-images/chat-ui.webp`, then: "code still mentions Yuri all the time. fix it. make it a flexible orchestrator, yuri must only be a character." Order, each a separate commit:

- [x] C-1 Tidy the tree: delete the Yuri widget (`widget.html`, `src/*.ts`, `src/style.css`; Yuri's repo stays the reference for K2) once the window speaks v1 only; remove `KASANE/vrm/`, `KASANE/voice_files/`; rename Cargo `yuri` → `kokyu`, `orchestrator.log` → `kernel.log`; drop the tray's API-model and click-through items; folder map in `CLAUDE.md` §4 (D-062) (038ad7e naming, logging, shell; d512ac9 widget and flat protocol gone; `KASANE/voice_files/` stays as `build_premade.py`'s input; `KASANE/vrm/` is C-1b)
- [ ] C-1b Delete `KASANE/vrm/` (user): byte-identical copies of `assets/premade/*/model.vrm` (SHA-256 checked), gitignored, read by nothing; Claude's delete was refused by auto mode
- [x] C-2 Kernel rebuild in place: split `app.py` into `server.py`, `boot.py`, `session.py` (one class per window, a handler per message type), `turns.py`; `logging` instead of `print("[yuri] …")` (R-13); retire the legacy flat protocol and the shadow-mode API toggle (D-049); lazy imports for STT, camera, OCR, pyttsx3; measure boot and first token before and after (D-062: d5da9f8 split, `app.py` kept as the server; 8e4997b Quit waits for the memory pass; `import app` 750 → 615 ms, camera/OCR/pyttsx3 were not on the import path; first token not re-measured)
- [x] K1-15a Heart and rotating thinking lines above the input; threads fill from the bottom (FR-C-5, D-063) (fb804a1)
- [x] K1-15 UI to the reference: frameless window with its own title-bar buttons; top bar (companion chip with avatar, Temp Chat switch); sidebar (logo, New chat, search, groups, Settings gear); composer (attach, mic, round send); model chip under the composer; popover badges (fits, vision, thinking, tools), effort slider, spend footer (b4f17b8, 3d87f72; D-068, D-069 after the user's review; the frameless window itself not seen: needs `npm run tauri dev`)
### Session 4, part 5: the user's review notes (2026-11-15)

"fix the slider, also only load the model that is selected. when selecting other one, unload rest. fix the colors too. add a theme selector …", "fix the core model persona (these are like c.ai characters …)", and the c.ai references.

- [x] Effort slider thumb flew past the track's end (ea67e85; FR-M-8)
- [x] One chat model in memory; the helper roles follow the pick; embeddings stay (c3a65a6; FR-M-6, D-072)
- [x] Settings → Appearance: Kōkyū / Midnight / Light, accent, bubbles with her initial, text size; hard-coded colors follow the theme (89bdb95; D-073)
- [x] **Modes** (Chat, Roleplay) and the persona fix: built as phase K1c below with the assumed answers in D-074 (470a05e docs). Live (Stage + voice per window) waits for K2.

- **Gate K1:** chat with one local and one API model; change model, effort and waifu mid-thread independently; failure UX shown with a forced API error; user sign-off on the layout vs the reference.

## Phase K1c: Conversation modes (D-074; SPEC §2.18)

Started 2026-11-17 with the user's "continue next step"; the six questions in `docs/notes/modes-plan.md` §9 took their recommended answers (D-074), reversible.

- [x] K1c-01 Thread mode and scenario stored (schema 3), `thread_new {mode, scenario}`, mode in thread rows (FR-MODE-1) (b1cd674)
- [x] K1c-02 Prompt layers: persona, mode layer, scenario, shared addendum, tool guidance in Chat only; one builder for every history[0] and the warm-up (FR-MODE-2, 3, 4) (b1cd674; wording 97de53a)
- [x] K1c-03 Roleplay turns: no forget, look intent, Task Guide or tools; profile-only recall; no transcript_log write; refused tool calls; delivery layer while voice is on; raw reply text kept (FR-MODE-3, 4, 8) (d7021f8; Stop drops an unclosed tag 4e698f9)
- [x] K1c-04 Story memory: `story_memory`, the batched local summarizer, injection, Temp Chat rules (FR-MODE-5) (38e5f34, schema 4; review fixes 5a1d972; a log line per fold 2b99262)
- [x] K1c-05 Dialogue-only speech in Roleplay (streaming filter) and captions to match (FR-MODE-8) (cbfe424; review fixes 4e698f9)
- [x] K1c-06 Scenario cards: storage and protocol, the opening message (FR-MODE-6) (b080b2b, schema 5; review fixes 5a1d972)
- [x] K1c-07 Screen companions quiet in roleplay threads (FR-MODE-9) (d7021f8; a remark checked before a thread switch is dropped 4e698f9)
- [x] K1c-08 Client: New roleplay dialog, badge, roleplay renderer, user lines styled, placeholder and empty state (FR-MODE-6, 7) (c9dbf95; review fixes c83f054; New roleplay under New chat 97de53a)
- [x] K1c-09 Persona-only `persona.md` for Luna and Yuri (untracked assets, D-041); SPEC Appendix A rules 3 and 6 (D-074) (no commit: the packs are untracked; SPEC in 470a05e; `waifu.yaml` `prompt: persona.md`, the original `prompt.md` kept)
- [ ] K1c-10 Follow-ups found in review (D-075), none blocking: a reply whose quotes are all U+201D speaks its narration; a screen remark partly spoken is dropped if the thread changes during speech; a story fold cut by the token cap is not detected; a scenario save pending over a disconnect stays "Saving…" until the dialog is reopened; no automated test for Escape during the delete confirm; a fold may start in the gap before `load_thread`'s delayed model request; Temp Chat lines in a roleplay thread may later be folded into the summary; `thread_list` carries full cards on every refresh
- **Gate K1c:** the user starts a roleplay from a card and from blank, talks with voice on and hears only dialogue, checks a chat thread still answers plainly with tools, and confirms or reverses the assumed answers in D-074.

## Phase K1b: Installer walking skeleton (D-035)

Goal: find packaging problems in week one of the product, not the last week.

- [ ] K1b-01 Choose the kernel packaging approach by spike: PyInstaller one-folder vs embedded CPython (size, antivirus behaviour, updateability) (`ARCHITECTURE.md` §11.1)
- [ ] K1b-02 Tauri bundle: NSIS per-user installer, WebView2 bootstrapper, kernel as sidecar or resources, data in `%APPDATA%\Kokyu`
- [ ] K1b-03 Test on a clean Windows machine or VM (no Python, Node, Rust, Git): install, launch, text chat with an API key, uninstall
- [ ] K1b-04 Record antivirus/SmartScreen behaviour, installer size and install time in `STATE.md`
- **Gate K1b:** a clean-machine install reaches a working API chat; findings recorded; packaging approach decided in `DECISIONS.md`.

## Phase K2: Stage and voice

- [ ] K2-01 Stage view: auto-framing, backdrop, spring bones, idle motion, look-at, expression hooks (FR-ST-1..3, 5, 7)
- [ ] K2-02 Lip-sync from played audio; captions; docked input; chat log slide-over; Chat | Stage toggle (FR-ST-3, 4, FR-C-7)
- [ ] K2-03 Sidebar waifu click → Stage, history click → Chat (FR-S-4)
- [ ] K2-04 Speech-safe normalizer, clause pipelining, arbiter, barge-in (FR-V-2..5)
- [ ] K2-05 TTS pre-warm on switch (FR-S-3); TTS-down banner (FR-V-7)
- [ ] K2-05b Voice provider interface; spike a small `builtin` voice (license, quality, CPU latency); make it the default provider (FR-VP-1, 5)
- [ ] K2-05c `elevenlabs` provider: voice ID plus key, cloud badge, opt-in (FR-VP-3)
- [ ] K2-06 STT (faster-whisper CPU), VAD, push-to-talk, mic toggle, live voice (FR-V-6)
- [ ] K2-07 Camera and file attach into the tray; vision helper (FR-C-4, FR-R-3, 4)
- [ ] K2-08 Measure and calibrate latency and fps targets (FR-V-8, FR-ST-6); record in `STATE.md`
- **Gate K2:** alternate two waifus mid-conversation; voice and persona change, no reload; barge-in works; targets measured and recorded.

## Phase K3: Waifu creator

- [ ] K3-01 Form shell with name, slug, validation messages (FR-CR-1)
- [ ] K3-02 VRM upload, validation, live preview, auto-frame (FR-CR-2)
- [ ] K3-03 Voice upload, clip checks, auto-transcript, language detect, Test voice (FR-CR-3)
- [ ] K3-04 Traits chips and instruction block with Copy (FR-CR-4, 5; Appendix A)
- [ ] K3-05 Paste-only prompt box with validation and token count (FR-CR-5, 6)
- [ ] K3-06 Test chat, Save, atomic pack creation, delete flow (FR-CR-7, 8; FR-W-2, 5)
- **Gate K3:** a new waifu created end-to-end with no file touched; she speaks in her own voice.

## Phase W: Component manager and Welcome wizard (release 1.0)

- [ ] W-01 Component interface and states in the kernel; manifests under `components/` (FR-COMP-1, ARCHITECTURE §15)
- [ ] W-02 Ollama: detect, guided install (silent mode tested), model pull with progress
- [ ] W-03 llama.cpp server download and start; STT model download with progress
- [ ] W-04 GPT-SoVITS component from Track T's manifest (advanced, hardware-gated)
- [ ] W-05 Doctor panel as the component UI with plain-language fixes (FR-COMP-4, 5)
- [ ] W-06 Welcome wizard: hardware check, API-key step with Test key, model, voice, companion (premade or create), first conversation (FR-WIZ-1..6)
- [ ] W-07 Premade companions as built-in read-only packs (D-039)
- **Gate W:** on a clean machine, installer to first reply on the API path, measured against FR-WIZ-7; the local path completes with guided installs; every failure shows a plain message.

## Phase K4: Desktop pets (release 1.1)

- [ ] K4-01 Spike: single overlay per monitor with alpha hit-testing vs one window per pet; record result in `DECISIONS.md` (D-014)
- [ ] K4-02 Baker: VRMA clips (idle, sit, walk) or procedural → atlas in `pet/` (FR-P-2)
- [ ] K4-03 Overlay window, sprite player, state machine (FR-P-3, 4)
- [ ] K4-04 Click, drag, quick-reply, speech bubble, right-click menu; speaks through the arbiter (FR-P-5)
- [ ] K4-05 Lifecycle with tray, 1 to 3 pets, overhead measurement (FR-P-1, 6)
- **Gate K4:** two pets idle and walk for an hour; overhead measured; user sign-off.

## Phase K5: 3D mode (release 1.1)

- [ ] K5-01 Port Luna's sandbox into the engine: room, camera, wandering
- [ ] K5-02 Scene pack loader, WASD + pointer lock + colliders, scene switcher (FR-3D-1, 2)
- [ ] K5-03 Apartment and garden scenes within budget (FR-3D-6)
- [ ] K5-04 Bring in one or two waifus; anchors, waypoints, face/approach behaviour; `scene_state` (FR-3D-3)
- [ ] K5-05 Two-waifu turn arbiter with per-speaker prompts (FR-3D-4)
- [ ] K5-06 Voice and text overlay in 3D (FR-3D-5)
- **Gate K5:** walk, switch scene, talk to two waifus with no persona bleed; fps recorded.

## Phase K6: Hardening

- [ ] K6-01 Calibrate all NFR targets and fix misses (SPEC §4)
- [ ] K6-02 Crash recovery and graceful shutdown tests (SPEC §4.2)
- [ ] K6-03 Soak test (several hours, mixed use); log findings
- [ ] K6-04 Docs pass: README quickstart verified from a clean clone
- **Gate K6:** soak test clean; docs verified.

## Phase K7: Release engineering (release 1.0)

- [ ] K7-01 Productionize the K1b packaging; resource resolver for built-in scenes, templates and premade packs; verify with the repo absent
- [ ] K7-02 Code signing for the installer and the kernel; SmartScreen behaviour recorded (Track B-6)
- [ ] K7-03 Updater: signed updates, static manifest, "update available" UX (FR-DIST-7)
- [ ] K7-04 License key verification, per D-032 and the payment provider (FR-DIST-10)
- [ ] K7-05 Export diagnostics (FR-DIST-8)
- [ ] K7-06 `docs/THIRD-PARTY.md` complete including asset rights; SHA-256 checksums; release notes
- [ ] K7-07 GitHub Actions: tagged release builds the Windows installer; clean-VM install test (manual until automated)
- [ ] K7-08 Portable bundle with `setup.ps1` and README setup instructions as a fallback channel
- **Gate K7:** a signed installer from a tagged release installs on a clean machine, passes the wizard, updates to the next tag, and exports diagnostics.

## Deferred

- **D1 Agent mode** (`SCOPE.md` §12): workspace grant, permission levels, diffs, backups, audit, no shell at first.
- **D2 VR:** WebXR spike (WebView2 vs browser page) once a headset is available.

## Backlog (parked, not approved)

- Waifu export/import as a single file
- Selectable stage backdrops and lighting presets
- Collapsible *Thoughts* block for reasoning models
- Emotion detection driving expressions
- Proactive messages / idle behaviours
- Multi-monitor pets
- Auto-update
- Per-waifu private memory (option; contradicts D-005 today)

- `kernel.port` as a config key (the port is the constant `PORT` in `KASANE/app.py`)
- Rename the Cargo package, binary and log file names (`yuri`, `orchestrator.log`) before packaging (K7)
- Persist the last-used companion in `settings.json` instead of `data/active_waifu.txt`
