import { test } from "node:test";
import assert from "node:assert/strict";

import {
  barNotice,
  canRegenerate,
  canSend,
  canStartThread,
  currentMode,
  editableKey,
  fromStored,
  MAX_TOASTS,
  initialState,
  lastExchange,
  reduce,
  startsGroup,
  turnFailure,
  visibleStream,
} from "../src/app/chat-state.ts";
import { backoffMs, dispatchRaw } from "../src/net/kernel.ts";
import { NOT_CONNECTED } from "../src/net/protocol.ts";

// K1-02: the chat window's behaviour, driven by kernel frames as they arrive.

const frame = (type, data, thread = "t1") => ({ kind: "frame", frame: { v: 1, type, id: "s1", thread, data } });
const thread = (id, extra = {}) => ({
  id,
  title: id,
  created_at: 1,
  updated_at: 1,
  active_waifu_id: null,
  model_ref: null,
  effort: null,
  temp: false,
  archived: false,
  mode: "chat", // FR-MODE-1: what the kernel sends for a chat thread
  scenario: {},
  ...extra,
});
const stored = (id, role, content, meta = {}) => ({
  id,
  thread_id: "t1",
  ts: 1,
  role,
  content,
  speaker_waifu_id: null,
  speaker_name: role === "assistant" ? "Yuri" : null,
  model_ref: null,
  effort: null,
  tokens_in: null,
  tokens_out: null,
  meta,
});
const run = (...events) => events.reduce(reduce, initialState);
const online = { kind: "status", status: "online" };

test("opening a thread shows its saved messages, including a stopped reply and a divider", () => {
  const s = run(
    online,
    frame("thread_opened", {
      thread: thread("t1"),
      messages: [stored(1, "user", "hi"), stored(2, "assistant", "hel", { stopped: true }), stored(3, "divider", "Luna joined")],
    }),
  );
  assert.equal(s.thread.id, "t1");
  assert.deepEqual(
    s.messages.map((m) => [m.role, m.text, m.stopped ?? false]),
    [["user", "hi", false], ["assistant", "hel", true], ["divider", "Luna joined", false]],
  );
});

test("a turn streams token by token, hides the emotion tag, then lands as one message", () => {
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, { kind: "sent", text: "hello" });
  assert.equal(s.turn, "thinking");
  assert.equal(canSend(s), false); // one turn at a time
  assert.equal(s.messages.at(-1).pending, true);

  s = reduce(s, frame("turn_start", { user_text: "hello" }));
  assert.equal(s.messages.length, 1); // the optimistic line is confirmed, not duplicated
  assert.equal(s.messages[0].pending, false);

  s = reduce(s, frame("token", { text: "Hi there " }));
  s = reduce(s, frame("token", { text: "[hap" }));
  assert.equal(s.turn, "replying");
  assert.equal(visibleStream(s), "Hi there"); // half-written tag hidden

  s = reduce(s, frame("turn_done", { text: "Hi there", stopped: false }));
  assert.equal(s.turn, "idle");
  assert.equal(s.streamRaw, "");
  assert.deepEqual(s.messages.map((m) => [m.role, m.text]), [["user", "hello"], ["assistant", "Hi there"]]);
  assert.equal(canSend(s), true);
});

test("Stop keeps the partial reply, marked as stopped", () => {
  let s = run(online, frame("turn_start", { user_text: "tell me a story" }), frame("token", { text: "Once upon" }));
  s = reduce(s, frame("turn_done", { text: "Once upon", stopped: true }));
  assert.equal(s.messages.at(-1).text, "Once upon");
  assert.equal(s.messages.at(-1).stopped, true);
});

test("an empty turn_done keeps the streamed text as the reply", () => {
  let s = run(online, frame("turn_start", { user_text: "x" }), frame("token", { text: "par" }));
  s = reduce(s, frame("turn_done", { text: "", stopped: true }));
  assert.equal(s.turn, "idle");
  assert.equal(s.messages.at(-1).text, "par");
});

test("a failed model is shown with Retry and Switch model, never silently swapped", () => {
  let s = run(online, { kind: "sent", text: "hi" }, frame("turn_start", { user_text: "hi" }));
  s = reduce(
    s,
    frame("error", {
      code: "model_failed",
      message: "The chosen model failed (timeout). Retry, or switch model.",
      reply_to: null,
      actions: ["retry", "switch_model"],
    }),
  );
  s = reduce(s, frame("turn_done", { text: "", stopped: false }));
  assert.deepEqual(s.notice.actions, ["retry", "switch_model"]);
  // K1-12, FR-R-5: inline on the turn, not in the bar
  assert.equal(turnFailure(s), s.notice);
  assert.equal(barNotice(s), null);
  assert.equal(s.messages.at(-1).failed, true);
  assert.equal(s.messages.filter((m) => m.role === "assistant").length, 0); // no fake reply

  // Retry: the kernel runs the exchange again; the line is confirmed, not duplicated
  s = reduce(s, { kind: "regenerating" });
  assert.equal(s.notice, null);
  assert.deepEqual(s.messages.map((m) => [m.role, m.text, m.pending, m.failed]), [["user", "hi", true, false]]);
  s = reduce(s, frame("turn_start", { user_text: "hi" }));
  s = reduce(s, frame("turn_done", { text: "hello", stopped: false }));
  assert.deepEqual(s.messages.map((m) => [m.role, m.text]), [["user", "hi"], ["assistant", "hello"]]);

  // Regenerate: the reply is replaced, the user line stays once
  s = reduce(s, { kind: "regenerating" });
  assert.equal(s.turn, "thinking");
  s = reduce(s, frame("turn_start", { user_text: "hi" }));
  s = reduce(s, frame("turn_done", { text: "hello again", stopped: false }));
  assert.deepEqual(s.messages.map((m) => [m.role, m.text]), [["user", "hi"], ["assistant", "hello again"]]);
});

test("an API failure keeps the provider's words for Details; a refused send stays in the bar", () => {
  // K1-12, FR-R-5
  let s = run(online, { kind: "sent", text: "hi" }, frame("turn_start", { user_text: "hi" }));
  s = reduce(
    s,
    frame("error", {
      code: "model_failed",
      reason: "RATE_LIMIT",
      message: "The provider is limiting requests right now. Retry, or switch model.",
      detail: "429 from https://api.example/v1/chat/completions: 'slow down'",
      reply_to: null,
      actions: ["retry", "switch_model"],
    }),
  );
  assert.equal(turnFailure(s).detail, "429 from https://api.example/v1/chat/completions: 'slow down'");
  s = reduce(s, frame("error", { code: "turn_running", message: "Wait for the reply to finish.", reply_to: null }));
  assert.equal(turnFailure(s), null);
  assert.equal(barNotice(s).text, "Wait for the reply to finish.");
  assert.equal(barNotice(reduce(s, { kind: "dismiss_notice" })), null);
});

test("Regenerate skips a trailing divider and puts the old reply back when nothing comes (review findings)", () => {
  const opened = run(
    online,
    frame("thread_opened", {
      thread: thread("t1"),
      messages: [stored(1, "user", "hi"), stored(2, "assistant", "hello"), stored(3, "divider", "Switched to Luna")],
    }),
  );
  assert.deepEqual(lastExchange(opened.messages), [0, 1]);
  assert.equal(lastExchange([]), null);

  let s = reduce(opened, { kind: "regenerating" });
  assert.deepEqual(s.messages.map((m) => [m.role, m.text]), [["divider", "Switched to Luna"], ["user", "hi"]]);
  s = reduce(s, frame("error", { code: "vision_unavailable", message: "No vision", reply_to: null }));
  assert.equal(s.turn, "thinking"); // not about this turn
  s = reduce(s, frame("turn_start", { user_text: "hi" }));
  s = reduce(s, frame("turn_done", { text: "", stopped: true })); // stopped before a word
  assert.equal(s.messages, opened.messages);
  assert.equal(s.turn, "idle");
});

test("turn_running while busy does not end the turn; other errors show a notice", () => {
  let s = run(online, frame("turn_start", { user_text: "a" }));
  s = reduce(s, frame("error", { code: "turn_running", message: "Wait", reply_to: null }, null));
  assert.equal(s.turn, "thinking");
  assert.equal(s.notice.text, "Wait");
});

test("the unpriced-model notice is shown and the reply goes on (D-083)", () => {
  let s = run(online, frame("turn_start", { user_text: "a" }));
  s = reduce(s, frame("error", { code: "price_unknown", message: "No listed price.", reply_to: null }, null));
  assert.equal(s.turn, "thinking");
  assert.equal(s.notice.text, "No listed price.");
});

test("frames for another thread are ignored; the list stays sorted and hides archived threads", () => {
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, frame("token", { text: "stray" }, "t2"));
  assert.equal(s.streamRaw, "");
  s = reduce(
    s,
    frame(
      "thread_list",
      { query: "", threads: [thread("old", { updated_at: 1 }), thread("gone", { archived: true }), thread("t1", { updated_at: 5 })] },
      null,
    ),
  );
  assert.deepEqual(s.threads.map((t) => t.id), ["old", "t1"]);
  // the open thread picks up its new title from the list (found live: the header kept "New chat")
  s = reduce(s, frame("thread_list", { query: "", threads: [thread("t1", { title: "Hi! I just got home" })] }, null));
  assert.equal(s.thread.title, "Hi! I just got home");
  s = reduce(
    s,
    frame(
      "thread_list",
      { query: "", threads: [thread("old", { updated_at: 1 }), thread("gone", { archived: true }), thread("t1", { updated_at: 5 })] },
      null,
    ),
  );
  s = reduce(s, frame("thread_updated", { thread: thread("old", { updated_at: 9, title: "renamed" }) }, "old"));
  assert.deepEqual(s.threads.map((t) => [t.id, t.title]), [["old", "renamed"], ["t1", "t1"]]);
  // search results are not the history list
  const searched = reduce(s, frame("thread_list", { query: "tea", threads: [] }, null));
  assert.equal(searched.threads.length, 2);
});

test("search hits older than the history list stay; Regenerate needs a saved thread (review findings)", () => {
  let s = run(online, frame("thread_list", { query: "tea", threads: [thread("ancient", { title: "tea", updated_at: 0 })] }, null));
  s = reduce(s, frame("thread_list", { query: "", threads: [thread("t1", { updated_at: 5 })] }, null));
  assert.deepEqual(s.search.threads.map((t) => t.id), ["ancient"]);
  // no thread store: the kernel would refuse, so the button is not offered
  s = run(online, { kind: "sent", text: "hi" }, frame("turn_done", { text: "hey", stopped: false }, null));
  assert.equal(canRegenerate(s), false);
  s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [stored(1, "user", "hi"), stored(2, "assistant", "hey")] }));
  assert.equal(canRegenerate(s), true);
});

test("her portrait stamp reaches the roster, and replies remember who spoke (D-091)", () => {
  let s = run(
    online,
    frame("waifu_state", { active: "luna", waifus: [{ id: "luna", name: "Luna", portrait: "m1-2" }], problems: [], pending: null }, null),
  );
  assert.equal(s.companion.portrait, "m1-2");
  assert.equal(fromStored({ ...stored(1, "assistant", "hi"), speaker_waifu_id: "luna" }).speakerId, "luna");
  s = reduce(s, frame("turn_start", { user_text: "a" }));
  s = reduce(s, frame("token", { text: "hello [happy]" }));
  s = reduce(s, frame("turn_done", {}));
  assert.equal(s.messages.at(-1).speakerId, "luna");
});

test("a new picture refreshes the roster; who is active and who comes next stay (D-091)", () => {
  const luna = { id: "luna", name: "Luna", portrait: "m1", traits: ["blunt"], about: "Blunt." };
  const yuri = { id: "yuri", name: "Yuri", portrait: "m2" };
  let s = run(online, frame("waifu_state", { active: "luna", waifus: [luna, yuri], problems: [], pending: "yuri" }, null));
  assert.equal(s.pendingCompanion.id, "yuri");
  s = reduce(s, frame("waifu_roster", { waifus: [{ ...luna, portrait: "c9", portrait_chosen: true }, yuri] }, null));
  assert.equal(s.companion.portrait, "c9");
  assert.equal(s.companion.portraitChosen, true);
  assert.deepEqual(s.companion.traits, ["blunt"]);
  assert.equal(s.companion.about, "Blunt.");
  assert.equal(s.pendingCompanion.id, "yuri");
});

test("her profile opens and closes; an unreadable picture does not end a reply (D-091)", () => {
  let s = run(online, { kind: "profile", id: "luna" });
  assert.equal(s.profile, "luna");
  s = reduce(s, { kind: "profile", id: null });
  assert.equal(s.profile, null);
  s = reduce(s, frame("turn_start", { user_text: "a" }));
  s = reduce(s, frame("error", { code: "picture_unreadable", message: "Not a picture.", reply_to: null }, null));
  assert.equal(s.turn, "thinking");
  assert.equal(s.notice.text, "Not a picture.");
});

// UI1-07: the message list

test("a run of messages from one voice starts one group; a divider or another speaker starts a new one", () => {
  const her = (key, id) => ({ key, role: "assistant", text: key, speaker: id, speakerId: id });
  const me = (key) => ({ key, role: "user", text: key, speaker: null });
  const list = [me("a"), me("b"), her("c", "luna"), her("d", "luna"), her("e", "yuri"), { key: "f", role: "divider", text: "", speaker: null }, her("g", "yuri")];
  assert.deepEqual(list.map((_, i) => startsGroup(list, i)), [true, false, true, false, true, true, true]);
});

test("saved messages keep their time, a reply its model, and a file line says it is one", () => {
  const s = run(
    online,
    frame("thread_opened", {
      thread: thread("t1"),
      messages: [
        { ...stored(1, "user", "(shared a file) milk", { attachment: "text" }), ts: 100 },
        { ...stored(2, "assistant", "ok"), model_ref: "ollama:gemma3" },
      ],
    }),
  );
  assert.deepEqual(
    s.messages.map((m) => [m.ts, m.model ?? null, m.file ?? false]),
    [[100, null, true], [1, "ollama:gemma3", false]],
  );
  assert.equal(editableKey(s), null); // a file line is the engine's words: no Edit
});

test("a live reply gets a time and the thread's model; Edit sits on the last line (D-092)", () => {
  let s = run(online, frame("hello", { default_model_ref: "ollama:qwen" }), frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, { kind: "sent", text: "hi" });
  s = reduce(s, frame("turn_start", { user_text: "hi", file: false }));
  s = reduce(s, frame("turn_done", { text: "hello", stopped: false }));
  const [line, reply] = s.messages;
  assert.equal(typeof line.ts, "number");
  assert.equal(reply.model, "ollama:qwen");
  assert.equal(editableKey(s), line.key);
  assert.equal(editableKey(reduce(s, { kind: "sent", text: "more" })), null); // not while a turn runs
});

test("an edited resend replaces the last line's words and waits for the kernel (D-092)", () => {
  let s = run(
    online,
    frame("thread_opened", { thread: thread("t1"), messages: [stored(1, "user", "helo"), stored(2, "assistant", "hm?")] }),
  );
  s = reduce(s, { kind: "regenerating", text: "hello" });
  assert.deepEqual(s.messages.map((m) => [m.role, m.text, m.pending ?? false]), [["user", "hello", true]]);
  s = reduce(s, frame("turn_start", { user_text: "hello" }));
  assert.equal(s.messages.length, 1);
  assert.equal(s.messages[0].pending, false);
  // nothing came back: the old exchange returns, typo and all
  s = reduce(s, frame("turn_done", { text: "", stopped: false }));
  assert.deepEqual(s.messages.map((m) => m.text), ["helo", "hm?"]);
});

test("a file line from turn_start cannot be edited", () => {
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, { kind: "sent", text: null });
  s = reduce(s, frame("turn_start", { user_text: "(shared a file) milk", file: true }));
  s = reduce(s, frame("turn_done", { text: "ok", stopped: false }));
  assert.equal(s.messages[0].file, true);
  assert.equal(editableKey(s), null);
});

test("companion name, observer role and a lost connection", () => {
  let s = run(
    online,
    frame("waifu_state", { active: "yuri", waifus: [{ id: "yuri", name: "Yuri" }], problems: [], pending: null }, null),
  );
  assert.deepEqual(s.companion, { id: "yuri", name: "Yuri", portrait: null, traits: [], about: null, portraitChosen: false, pet: null, petPoses: [], petOwn: false });
  s = reduce(s, frame("surface_status", { role: "observer" }, null));
  assert.equal(canSend(s), false);
  s = reduce(s, frame("surface_status", { role: "driver" }, null));
  s = reduce(s, frame("turn_start", { user_text: "x" }));
  s = reduce(s, { kind: "status", status: "offline" });
  assert.equal(s.turn, "idle");
  assert.equal(canSend(s), false);
});

test("the socket passes v1 frames on and reports anything else as a problem (D-062)", () => {
  const seen = [];
  const h = {
    onFrame: (f) => seen.push(["frame", f.type]),
    onStatus: () => {},
    onProblem: (r) => seen.push(["problem", r]),
  };
  dispatchRaw(JSON.stringify({ v: 1, type: "token", id: "a", thread: "t", data: { text: "x" } }), h);
  dispatchRaw(JSON.stringify({ type: "speak", text: "x", audio_b64: "", mime: "audio/wav" }), h);
  dispatchRaw(JSON.stringify({ v: 2, type: "token", id: "a", thread: "t", data: {} }), h);
  dispatchRaw("not json", h);
  assert.deepEqual(seen.map((x) => x[0]), ["frame", "problem", "problem", "problem"]);
  assert.deepEqual([0, 1, 2, 3, 9].map(backoffMs), [250, 500, 1000, 2000, 2000]);
});

test("a file send waits for the kernel's wording of the line (K1-05, FR-C-3)", () => {
  let s = run(online, { kind: "sent", text: null });
  assert.equal(s.turn, "thinking");
  assert.equal(s.messages.length, 0); // no guessed line: the kernel words it ("shared an image…")
  s = reduce(s, frame("turn_start", { user_text: '(shared an image, "cat.png") A cat on a desk.\n\nlook' }));
  assert.deepEqual(s.messages.map((m) => [m.role, m.pending ?? false]), [["user", false]]);
  assert.equal(s.messages[0].sentTo, undefined); // a local model: nothing left the PC
  // FR-R-7: an attachment that went to an API model says so, live and when reopened
  const api = "api:airouter/deepseek/deepseek-v4-flash";
  s = reduce(run(online, { kind: "sent", text: null }), frame("turn_start", { user_text: "(shared a file)", sent_to: api }));
  assert.equal(s.messages[0].sentTo, api);
  s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [stored(1, "user", "(shared a file)", { sent_to: api })] }));
  assert.equal(s.messages[0].sentTo, api);
  // the vision step failed: the kernel's notice, then an empty turn_done, close the turn without a line
  s = run(online, { kind: "sent", text: null }, frame("error", { code: "vision_unavailable", message: "Couldn't look", reply_to: null }, null));
  assert.equal(s.turn, "thinking");
  s = reduce(s, frame("turn_done", { text: "", stopped: false }, null));
  assert.equal(s.turn, "idle");
  assert.equal(s.messages.length, 0);
  assert.equal(s.notice.text, "Couldn't look");
});

test("the screen companions' state comes from the kernel and goes on disconnect (K1-05b)", () => {
  let s = run(online, frame("screen_companions", { task_guide: { on: true, task: "essay" }, ocr_watch: { on: false } }, null));
  assert.equal(s.screen.task_guide.task, "essay");
  s = reduce(s, { kind: "status", status: "offline" });
  assert.equal(s.screen, null); // a restarted kernel starts with both off (FR-SC-1)
});


test("Settings opens on a section and keeps the Doctor's and memory's last answers", () => {
  // K1-13 (FR-SET-3, FR-MEM-4)
  let s = run(online);
  assert.equal(s.settings, null);
  s = reduce(s, { kind: "picker", open: true });
  s = reduce(s, { kind: "settings", section: "doctor" });
  assert.equal(s.settings, "doctor");
  assert.equal(s.pickerOpen, false); // one popup at a time
  const checks = [{ id: "ollama", label: "Ollama", state: "fail", detail: "Not reachable", hint: "Start Ollama" }];
  s = reduce(s, frame("doctor_report", { checks }, null));
  assert.deepEqual(s.doctor, checks);
  const facts = [{ id: 3, content: "The user likes green tea", source: "writer_pass", pinned: false, created_ts: 1, forgotten: false }];
  s = reduce(s, frame("memory_facts", { facts }, null));
  assert.deepEqual(s.memory, facts);
  s = reduce(s, { kind: "settings", section: null });
  assert.equal(s.settings, null);
  assert.deepEqual(s.doctor, checks); // shown at once next time, then refreshed
});

test("the editable settings arrive as one frame, a refusal with its reason (K1-13b, FR-SET-2)", () => {
  let s = reduce(initialState, { kind: "settings", section: "models" });
  assert.equal(s.prefs, null);
  const prefs = {
    ollama_url: "http://127.0.0.1:11434",
    budget: { enabled: true, hourly_usd: 0.25, daily_usd: null, monthly_usd: 20 },
    custom_api: null,
    screen: { task_guide: false, ocr_watch: true },
    saved: ["screen"],
    file: "C:/data/settings.json",
    problem: null,
  };
  s = reduce(s, frame("settings", prefs, null));
  assert.deepEqual(s.prefs, prefs);
  s = reduce(s, frame("settings", { ...prefs, problem: "Ollama must run on this PC." }, null));
  assert.equal(s.prefs.problem, "Ollama must run on this PC.");
  assert.equal(s.settings, "models"); // the dialog stays open on its section
});

// K1c-08 (FR-MODE-1, 6): the mode comes from the open thread; the New roleplay dialog.

test("the open thread's mode decides how it is shown; before one opens, chat (FR-MODE-1)", () => {
  assert.equal(currentMode(initialState), "chat");
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  assert.equal(currentMode(s), "chat");
  const card = { title: "Rainy café", setting: "A café at night" };
  s = reduce(s, frame("thread_opened", { thread: thread("t2", { mode: "roleplay", scenario: card }), messages: [] }, "t2"));
  assert.equal(currentMode(s), "roleplay");
  assert.deepEqual(s.thread.scenario, card);
  // a companion switch does not touch the mode: it is the thread's, not hers
  s = reduce(s, frame("waifu_state", { active: "luna", waifus: [{ id: "luna", name: "Luna" }], problems: [], pending: null }, null));
  assert.equal(currentMode(s), "roleplay");
});

test("the saved scenario cards arrive as one frame (FR-MODE-6)", () => {
  assert.equal(initialState.scenarios, null); // not asked yet
  const cards = [{ id: "c1", title: "Rainy café", card: { title: "Rainy café" }, updated_at: 2 }];
  const s = reduce(run(online), frame("scenarios", { cards }, null));
  assert.deepEqual(s.scenarios, cards);
  assert.deepEqual(reduce(s, frame("scenarios", { cards: [] }, null)).scenarios, []);
});

test("a card save waits for its own answer, never for another list (FR-MODE-6)", () => {
  const cards = [{ id: "c1", title: "Rainy café", card: { title: "Rainy café" }, updated_at: 2 }];
  let s = reduce(run(online), { kind: "roleplay", open: true });
  assert.equal(s.scenarioSave, null);
  s = reduce(s, { kind: "scenario_saving" });
  assert.equal(s.scenarioSave, "pending");
  // the dialog's first list, or a delete's answer, is not the save's answer
  s = reduce(s, frame("scenarios", { cards }, null));
  assert.equal(s.scenarioSave, "pending");
  assert.deepEqual(s.scenarios, cards);
  // the save's answer names the saved card, whichever card is newest
  const saved = [cards[0], { id: "mine", title: "Mine", card: {}, updated_at: 1 }];
  s = reduce(s, frame("scenarios", { cards: saved, saved_id: "mine" }, null));
  assert.deepEqual(s.scenarioSave, { saved: "mine" });
  // a later list does not change it
  assert.deepEqual(reduce(s, frame("scenarios", { cards }, null)).scenarioSave, { saved: "mine" });
  // reopening starts clean
  assert.equal(reduce(reduce(s, { kind: "roleplay", open: false }), { kind: "roleplay", open: true }).scenarioSave, null);
});

test("a store failure ends a pending card save; other errors and idle saves are left alone (FR-MODE-6)", () => {
  const unavailable = frame("error", { code: "threads_unavailable", message: "Saved scenarios are unavailable right now." }, null);
  let s = reduce(reduce(run(online), { kind: "roleplay", open: true }), { kind: "scenario_saving" });
  assert.equal(reduce(s, frame("error", { code: "turn_running", message: "busy" }, null)).scenarioSave, "pending");
  s = reduce(s, unavailable);
  assert.equal(s.scenarioSave, "failed");
  assert.equal(s.notice.code, "threads_unavailable");
  // a failure arriving later does not count for a save that was already answered
  const done = reduce(reduce(s, { kind: "scenario_saving" }), frame("scenarios", { cards: [], saved_id: "c9" }, null));
  assert.deepEqual(reduce(done, unavailable).scenarioSave, { saved: "c9" });
  assert.equal(reduce(run(online), unavailable).scenarioSave, null);
});

test("a dropped connection ends a pending card save as lost, never stuck on Saving (FR-MODE-6)", () => {
  let s = reduce(reduce(run(online), { kind: "roleplay", open: true }), { kind: "scenario_saving" });
  s = reduce(s, { kind: "status", status: "offline" });
  assert.equal(s.scenarioSave, "lost");
  assert.equal(s.roleplayOpen, true); // the dialog and its form stay
  // an answered save is left as it was
  const done = reduce(reduce(run(online), { kind: "scenario_saving" }), frame("scenarios", { cards: [], saved_id: "c1" }, null));
  assert.deepEqual(reduce(done, { kind: "status", status: "offline" }).scenarioSave, { saved: "c1" });
});

test("Start roleplay closes the dialog only when the thread opens; a refusal keeps it (FR-MODE-6)", () => {
  const opened = frame("thread_opened", { thread: thread("t2", { mode: "roleplay" }), messages: [] }, "t2");
  let s = reduce(run(online), { kind: "roleplay", open: true });
  s = reduce(s, { kind: "roleplay_starting" });
  assert.equal(s.roleplayStart, "pending");
  assert.equal(s.roleplayOpen, true);
  // the kernel opened it: the dialog closes
  const ok = reduce(s, opened);
  assert.equal(ok.roleplayOpen, false);
  assert.equal(ok.roleplayStart, null);
  // refused (a turn started first, or the store failed): open, with the reason
  for (const code of ["turn_running", "threads_unavailable"]) {
    const refused = reduce(s, frame("error", { code, message: "Not now." }, null));
    assert.equal(refused.roleplayOpen, true, code);
    assert.deepEqual(refused.roleplayStart, { failed: "Not now." }, code);
  }
  // the connection dropped before the answer: open, not waiting
  const dropped = reduce(s, { kind: "status", status: "offline" });
  assert.equal(dropped.roleplayOpen, true);
  assert.equal(typeof dropped.roleplayStart.failed, "string");
  // with no start asked, an opened thread does not touch the dialog
  const idle = reduce(run(online), { kind: "roleplay", open: true });
  assert.equal(reduce(idle, opened).roleplayOpen, true);
  // reopening starts clean
  assert.equal(reduce(reduce(dropped, { kind: "roleplay", open: false }), { kind: "roleplay", open: true }).roleplayStart, null);
});

test("New roleplay opens only when a new thread could start, and always closes (FR-MODE-6)", () => {
  const open = { kind: "roleplay", open: true };
  const close = { kind: "roleplay", open: false };
  assert.equal(canStartThread(initialState), false); // still connecting
  assert.equal(reduce(initialState, open).roleplayOpen, false);
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  assert.equal(canStartThread(s), true);
  s = reduce(s, { kind: "picker", open: true });
  s = reduce(s, open);
  assert.equal(s.roleplayOpen, true);
  assert.equal(s.pickerOpen, false); // one popup at a time
  assert.equal(reduce(s, close).roleplayOpen, false);
  // mid-turn: no new thread (the kernel refuses one too)
  const busy = reduce(reduce(s, close), { kind: "sent", text: "hi" });
  assert.equal(canStartThread(busy), false);
  assert.equal(reduce(busy, open).roleplayOpen, false);
  // offline: no new thread
  const offline = reduce(reduce(s, close), { kind: "status", status: "offline" });
  assert.equal(canStartThread(offline), false);
  assert.equal(reduce(offline, open).roleplayOpen, false);
});

// UI1-09: toasts and the in-app confirm

test("toasts queue up to a few, the oldest giving way, and each goes by its id", () => {
  let s = initialState;
  for (const text of ["a", "b", "c", "d"]) s = reduce(s, { kind: "toast", text });
  assert.equal(s.toasts.length, MAX_TOASTS);
  assert.deepEqual(s.toasts.map((t) => t.text), ["b", "c", "d"]);
  s = reduce(s, { kind: "toast_gone", id: s.toasts[1].id });
  assert.deepEqual(s.toasts.map((t) => t.text), ["b", "d"]);
});

test("a confirm is asked and answered without closing what it sits on", () => {
  const ask = { title: "Remove the key?", action: "Remove", danger: true };
  let s = { ...initialState, pickerOpen: true };
  s = reduce(s, { kind: "confirm", ask });
  assert.deepEqual([s.confirm, s.pickerOpen], [ask, true]);
  s = reduce(s, { kind: "confirm", ask: null });
  assert.equal(s.confirm, null);
});

// UI1-10 (D-095): the keyboard

import { anyModal, paletteItems, shortcutFor } from "../src/app/keys.ts";

const key = (k, mods = {}) => ({ key: k, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...mods });

test("Ctrl+N, Ctrl+K, Ctrl+comma and Escape are the shortcuts; a handled Escape is not a Stop", () => {
  assert.equal(shortcutFor(key("n", { ctrlKey: true })), "new_chat");
  assert.equal(shortcutFor(key("K", { ctrlKey: true })), "palette");
  assert.equal(shortcutFor(key(",", { ctrlKey: true })), "settings");
  assert.equal(shortcutFor(key("Escape")), "stop");
  assert.equal(shortcutFor(key("Escape", { defaultPrevented: true })), null);
  assert.equal(shortcutFor(key("n", { ctrlKey: true, shiftKey: true })), null);
  assert.equal(shortcutFor(key("n")), null);
  assert.equal(shortcutFor(key("k", { ctrlKey: true, isComposing: true })), null);
});

test("any open dialog or pop-up keeps the shortcuts away", () => {
  assert.equal(anyModal(initialState), false);
  for (const open of [{ settings: "models" }, { roleplayOpen: true }, { profile: "luna" }, { confirm: { title: "x", action: "y" } }, { pickerOpen: true }, { palette: true }]) {
    assert.equal(anyModal({ ...initialState, ...open }), true);
  }
});

test("the palette lists what works now and filters by every word", () => {
  const base = run(
    online,
    frame("waifu_state", { waifus: [{ id: "luna", name: "Luna" }, { id: "yuri", name: "Yuri" }], active: "luna", pending: null }),
    frame("thread_list", { query: "", threads: [thread("a", { title: "Garden plans" }), thread("b", { title: "Cat names" })] }),
    frame("thread_opened", { thread: thread("a", { title: "Garden plans" }), messages: [] }),
  );
  const labels = (s, q) => paletteItems(s, q).map((i) => i.label);
  const all = labels(base, "");
  assert.ok(all.includes("New chat") && all.includes("Talk to Yuri") && all.includes("Luna's profile"));
  assert.ok(!all.includes("Talk to Luna")); // she is already here
  assert.ok(all.includes("Cat names") && !all.includes("Garden plans")); // not the open one
  assert.deepEqual(labels(base, "cat NA"), ["Cat names"]);
  assert.deepEqual(labels(base, "zzz"), []);
  // mid-reply: no new thread, no model switch, no other conversation
  const busy = reduce(base, { kind: "sent", text: "hi" });
  const during = labels(busy, "");
  assert.ok(!during.includes("New chat") && !during.includes("Choose a model") && !during.includes("Cat names"));
  assert.ok(during.includes("Settings"));
});

test("opening the palette closes the model picker", () => {
  const s = reduce({ ...initialState, pickerOpen: true }, { kind: "palette", open: true });
  assert.deepEqual([s.palette, s.pickerOpen], [true, false]);
});

// D-100: every message on screen carries its stored id, so its ⋯ card can act on it.
test("a finished turn takes the stored ids, pins and swipes the engine reports", () => {
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, { kind: "sent", text: "hello" });
  s = reduce(s, frame("turn_start", { user_text: "hello" }));
  s = reduce(s, frame("token", { text: "Hi there. [happy]" }));
  const reply = stored(8, "assistant", "Hi there.", { swipes: [{ content: "Old" }, null], swipe: 1 });
  s = reduce(s, frame("exchange_saved", { user: stored(7, "user", "hello", { pinned: true }), reply }));
  assert.equal(s.messages.length, 1); // nothing shown before turn_done
  s = reduce(s, frame("turn_done", { text: "Hi there.", stopped: false }));
  assert.deepEqual(
    s.messages.map((m) => [m.key, m.id, m.text, m.pinned ?? false, m.swipes ?? 1, m.swipe ?? 0]),
    [["m7", 7, "hello", true, 1, 0], ["m8", 8, "Hi there.", false, 2, 1]],
  );
  assert.equal(s.saved, null);
});

// D-121: a line about self-harm gets the help card, never a reply.
test("a flagged line is marked and gets no reply", () => {
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, { kind: "sent", text: "a line" });
  s = reduce(s, frame("turn_start", { user_text: "a line" }));
  s = reduce(s, frame("safety", { where: "user" }));
  s = reduce(s, frame("exchange_saved", { user: stored(3, "user", "a line", { safety: "user" }), reply: null }));
  s = reduce(s, frame("turn_done", { text: "", stopped: false }));
  assert.deepEqual(s.messages.map((m) => [m.key, m.role, m.safety]), [["m3", "user", "user"]]);
  assert.equal(s.turn, "idle");
});

test("a harmful reply is dropped mid-stream and the line marked", () => {
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, frame("turn_start", { user_text: "hi" }));
  s = reduce(s, frame("token", { text: "Some words" }));
  s = reduce(s, frame("safety", { where: "reply" }));
  assert.equal(visibleStream(s), "");
  s = reduce(s, frame("turn_done", { text: "", stopped: false }));
  assert.deepEqual(s.messages.map((m) => [m.role, m.safety]), [["user", "reply"]]);
  assert.equal(fromStored(stored(4, "user", "hi", { safety: "reply" })).safety, "reply");
  assert.equal(fromStored(stored(5, "user", "hi", { safety: "nope" })).safety, undefined);
});

test("a changed message (a pin, a swipe) replaces its row in place", () => {
  let s = run(
    online,
    frame("thread_opened", { thread: thread("t1"), messages: [stored(1, "user", "hi"), stored(2, "assistant", "two", { swipes: [{}, null], swipe: 1 })] }),
  );
  s = reduce(s, frame("message_updated", { message: stored(2, "assistant", "one", { swipes: [null, {}], swipe: 0, pinned: true }) }));
  assert.deepEqual(
    s.messages.map((m) => [m.key, m.text, m.swipe ?? null, m.pinned ?? false]),
    [["m1", "hi", null, false], ["m2", "one", 0, true]],
  );
});

test("a refused pin leaves a running turn alone", () => {
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, { kind: "sent", text: "hello" });
  s = reduce(s, frame("error", { code: "pin_limit", message: "A story can have 10 pinned messages." }));
  assert.equal(s.turn, "thinking");
});

// D-101: History and Memory belong to a roleplay; Memory follows its own story.
test("a roleplay's pages open only in a roleplay, and Memory closes when another thread opens", () => {
  let s = run(online, frame("thread_opened", { thread: thread("t1"), messages: [] }));
  s = reduce(s, { kind: "story", panel: "memory" });
  assert.equal(s.story, null); // a chat has no Memory
  s = reduce(s, frame("thread_opened", { thread: thread("t2", { mode: "roleplay" }), messages: [] }, "t2"));
  s = reduce(s, { kind: "story", panel: "memory" });
  assert.equal(s.story, "memory");
  s = reduce(s, frame("thread_opened", { thread: thread("t3", { mode: "roleplay" }), messages: [] }, "t3"));
  assert.equal(s.story, null);
  s = reduce(s, { kind: "story", panel: "history" });
  s = reduce(s, frame("thread_opened", { thread: thread("t4", { mode: "roleplay" }), messages: [] }, "t4"));
  assert.equal(s.story, "history"); // History closes itself when a story is picked
});

test("an error about something else does not end a started turn or bring back the old reply (audit)", () => {
  let s = run(
    online,
    frame("thread_opened", { thread: thread("t1"), messages: [stored(1, "user", "hi"), stored(2, "assistant", "old")] }),
    { kind: "regenerating" },
    frame("turn_start", { user_text: "hi" }),
  );
  s = reduce(s, frame("error", { code: "unknown_thread", message: "That conversation no longer exists.", reply_to: null }, null));
  assert.equal(s.turn, "thinking");
  assert.ok(!s.messages.some((m) => m.text === "old"));
});

test("Regenerate skips a screen remark after the exchange, as the kernel does (audit)", () => {
  const s = run(
    online,
    frame("thread_opened", {
      thread: thread("t1"),
      messages: [stored(1, "user", "hi"), stored(2, "assistant", "hello"), stored(3, "assistant", "You have a typo.", { ambient: true })],
    }),
  );
  assert.deepEqual(lastExchange(s.messages), [0, 1]);
});

test("the not-connected notice goes once the engine is back (audit)", () => {
  let s = run({ kind: "status", status: "offline" }, { kind: "problem", reason: NOT_CONNECTED });
  assert.equal(s.notice.text, NOT_CONNECTED);
  s = reduce(s, online);
  assert.equal(s.notice, null);
});
