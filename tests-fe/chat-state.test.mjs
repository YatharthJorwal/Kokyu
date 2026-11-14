import { test } from "node:test";
import assert from "node:assert/strict";

import { canRegenerate, canSend, initialState, lastExchange, reduce, visibleStream } from "../src/app/chat-state.ts";
import { backoffMs, dispatchRaw } from "../src/net/kernel.ts";

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

test("a legacy turn_end closes a turn that never got turn_done, keeping the partial text", () => {
  let s = run(online, frame("turn_start", { user_text: "x" }), frame("token", { text: "par" }));
  s = reduce(s, { kind: "legacy", msg: { type: "turn_end" } });
  assert.equal(s.turn, "idle");
  assert.equal(s.messages.at(-1).text, "par");
  // and after a normal turn_done it changes nothing
  assert.deepEqual(reduce(s, { kind: "legacy", msg: { type: "turn_end" } }), s);
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

test("companion name, observer role and a lost connection", () => {
  let s = run(
    online,
    { kind: "legacy", msg: { type: "waifu_state", active: "yuri", waifus: [{ id: "yuri", name: "Yuri" }], problems: [] } },
  );
  assert.deepEqual(s.companion, { id: "yuri", name: "Yuri" });
  s = reduce(s, { kind: "legacy", msg: { type: "surface_status", role: "observer" } });
  assert.equal(canSend(s), false);
  s = reduce(s, { kind: "legacy", msg: { type: "surface_status", role: "driver" } });
  s = reduce(s, frame("turn_start", { user_text: "x" }));
  s = reduce(s, { kind: "status", status: "offline" });
  assert.equal(s.turn, "idle");
  assert.equal(canSend(s), false);
});

test("the socket splits v1 frames from legacy messages and reports what it cannot read", () => {
  const seen = [];
  const h = {
    onFrame: (f) => seen.push(["frame", f.type]),
    onLegacy: (m) => seen.push(["legacy", m.type]),
    onStatus: () => {},
    onProblem: (r) => seen.push(["problem", r]),
  };
  dispatchRaw(JSON.stringify({ v: 1, type: "token", id: "a", thread: "t", data: { text: "x" } }), h);
  dispatchRaw(JSON.stringify({ type: "speak", text: "x", audio_b64: "", mime: "audio/wav" }), h);
  dispatchRaw(JSON.stringify({ v: 2, type: "token", id: "a", thread: "t", data: {} }), h);
  dispatchRaw("not json", h);
  assert.deepEqual(seen.map((x) => x[0]), ["frame", "legacy", "problem", "problem"]);
  assert.deepEqual([0, 1, 2, 3, 9].map(backoffMs), [250, 500, 1000, 2000, 2000]);
});

test("a file send waits for the kernel's wording of the line (K1-05, FR-C-3)", () => {
  let s = run(online, { kind: "sent", text: null });
  assert.equal(s.turn, "thinking");
  assert.equal(s.messages.length, 0); // no guessed line: the kernel words it ("shared an image…")
  s = reduce(s, frame("turn_start", { user_text: '(shared an image, "cat.png") A cat on a desk.\n\nlook' }));
  assert.deepEqual(s.messages.map((m) => [m.role, m.pending ?? false]), [["user", false]]);
  // the vision step failed: Yuri's widget message closes the turn without one
  s = reduce(run(online, { kind: "sent", text: null }), { kind: "legacy", msg: { type: "turn_end" } });
  assert.equal(s.turn, "idle");
});

test("the screen companions' state comes from the kernel and goes on disconnect (K1-05b)", () => {
  let s = run(online, frame("screen_companions", { task_guide: { on: true, task: "essay" }, ocr_watch: { on: false } }, null));
  assert.equal(s.screen.task_guide.task, "essay");
  s = reduce(s, { kind: "status", status: "offline" });
  assert.equal(s.screen, null); // a restarted kernel starts with both off (FR-SC-1)
});
