> Archived 2026-11-17, frozen. Superseded by `docs/SPEC.md` (FR-MODE-1..10), D-074, D-075 and `docs/ARCHITECTURE.md` §4; kept for history.

# Modes plan: Chat, Roleplay and Live (proposal, not approved)

- **Status:** draft for the user's review, 2026-11-15 (session 4). Nothing here is built.
- **Asked for:** "we should make modes … brainstorm and come up with a plausible plan." Also "fix the core model persona (these are like c.ai characters …)" and "asterisk quoted words are an action so italic. double asterisk means bold. brackets are parenthesis".
- **Needs before code:** the user's answers to §9, new SPEC requirements (FR-MODE-*), a DECISIONS entry, and a TODO phase.

## 1. The idea in one paragraph

Two separate choices, not one list of three modes:

- **What kind of conversation** this thread is: **Chat** or **Roleplay**. Chosen when the thread starts, kept with the thread.
- **How you are with her** right now: **text**, or **Live** (her avatar on the Stage and her voice, K2). A window setting you turn on and off at any time, in any thread.

Your "VR mode" is Live. Live works in both kinds of thread, which answers your last question: to see her avatar in a normal chat, open a Chat thread and go Live. To play a story with her avatar, open a Roleplay thread and go Live.

|                | Text                                        | Live (Stage + voice)                                         |
|----------------|---------------------------------------------|--------------------------------------------------------------|
| **Chat**       | ChatGPT-like: plain, short, tools, your memory | Her avatar talks to you in short spoken lines; tools still work |
| **Roleplay**   | c.ai-like: `*actions*`, dialogue, the story's memory | She speaks only her dialogue; her actions move the avatar      |

Waifu invariance holds (RULES §3.1): a mode belongs to the **thread**, never to a companion. Luna and Yuri both do Chat, Roleplay and Live, with the same model, tools and permissions.

## 2. Chat (default)

- **For:** talking, questions, work. She is still herself (her name, personality, way of talking), never "an AI assistant", but she answers plainly.
- **Length:** 3 to 4 lines. Longer only when the task needs it (code, a list, steps you asked for).
- **Format:** Markdown when it helps (lists, code, bold). No `*action*` narration.
- **Memory:** the app memory you already have (your facts, preferences, what you told her), read and written as today (K1-14, FR-MEM-*).
- **Tools:** on, as today (screen, camera, clipboard; more later). She behaves like an agent when a tool is offered.

## 3. Roleplay

- **For:** stories and scenes, like c.ai. She stays in character and writes in the c.ai format:
  - `*she glances up from her book*` an action or narration, shown *italic and softer*;
  - plain or `"quoted"` text is her dialogue, shown normally;
  - `**word**` is emphasis, shown **bold**;
  - `(OOC: …)` or `((…))` is out of character, shown small and muted. You can write it too, to steer the story.
- **Length:** a paragraph or two, like a reply on c.ai; a setting can make it shorter or longer.
- **Starting one:** *New chat* gets a second choice, *New roleplay…*, which opens a scenario card:
  - title, setting, who you are, who she is to you, how the scene opens;
  - her opening message (the c.ai greeting), written by you or by her from the card;
  - optional rules ("slow burn", "no time skips").
  - Saved cards can be started again; *Blank roleplay* skips the card.
- **Memory:**
  - **Story memory**, kept with that roleplay only: a running summary, what happened, who is who, where things stand. It is fed back on every turn, so a long story does not forget its start.
  - She reads your name and basic profile from app memory, but **nothing from a story is written into app memory**: fiction never becomes "facts about you".
  - The memory writer stays local (D-015), and Temp Chat (FR-MEM-5) works the same.
- **Tools:** off by default, for immersion. Open question §9.3.

## 4. Live (the Stage with voice; your "VR mode")

- Turned on per window, in any thread. It needs K2 (Stage, voice in, voice out), so it lands with K2.
- **In a Chat thread:** she answers in 1 to 3 short spoken sentences. The prompt gains a speech layer: no lists, no Markdown, no symbols, no quotes or dashes, no "you're"-style contractions GPT-SoVITS stumbles on, numbers in words.
- **In a Roleplay thread:** she keeps writing actions and dialogue, so the transcript stays a story, but:
  - the voice reads **only her dialogue**: `*actions*`, `(OOC)` and narration are cut before TTS, by code, not by asking the model;
  - her actions drive the avatar: `*smiles*`, `*tilts her head*` map to expressions and gestures (the emotion tag already does part of this);
  - a setting, *Read narration aloud*, is off by default; it can be turned on with a narrator voice later.
- This matches your idea of a "live chat where her format is deactivated", without losing the story's text. If Live in Roleplay feels wrong in practice, it can fall back to your simpler rule: Roleplay text has no voice.

## 5. How her prompt is built (the persona fix)

Today the system prompt is the pack's `prompt.md` (which mixes personality with TTS rules: no Markdown, 1 to 2 sentences, no dashes) plus `APP_ADDENDUM`. That is why she is short and flat everywhere, even in text. It becomes three layers:

1. **Persona** (the pack's `prompt.md`, rewritten to hold only who she is): identity, personality, how she talks, likes, history, relationship to you. No format or length rules. This is the "c.ai character card", the same in every mode.
2. **Mode layer** (one per mode, written once for every companion): Chat or Roleplay rules from §2 and §3, plus the roleplay scenario card and story summary when there is one.
3. **Delivery layer** (only while Live): the spoken-line rules from §4.

`APP_ADDENDUM` (emotion tag, honesty about abilities, tool guidance) stays, with the tool guidance only in modes with tools. The pack prompts are your assets (untracked, from the Luna and Yuri repos): I would draft the persona-only rewrite and you approve it.

## 6. Making speech safe by code, not only by prompt

`audio/speech.py` already strips Markdown, parentheses, quotes and dashes. It gains:

- a **mode-aware cut**: in Roleplay, keep only dialogue (drop `*…*` spans, `(OOC …)`, `((…))`, and narration outside quotes when the reply uses quotes for dialogue);
- a last check that nothing GPT-SoVITS chokes on reaches the TTS, whatever the model wrote. The prompt rules make lines sound natural; the code makes them safe.

## 7. Screen and memory details

- **Thread data:** `threads.mode` (`chat` | `roleplay`), `threads.scenario` (the card as JSON), story memory in its own table keyed by thread. Old threads are Chat.
- **Protocol v1 additions:** `thread_new {mode, scenario?}`; `thread_updated` carries `mode`; the scenario list and save messages; `live_mode {on}` with K2.
- **Sidebar:** a small mark on roleplay threads; search covers both.
- **Renderer:** the c.ai styling (§3) applies in Roleplay threads only. In Chat, `*x*` stays ordinary italic and parentheses stay plain text, so "install it (with pip)" is not greyed out.

## 8. Order of work (suggested)

1. **M1 Prompt layers and Chat mode:** the three layers, persona-only pack prompts (your approval), Chat rules, the speech cut. Small; it fixes the "flat persona" at once.
2. **M2 Roleplay:** the thread mode, New roleplay with scenario cards, story memory, the c.ai renderer, tools off.
3. **M3 Live:** with K2 (Stage + voice): the delivery layer, dialogue-only voice, actions to expressions.

M1 and M2 could be a phase **K1c Modes** after the K1 gate, before or after K1b (installer). M3 is part of K2. Your call.

## 9. Questions for you

1. **Is a thread's mode fixed when it starts?** Recommended: yes. Switching mid-thread mixes app memory with story memory. *Continue as roleplay* can start a new roleplay from a chat later.
2. **Chat length:** 3 to 4 lines, longer only when the task needs it (code, steps)? Or a hard 3 to 4 lines always?
3. **Tools in Roleplay:** off (recommended), or on (she could look at your screen mid-story)?
4. **Voice in Roleplay:** dialogue-only (recommended), or no voice at all in Roleplay as you first suggested?
5. **Opening messages:** should each companion ship with a few premade scenario cards (content, like her prompt), or only cards you write?
6. **Pack prompts:** may I draft persona-only rewrites of Luna's and Yuri's `prompt.md` for you to approve?
