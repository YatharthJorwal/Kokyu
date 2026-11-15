import { test } from "node:test";
import assert from "node:assert/strict";

import {
  canPickModel,
  currentEffort,
  currentEfforts,
  currentModelRef,
  initialState,
  shownEffort,
  modelLabel,
  modelLoadingHere,
  reduce,
} from "../src/app/chat-state.ts";
import {
  SLOW_AFTER_S,
  THINKING_LINES,
  WAKING_LINES,
  WAKING_STEP_S,
  awakeLine,
  badgesFor,
  effortLabel,
  failedLine,
  filterRows,
  formatElapsed,
  formatSize,
  isLocalRef,
  shortRef,
  thinkingLine,
  wakingLine,
} from "../src/app/models.ts";

// K1-10: the model chip, its picker and the "waking up" card (FR-M-1..7, D-054).

const row = (ref, label, extra = {}) => ({
  ref,
  label,
  kind: ref.startsWith("api:") ? "api" : "local",
  backend: "ollama",
  detail: null,
  size_bytes: null,
  available: true,
  note: null,
  fits: null,
  ...extra,
});

const LIST = {
  default_ref: "local:llamacpp/big",
  local: [row("local:llamacpp/big", "Qwen3.6 35B A3B", { detail: "llama.cpp · 8k context" }), row("local:ollama/qwen3.5:9b", "qwen3.5:9b")],
  api: [row("api:airouter/vendor/chat-1", "vendor/chat-1", { tags: ["reasoning"] })],
  local_error: null,
  api_error: null,
  api_stale: false,
  api_key: true,
  spend: null,
};

const frame = (type, data, thread = null) => ({ kind: "frame", frame: { v: 1, type, id: "s", thread, data } });
const thread = (model_ref = null) => ({
  id: "t1",
  title: "t",
  created_at: 1,
  updated_at: 1,
  active_waifu_id: null,
  model_ref,
  effort: null,
  temp: false,
  archived: false,
});
const online = { kind: "status", status: "online" };

test("the waking line names the companion, starts the same way and changes every few seconds", () => {
  assert.equal(wakingLine("Yuri", 0), "Yuri is waking up…");
  assert.equal(wakingLine(null, 0), "Your waifu is waking up…"); // the user's own phrase
  const seen = new Set();
  for (let s = WAKING_STEP_S; s < WAKING_STEP_S * (WAKING_LINES.length + 1); s += WAKING_STEP_S) seen.add(wakingLine("Luna", s));
  assert.equal(seen.size, WAKING_LINES.length); // every line gets its turn
  for (const line of seen) assert.match(line, /Luna/);
  assert.match(wakingLine(null, WAKING_STEP_S * 2), /your waifu|Your waifu/);
  assert.doesNotMatch(wakingLine(null, WAKING_STEP_S * 2), /\{name\}/);
  // a big model: say honestly that it takes a while
  const later = Array.from({ length: 12 }, (_, i) => wakingLine("Yuri", SLOW_AFTER_S + i * WAKING_STEP_S));
  assert.ok(later.some((l) => /Big brains take a minute/.test(l)));
  // a sentence start keeps its capital (found live: "…a minute. your waifu is…")
  const slowAnon = Array.from({ length: 12 }, (_, i) => wakingLine(null, SLOW_AFTER_S + i * WAKING_STEP_S)).find((l) =>
    l.startsWith("Big brains"),
  );
  assert.equal(slowAnon, "Big brains take a minute. Your waifu is worth the wait…");
  assert.equal(wakingLine(null, WAKING_STEP_S * 2), "Rubbing the sleep out of your waifu's eyes…");
  // replacing a model that was already up
  assert.equal(wakingLine("Yuri", 0, true), "Yuri is swapping brains. Hold still…");
  assert.equal(awakeLine("Yuri"), "Yuri is awake.");
  assert.equal(failedLine(null), "Your waifu couldn't wake up.");
});

test("small formatting helpers", () => {
  assert.equal(formatElapsed(7.9), "0:07");
  assert.equal(formatElapsed(125), "2:05");
  assert.equal(formatSize(6_600_000_000), "6.6 GB");
  assert.equal(formatSize(21_400_000_000), "21 GB");
  assert.equal(formatSize(274_000_000), "274 MB");
  assert.equal(formatSize(null), null);
  assert.equal(shortRef("local:llamacpp/qwen3.6-35b-a3b"), "qwen3.6-35b-a3b");
  assert.equal(shortRef("api:airouter/vendor/chat-1"), "vendor/chat-1");
  assert.equal(shortRef("api:open_router2/vendor/chat-1"), "vendor/chat-1"); // D-059 endpoint ids
  assert.equal(isLocalRef("api:airouter/x"), false);
  assert.equal(isLocalRef("local:ollama/x"), true);
  assert.equal(effortLabel("off"), "No thinking");
  assert.equal(effortLabel(null), null);
  // FR-M-4 variant badges: a few known tags, deduplicated, never a wall of them
  assert.deepEqual(badgesFor({ tags: ["reasoning", "Thinking", "vision", "json", "tools", "free"] }), ["reasoning", "vision", "tools"]);
  assert.deepEqual(badgesFor({}), []);
  assert.deepEqual(badgesFor({ tags: ["tool-use", "reasoning", "structured-output"] }), ["tools", "reasoning"]); // AI Router's tags
});

test("search matches every word against the label, id, detail and tags", () => {
  const rows = [...LIST.local, ...LIST.api];
  assert.deepEqual(filterRows(rows, "").length, 3);
  assert.deepEqual(filterRows(rows, "qwen").map((r) => r.label), ["Qwen3.6 35B A3B", "qwen3.5:9b"]);
  assert.deepEqual(filterRows(rows, "qwen llama.cpp").map((r) => r.label), ["Qwen3.6 35B A3B"]);
  assert.deepEqual(filterRows(rows, "REASONING").map((r) => r.label), ["vendor/chat-1"]);
  assert.deepEqual(filterRows(rows, "nothing-like-this"), []);
});

test("the chip shows the thread's model, else the kernel's default, by its label", () => {
  let s = reduce(initialState, online);
  assert.equal(currentModelRef(s), null);
  assert.equal(modelLabel(s, null), "Default model");
  // the loader may be busy with ANOTHER thread's model: never guess from it (review finding)
  s = reduce(s, frame("model_status", { model_ref: "local:llamacpp/big", label: "Qwen3.6 35B A3B", state: "ready", message: null, elapsed_s: 3 }));
  assert.equal(currentModelRef(s), null);
  s = reduce(s, frame("hello", { protocol: 1, kernel: "KASANE", default_model_ref: "local:ollama/qwen3.5:9b", default_effort: "low" }));
  s = reduce(s, frame("thread_opened", { thread: thread(null), messages: [] }, "t1"));
  assert.equal(currentModelRef(s), "local:ollama/qwen3.5:9b");
  assert.equal(currentEffort(s), "low"); // what the turn really runs with (chat.default_effort)
  s = reduce(s, frame("model_list", LIST));
  assert.equal(modelLabel(s, currentModelRef(s)), "qwen3.5:9b");
  s = reduce(s, frame("thread_updated", { thread: { ...thread("local:llamacpp/big"), effort: "high" } }, "t1"));
  assert.equal(currentModelRef(s), "local:llamacpp/big");
  assert.equal(modelLabel(s, currentModelRef(s)), "Qwen3.6 35B A3B");
  assert.equal(currentEffort(s), "high");
  assert.equal(modelLabel(s, "local:ollama/unknown:1b"), "unknown:1b");
  // a reconnect may reach a restarted kernel with another config: forget its facts
  s = reduce(s, { kind: "status", status: "offline" });
  assert.equal(s.defaults, null);
  assert.equal(s.models, null);
});

test("the effort slider offers the current model's levels, and none for a model without them", () => {
  // K1-11, FR-M-8: the kernel's model list carries each row's levels (FR-M-10, D-064)
  const list = {
    ...LIST,
    local: [row("local:ollama/qwen3.5:9b", "qwen3.5:9b", { efforts: ["off", "high"] }), row("local:llamacpp/big", "Big")],
  };
  let s = reduce(initialState, online);
  assert.deepEqual(currentEfforts(s), []); // no list yet
  s = reduce(s, frame("hello", { protocol: 1, kernel: "KASANE", default_model_ref: "local:ollama/qwen3.5:9b", default_effort: null }));
  s = reduce(s, frame("thread_opened", { thread: thread(null), messages: [] }, "t1"));
  s = reduce(s, frame("model_list", list));
  assert.deepEqual(currentEfforts(s), ["off", "high"]);
  assert.equal(currentEfforts(s), currentEfforts(s)); // same array: a store selector may return it
  s = reduce(s, frame("thread_updated", { thread: thread("local:llamacpp/big") }, "t1"));
  assert.deepEqual(currentEfforts(s), []); // a row without levels: no slider
  assert.equal(currentEfforts(s), currentEfforts(reduce(s, online))); // the empty list is shared too
});

test("the chip names an effort the model offers; before the list, only the thread's own pick", () => {
  const list = { ...LIST, local: [row("local:ollama/qwen3.5:9b", "qwen3.5:9b", { efforts: ["off", "high"] })] };
  let s = reduce(initialState, online);
  s = reduce(s, frame("hello", { protocol: 1, kernel: "KASANE", default_model_ref: "local:ollama/qwen3.5:9b", default_effort: "low" }));
  s = reduce(s, frame("thread_opened", { thread: thread(null), messages: [] }, "t1"));
  assert.equal(shownEffort(s), null); // the config default may not fit this model: unknown yet
  s = reduce(s, frame("thread_updated", { thread: { ...thread(null), effort: "high" } }, "t1"));
  assert.equal(shownEffort(s), "high"); // found live: a reconnect lost "High" until the picker opened
  s = reduce(s, frame("model_list", list));
  assert.equal(shownEffort(s), "high");
  s = reduce(s, frame("thread_updated", { thread: thread(null) }, "t1"));
  assert.equal(shownEffort(s), null); // "low" is not one of this model's levels
});

test("the picker opens only when a model can be picked and closes on send or disconnect", () => {
  let s = reduce(initialState, { kind: "picker", open: true });
  assert.equal(s.pickerOpen, false); // still connecting
  s = reduce(s, online);
  s = reduce(s, { kind: "picker", open: true });
  assert.equal(s.pickerOpen, true);
  s = reduce(s, { kind: "sent", text: "hi" });
  assert.equal(s.pickerOpen, false);
  assert.equal(canPickModel(s), false); // not mid-reply: the kernel refuses it
  s = reduce(s, frame("turn_done", { text: "ok", stopped: false }));
  s = reduce(s, { kind: "picker", open: true });
  s = reduce(s, frame("model_status", { model_ref: "x", label: "x", state: "loading", message: null, elapsed_s: 0 }));
  s = reduce(s, { kind: "status", status: "offline" });
  assert.equal(s.pickerOpen, false);
  assert.equal(s.modelStatus, null); // the kernel re-sends it on reconnect
});

test("the thinking line names her, walks the list from a random start and wraps (D-063)", () => {
  assert.equal(thinkingLine("Luna", 0), "Luna is mulling it over…");
  const turn = Array.from({ length: THINKING_LINES.length }, (_, i) => thinkingLine("Luna", i, 4));
  assert.equal(new Set(turn).size, THINKING_LINES.length); // every line once before any repeats
  assert.equal(turn[0], thinkingLine("Luna", THINKING_LINES.length, 4));
  assert.ok(turn.every((l) => l.startsWith("Luna ") && l.endsWith("…")));
  assert.equal(thinkingLine(null, 0), "Your waifu is mulling it over…");
  // FR-W-3: only the name changes between companions
  assert.equal(thinkingLine("Yuri", 3, 2).replace("Yuri", "Luna"), thinkingLine("Luna", 3, 2));
});

test("the thinking line waits while the waking-up card speaks for this thread's model", () => {
  const status = (model_ref, state) => ({ kind: "frame", frame: { v: 1, type: "model_status", id: "s", thread: null, data: { model_ref, label: null, state, message: null, elapsed_s: 0 } } });
  const hello = { kind: "frame", frame: { v: 1, type: "hello", id: "s", thread: null, data: { protocol: 1, kernel: "k", default_model_ref: "local:a" } } };
  let s = reduce(reduce(initialState, hello), status("local:a", "loading"));
  assert.equal(modelLoadingHere(s), true);
  assert.equal(modelLoadingHere(reduce(s, status("local:b", "loading"))), false); // another thread's model
  assert.equal(modelLoadingHere(reduce(s, status("local:a", "ready"))), false);
});
