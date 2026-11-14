import { test } from "node:test";
import assert from "node:assert/strict";
import {
  PROTOCOL_VERSION,
  ReplyAccumulator,
  clientFrame,
  parseFrame,
  stripTrailingTag,
} from "../src/net/protocol.ts";

test("a client frame carries the version, a unique id and the data", () => {
  const a = clientFrame("thread_open", { id: "t1" });
  const b = clientFrame("thread_new", {});
  assert.equal(a.v, PROTOCOL_VERSION);
  assert.equal(a.type, "thread_open");
  assert.deepEqual(a.data, { id: "t1" });
  assert.equal(a.thread, null);
  assert.notEqual(a.id, b.id);
});

test("flat messages are legacy; v1 frames parse; anything else is a stated problem", () => {
  assert.equal(parseFrame({ type: "speak", text: "hi" }).kind, "legacy");
  assert.equal(parseFrame("nope").kind, "legacy");
  const ok = parseFrame({ v: 1, type: "token", id: "x", thread: "t", data: { text: "a" } });
  assert.equal(ok.kind, "frame");
  assert.equal(ok.frame.data.text, "a");
  assert.match(parseFrame({ v: 2, type: "token", data: {} }).reason, /protocol 2/);
  assert.equal(parseFrame({ v: 1, type: "nonsense", data: {} }).kind, "error");
  assert.equal(parseFrame({ v: 1, type: "token", data: null }).kind, "error");
});

test("the trailing emotion tag is hidden, also while it is still being written", () => {
  assert.equal(stripTrailingTag("Hello there. [happy]"), "Hello there.");
  assert.equal(stripTrailingTag("Hello there. [hap"), "Hello there.");
  assert.equal(stripTrailingTag("See [the docs](http://x) now"), "See [the docs](http://x) now");
  assert.equal(stripTrailingTag("A list [one two] here"), "A list [one two] here");
  assert.equal(stripTrailingTag("No tag"), "No tag");
});

test("tokens accumulate into the visible reply", () => {
  const acc = new ReplyAccumulator("t1");
  assert.equal(acc.push("Hel"), "Hel");
  assert.equal(acc.push("lo. [ha"), "Hello.");
  assert.equal(acc.push("ppy]"), "Hello.");
  assert.equal(acc.thread, "t1");
});
