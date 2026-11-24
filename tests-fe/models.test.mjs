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
  modelStatusHere,
  reduce,
} from "../src/app/chat-state.ts";
import {
  SLOW_AFTER_S,
  THINKING_WORDS,
  WAKING_LINES,
  WAKING_STEP_S,
  awakeLine,
  badgesFor,
  companiesOf,
  effortLabel,
  failedLine,
  filterCompanies,
  filterRows,
  parsePickerPrefs,
  sortRows,
  formatElapsed,
  formatSize,
  isLocalRef,
  modelFacts,
  shortRef,
  thinkingOrder,
  wakingLine,
} from "../src/app/models.ts";
import { revealTo } from "../src/app/typewriter.ts";

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
  mode: "chat", // FR-MODE-1: what the kernel sends for a chat thread
  scenario: {},
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
  assert.deepEqual(badgesFor({ tags: ["reasoning", "Thinking", "vision", "json", "tools", "free"] }), ["vision", "thinking", "tools"]);
  assert.deepEqual(badgesFor({}), []);
  assert.deepEqual(badgesFor({ tags: ["tool-use", "reasoning", "structured-output"] }), ["thinking", "tools"]); // AI Router's tags, in the badges' own order
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

test("thinking words: each once a turn in a fresh order, short, and none from the waking lines (D-096)", () => {
  let seed = 7;
  const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const order = thinkingOrder(rand);
  assert.equal(order.length, THINKING_WORDS.length);
  assert.equal(new Set(order).size, THINKING_WORDS.length);
  assert.notDeepEqual(order, THINKING_WORDS);
  assert.deepEqual([...order].sort(), [...THINKING_WORDS].sort());
  // "Waifu-mode-engaging" is the user's word, approved as the one exception to D-082 (D-097).
  const ordinary = THINKING_WORDS.filter((w) => w !== "Waifu-mode-engaging");
  assert.equal(ordinary.length, THINKING_WORDS.length - 1);
  assert.ok(THINKING_WORDS.every((w) => w.length <= 20 && !/\s/.test(w)));
  assert.ok(ordinary.every((w) => !/waifu|kernel/i.test(w)));
  assert.ok(THINKING_WORDS.every((w) => !WAKING_LINES.some((l) => l.toLowerCase().includes(w.toLowerCase()))));
});

test("a reply types out: steady when close, faster when far behind, never half an emoji (D-096)", () => {
  assert.equal(revealTo(0, "hello", 16), 1); // at least a letter a frame
  assert.equal(revealTo(5, "hello", 16), 5);
  const long = "x".repeat(700);
  assert.ok(revealTo(0, long, 100) >= 100); // 700 behind: about 1000 letters a second
  let shown = 0;
  let ms = 0;
  while (shown < long.length) {
    shown = revealTo(shown, long, 16);
    ms += 16;
  }
  assert.ok(ms < 4000, `${ms} ms to type 700 letters`);
  assert.ok(ms > 1000, "not dumped at once");
  assert.equal(revealTo(0, "\u{1F600}a", 16), 2); // the emoji's two halves together
  assert.equal(revealTo(0, "a", -5), 1); // a clock that went back still moves on
});

test("the loading strip speaks only for this thread's model", () => {
  const status = (model_ref, state) => ({ kind: "frame", frame: { v: 1, type: "model_status", id: "s", thread: null, data: { model_ref, label: null, state, message: null, elapsed_s: 0 } } });
  const hello = { kind: "frame", frame: { v: 1, type: "hello", id: "s", thread: null, data: { protocol: 1, kernel: "k", default_model_ref: "local:a" } } };
  let s = reduce(reduce(initialState, hello), status("local:a", "loading"));
  assert.equal(modelStatusHere(s)?.state, "loading");
  assert.equal(modelStatusHere(reduce(s, status("local:b", "loading"))), null); // another thread's model
  assert.equal(modelStatusHere(reduce(s, status("local:a", "ready")))?.state, "ready");
});

test("the hover details: full id searchable, facts in one muted line (D-084, FR-M-12)", () => {
  const row = {
    ref: "local:ollama/hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L",
    label: "Qwen3.5 9B Q6_K_L",
    full: "hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K_L",
    kind: "local",
    backend: "ollama",
    detail: "Ollama · 9.0B · Q6_K",
    size_bytes: 7_600_000_000,
    available: true,
    note: null,
    fits: true,
  };
  assert.equal(modelFacts(row), "Ollama · 9.0B · Q6_K · 7.6 GB");
  assert.equal(filterRows([row], "bartowski").length, 1);
  const api = { ...row, detail: "200k context", size_bytes: null, price_in: 3, price_out: 15, note: "needs an API key" };
  assert.equal(modelFacts(api), "200k context · $3.00 / $15.00 per 1M · needs an API key");
});

test("the picker sorts by company, name or price and shows only the companies picked (D-127)", () => {
  const r = (label, group, price_in, price_out) => ({ ref: `api:x/${label}`, label, group, kind: "api", price_in, price_out });
  const rows = [r("Opus", "Anthropic", 5, 25), r("Haiku", "Anthropic", 1, 5), r("Flash", "Google", 0.3, 2.5), r("Mystery", "Vendor", null, null)];
  assert.deepEqual(sortRows(rows, "company"), rows);                                  // the kernel's order
  assert.deepEqual(sortRows(rows, "name").map((x) => x.label), ["Flash", "Haiku", "Mystery", "Opus"]);
  assert.deepEqual(sortRows(rows, "cheap").map((x) => x.label), ["Flash", "Haiku", "Opus", "Mystery"]); // no price: last
  assert.deepEqual(sortRows(rows, "pricey").map((x) => x.label), ["Opus", "Haiku", "Flash", "Mystery"]);
  assert.deepEqual(sortRows([r("Model 10", "A", 1, 1), r("Model 9", "A", 1, 1)], "name").map((x) => x.label), ["Model 9", "Model 10"]);
  assert.deepEqual(companiesOf(rows), ["Anthropic", "Google", "Vendor"]);
  assert.deepEqual(filterCompanies(rows, ["Google"]).map((x) => x.label), ["Flash"]);
  assert.deepEqual(filterCompanies(rows, []), rows);
  assert.deepEqual(filterCompanies(rows, ["Gone"]), rows);                            // a stale pick never empties the list
  assert.deepEqual(parsePickerPrefs('{"order":"cheap","companies":["Google",3],"all":true}'), { order: "cheap", companies: ["Google"], all: true });
  assert.deepEqual(parsePickerPrefs("not json"), { order: "company", companies: [], all: false });
  assert.deepEqual(parsePickerPrefs('{"order":"random","all":"yes"}'), { order: "company", companies: [], all: false });
});
