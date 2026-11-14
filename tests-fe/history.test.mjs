import { test } from "node:test";
import assert from "node:assert/strict";

import { groupOf, groupThreads, toMs } from "../src/app/history.ts";

// K1-03 (FR-C-6): the sidebar groups history by day.

const at = (y, m, d, h = 12) => new Date(y, m - 1, d, h, 0, 0).getTime();
const NOW = at(2026, 11, 14, 15);
const thread = (id, ms) => ({
  id,
  title: id,
  created_at: ms / 1000,
  updated_at: ms / 1000, // the kernel sends Unix seconds
  active_waifu_id: null,
  model_ref: null,
  effort: null,
  temp: false,
  archived: false,
});

test("days are calendar days in local time, not 24-hour windows", () => {
  assert.equal(groupOf(at(2026, 11, 14, 0) / 1000 + 1, NOW), "Today");
  assert.equal(groupOf(at(2026, 11, 13, 23) / 1000, NOW), "Yesterday"); // 16 hours ago, but yesterday
  assert.equal(groupOf(at(2026, 11, 13, 0) / 1000, NOW), "Yesterday");
  assert.equal(groupOf(at(2026, 11, 8) / 1000, NOW), "Previous 7 days");
  assert.equal(groupOf(at(2026, 11, 7, 0) / 1000, NOW), "Previous 7 days");
  assert.equal(groupOf(at(2026, 11, 6, 23) / 1000, NOW), "Older");
  assert.equal(toMs(1_700_000_000), 1_700_000_000_000);
  assert.equal(toMs(1_700_000_000_000), 1_700_000_000_000);
});

test("groups come in order, newest first inside each, and empty groups are left out", () => {
  const groups = groupThreads(
    [thread("old", at(2026, 1, 2)), thread("t2", at(2026, 11, 14, 9)), thread("t1", at(2026, 11, 14, 14)), thread("w", at(2026, 11, 10))],
    NOW,
  );
  assert.deepEqual(
    groups.map((g) => [g.name, g.threads.map((t) => t.id)]),
    [["Today", ["t1", "t2"]], ["Previous 7 days", ["w"]], ["Older", ["old"]]],
  );
  assert.deepEqual(groupThreads([], NOW), []);
});

import { initialState, reduce } from "../src/app/chat-state.ts";

const frame = (type, data) => ({ kind: "frame", frame: { v: 1, type, id: "s", thread: null, data } });

test("the roster and the active companion come from waifu_state", () => {
  const s = reduce(initialState, {
    kind: "legacy",
    msg: { type: "waifu_state", active: "luna", waifus: [{ id: "yuri", name: "Yuri", premade: true, traits: [] }, { id: "luna", name: "Luna" }] },
  });
  assert.deepEqual(s.roster, [{ id: "yuri", name: "Yuri" }, { id: "luna", name: "Luna" }]); // no extra fields kept
  assert.deepEqual(s.companion, { id: "luna", name: "Luna" });
});

test("search results live apart from the history and follow renames and deletes", () => {
  const a = thread("a", NOW), b = thread("b", NOW);
  let s = reduce(initialState, frame("thread_list", { query: "", threads: [a, b] }));
  s = reduce(s, frame("thread_list", { query: "pizza", threads: [a, b] }));
  assert.deepEqual(s.search.threads.map((t) => t.id), ["a", "b"]);
  assert.deepEqual(s.threads.map((t) => t.id), ["a", "b"]); // the history is untouched
  // b deleted and a renamed elsewhere: the kernel sends the plain list again
  s = reduce(s, frame("thread_list", { query: "", threads: [{ ...a, title: "Pizza night" }] }));
  assert.deepEqual(s.search.threads.map((t) => [t.id, t.title]), [["a", "Pizza night"]]);
  assert.equal(s.search.query, "pizza");
});
