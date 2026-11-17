> Archived 2026-11-17, frozen. The user answered it the same day; the answers are D-076 to D-085 in docs/DECISIONS.md.

# Refinement proposal (2026-11-17, not approved)

A proposal for the user. Built from a full review of every doc and the frontend: five critics, each verdict checked by a skeptic who tried to refute it, plus a frontend audit and a model-naming design. Nothing here is decided until the user says so; once approved, it becomes DECISIONS entries and the new TODO, and this note is archived.

## 1. Where we really are

- **Code:** K0, K1 and K1c are code-complete. `npm run check` is green (pytest 1209, frontend 140). 13 commits from `470a05e` to `7c16e95` are local, unless the user has pushed them since.
- **Verified:** K1 features were checked live in the browser pane against a scratch kernel, the real Ollama and the real GPU. K1c (modes) was checked only with fakes and with injected UI state.
- **Not verified:** nothing has been used end to end in the desktop window with a real model as a user would. K1c was never run against a real model. The primary 1.0 path (an API key) has never run, because there is no key on the PC. All three manual gates (K0, K1, K1c) are open: 16 unticked items.
- **Honest diagnosis:** we kept adding features (themes, screen companions, modes) on top of open gates. K1c was built on six assumed answers. The "feels like a cheap localhost shell" problem comes from two things: (a) no design system or UI quality bar exists in any doc, and (b) nobody has used the app as a product yet.

## 2. Trash ideas (cut or replace)

| Idea | Where | Why it's bad | Replace with |
|---|---|---|---|
| Paste-only persona box in the creator (typing disabled; copy an instruction to another chatbot, paste the answer back) | D-008, FR-CR-5/6, SCOPE §8 | Hostile to ordinary buyers. You can't fix a typo, and it needs a second AI service when the app already has a model. | An editable box plus **Write it for me**, which runs the instruction through the picked model. "Copy instruction" stays as an extra. |
| Walkable first-person 3D world with two-companion scenes | SCOPE §10, FR-3D, K5 | Authored scenes, colliders, locomotion and a two-speaker arbiter, all fighting the LLM for VRAM. Users pay for the character, voice and stage, not WASD. | **Stage backdrops** (rooms and lighting presets behind the stage camera). One companion per thread, as a rule. |
| Agent mode and VR | SCOPE §12, README, PRODUCT 2.x, ARCH §14 | Off-mission for a companion app, and a liability for non-technical users. There is no headset to build VR with. | One line: "Not planned: agent mode, VR." |
| Productized GPT-SoVITS auto-install by a separate agent (Track T, hashed manifests) | TTS-BACKEND.md, TODO Track T | The hardest component to make reliable. Not started since session 0. | 1.0: "connect your own GPT-SoVITS" (address plus a Doctor check plus a how-to). The **built-in voice** is the real default. |
| Generic component-manager framework (6-method interface, JSON manifests, a wizard state machine) | ARCH §15, FR-COMP-2 | A framework for about 4 things, two of which don't exist. | Grow `doctor.py` into fix actions (open the installer, start, retry). A 3-screen first run: model or key → companion → done. |
| Portable zip plus `setup.ps1` as a second distribution | FR-DIST-1, D-022 | Doubles packaging and support, and breaks the no-terminal promise. *(This was your own call in D-022, so it's yours to drop.)* | The per-user NSIS installer only. |
| Disabled stub controls in the product (the dead mic, "arrives in K2/K3" tooltips) | FR-C-4 | Makes the app look unfinished and leaks developer phase codes. | Show only working controls, and never phase codes in UI text. |
| A spend cap that refuses every unpriced model, on by default | D-058 (open since 11-14) | Blocks DeepSeek and every custom endpoint out of the box for a BYOK user. | Allow them, with a row label like "price unknown, not counted against the cap" and a one-time notice. |
| The process as practised: stacked gates that never gate, 5 living docs rewritten every session (35 of 99 commits are `docs:`), DECISIONS as a 16k-word implementation changelog, session diaries pasted into TODO | CLAUDE.md §2, RULES, TODO, STATE, HANDOFF | It costs a lot and still goes stale (the TODO overview says K1 "Not started"). | See §5. |

## 3. Stale or contradictory (fix)

- **SCOPE.md** is wrong in 7+ places: the companion list in the sidebar, AI Router hard-wired, `.env` keys, the licence "undecided", helpers resident, no modes. CLAUDE.md sends every session to it.
- **README** says "Phase 0 only", demands 12 GB / 32 GB, and calls the installer "later".
- **TODO** overview table: K1 "Not started", no K1c, a done backlog item, auto-update listed twice.
- **ARCHITECTURE:** describes a `models/` package that doesn't exist. §5 is mostly Yuri's retired protocol, while the real v1 messages are barely documented. §7 still has helpers resident (D-072 changed that).
- **SPEC:** rows amended by D-055 to D-075 were never rewritten (FR-M-4/6, FR-R-2, FR-S-4, FR-SET-1/2, §3.3, §5). FR-S-4 still says "click a waifu in the sidebar".
- **DECISIONS:** "Superseded" is defined but used by no entry (about 12 are). Yuri's IDs leaked in (D-072 cites "D-015" for local memory; Kōkyū's D-015 is the licence).
- **CLAUDE.md:** "delivery by git bundle" (D-030) and Yuri's ports. HANDOFF contradicts itself on the preview port.
- **modes-plan.md** still says "proposal, nothing built".
- **Assets in git:** D-041 says premade packs are committable, CLAUDE.md says `.vrm`/`.wav` never are, and today they are neither ignored nor tracked, so `git add -A` would commit them. The `persona.md` drafts (product content) have no version control.

## 4. Missing (needs a decision)

1. **A design and UX quality bar.** No doc defines what "a proper chatbot app" means. This is the root of the shell feeling.
2. **The voice story for a 1.0 buyer.** Luna's and Yuri's voices exist only as GPT-SoVITS reference clips, so on the API path with the built-in voice they won't sound like themselves.
3. **Content stance and payment fit.** Both premade personas carry explicit sexual instructions, the roleplay mode is new, and whether Dodo accepts companion or adult content is unverified (PRODUCT §5). This needs one decision (premade content, age gate) before any commerce work. It's an hour of reading, not code.
4. **An API key to test with** (a few dollars on OpenRouter or DeepSeek). The K1 and K1b gates both need one, and no task says so.
5. **A face for the companion.** Every avatar is a letter, and in the default style even that is hidden. The VRM files already carry a thumbnail.

## 5. Keep (genuinely good)

- The invariants: a companion is a voice and a persona; one model entry point; local-only captures; no silent fallback. They are tested in code.
- PRODUCT §3's honest buyer analysis: most buyers have no 12 GB card, and the API key is itself a wall.
- Modes design: per thread, layered prompts, fiction never reaches memory.
- Desktop pets as sprites baked from the VRM (cheap on the GPU).
- Shared memory with the viewer and Temp Chat.
- The early installer walking skeleton (later than planned).
- STATE's verified / not-verified honesty, and the traps list.

## 6. The refined plan

**R0. Docs reset (one session, Claude).**
- **SCOPE** becomes a real one-pager (about 90 lines): the product, the invariants, the differentiators, the **cut list**, the release train.
- **PRODUCT** is trimmed to about 90 lines, with the content and payment question at the top of its open list.
- **SPEC v1.1:** amended rows rewritten in place with the D-ID, a 5-line changelog, the 1.1+ features moved to a short appendix, and new rows for chat polish and model naming.
- **ARCHITECTURE** comes to about 200 lines: real modules, a real protocol table, no Yuri history, no changelog prose.
- **DECISIONS:**
  - an index at the top with three parts: in force (one line each), open questions, and superseded (pointing to the successor);
  - the full log moves unchanged to `docs/decisions/log.md`;
  - new entries are about 150 words.
- **STATE** shrinks to about 80 lines and gains one verification column with three levels: tests / seen with injected state / end to end in the desktop app with a real model.
- **TODO** is a forward plan of about 120 lines; finished phases become one line each with a commit range.
- **HANDOFF** shrinks to about 40 lines.
- **New docs/DESIGN.md:** tokens, type scale, motion, required states, copy rules, the model-naming rule.
- **Archive** the vision handoff, modes-plan, yuri-inventory and the TTS brief under `docs/notes/archive/`.
- **Process:** docs are updated once per session; one real gate per phase; the autonomous mode is written down honestly (take the recommended answer, mark it ASSUMED, keep it reversible, never start a new phase).

**R1. Dogfood checkpoint (with you, about an hour).** `npm run tauri dev` with the local 9B, plus one cheap API model. Six checks: the window, a chat, a roleplay, voice on and off, a forced failure, a companion switch. Fix what it finds before anything new. This one gate replaces the three stacked ones.

**UI-1. Chat app polish (before K1b).** One commit-sized package each, with screenshots at 900×600 and 1440×900 in every theme:
1. **Foundation:**
   - tokens (surfaces, text, accent, focus);
   - a type scale with nothing under 12 px (today there are 11 sizes, down to 9 px);
   - a 4 px spacing scale;
   - one bundled UI font;
   - visible focus rings;
   - no white flash at startup;
   - no developer words in the UI ("Kernel offline", "K2", the permanent Enter hint).
2. **Model names (your request):** see §7, together with a real tooltip component and one icon set replacing the emoji glyphs (✎ 🗑 ▾ ↻).
3. **Companion portrait:** taken from the VRM thumbnail, used in the chip, the sidebar and the messages.
4. **Message list:**
   - grouped by speaker;
   - a hover action bar with icons;
   - time and model on hover;
   - the view stops yanking to the bottom while you read;
   - a jump-to-latest pill;
   - the thinking state where the reply will appear;
   - a streaming caret;
   - edit and resend of your last message.
5. **Markdown:** tables, nested lists, syntax-highlighted code with a header and copy.
6. **Shell:**
   - one slim header (portrait chip, thread title, Temp toggle, window buttons);
   - a split New button (Chat / Roleplay…);
   - a context menu and pinning in the sidebar;
   - an empty state with her face, a greeting and starter chips;
   - toasts;
   - in-app confirms instead of `window.confirm`.
7. **Keyboard:** Ctrl+N, Ctrl+K palette, Ctrl+comma, Esc to stop.

New dependencies, each with a DECISIONS entry and THIRD-PARTY line:
- **Radix primitives** (unstyled: tooltip, popover, dialog, menus; they fix the focus and escape handling the hand-rolled popovers get wrong);
- **lucide-react** icons;
- one OFL font;
- a small lazy-loaded syntax highlighter.

**Then:** K1b installer skeleton, time-boxed to about 2 sessions → K2 stage and voice (decide the 1.0 voice first) → K3 creator (with Write it for me) → W first run (3 screens) → K6/K7. Release 1.1: pets and stage backdrops.

## 7. Model short names (design)

- **Computed in the kernel** (a new pure module, `router/names.py`), so the chip, the picker, the loading card, the VRAM messages and "Sent to" all say the same thing.
  - Clients hold no business logic, so the client's own `shortRef` regex goes.
  - Rows keep `label` (now the short name) and gain `full` (the exact id) and `facts` (backend, quant, parameters, file size, context, price, date).
- **The rule, in order:**
  1. A `names:` override in `models.yaml` wins.
  2. Else a llama.cpp preset label, minus its "(…)" part.
  3. Else the name is derived from the id:
     - strip `hf.co/<org>/`, `-GGUF` and the `Vendor_` duplicate;
     - move quant tags, dates, "instruct" and context sizes into the details;
     - uppercase the size (9B, 35B-A3B);
     - format versions (5-5 → 5.5);
     - title-case known families (Qwen, Llama, DeepSeek, GPT, Gemini, Claude…);
     - the API vendor becomes the group header (Anthropic, Meta, xAI), never part of the name.

  If two rows in one section get the same name, the quant is appended.
- **Hover:**
  - On the chip, a styled tooltip on hover or keyboard focus.
  - In the picker, a muted detail strip for the row under the pointer (rows scroll, and keyboard focus stays in the search box, so per-row tooltips would clip).
  - Both show the full id in muted monospace, and the details on a second muted line.

| Full | Short |
|---|---|
| `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L` | Qwen3.5 9B (Q6_K_L, since it collides with the next) |
| `qwen3.5:9b` | Qwen3.5 9B (Q4_K_M) |
| `qwen3.5:4b` | Qwen3.5 4B |
| llama.cpp `Qwen3.6-35B-A3B UD-Q4_K_XL` | Qwen3.6 35B-A3B |
| `anthropic/claude-sonnet-5-5` | Claude Sonnet 5.5 (group Anthropic) |
| `deepseek/deepseek-v4-chat` | DeepSeek V4 Chat |
| `openai/gpt-5.5-mini` | GPT-5.5 Mini |
| `google/gemini-3-pro` | Gemini 3 Pro |
| `meta-llama/llama-4-scout` | Llama 4 Scout (group Meta) |
| `anthropic/claude-3-5-sonnet-20241022` | Claude 3.5 Sonnet (date on hover) |
| `gemma3:27b-it-qat` | Gemma 3 27B (QAT on hover) |
| `mistral-small:24b` | Mistral Small 24B |

Tests: one pytest row per example, plus the collision case, the override, and an unparseable id (returned unchanged, never empty). Risk: odd new model names come out imperfect. The full id is always one hover away, and the override fixes any single model.
