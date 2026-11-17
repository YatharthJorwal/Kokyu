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

test("thread_new carries the mode and the scenario card as given (FR-MODE-1, FR-MODE-6)", () => {
  const roleplay = clientFrame("thread_new", { mode: "roleplay", scenario: { title: "Rain", opening: "*waves*" } });
  assert.deepEqual(roleplay.data, { mode: "roleplay", scenario: { title: "Rain", opening: "*waves*" } });
  assert.deepEqual(clientFrame("thread_new", {}).data, {}); // the kernel reads {} as a chat thread
});

test("saved scenario cards: list, save, delete out; the scenarios list back (FR-MODE-6)", () => {
  assert.deepEqual(clientFrame("scenario_list", {}).data, {});
  assert.deepEqual(clientFrame("scenario_save", { card: { setting: "A pier." } }).data, { card: { setting: "A pier." } });
  assert.deepEqual(clientFrame("scenario_save", { id: "c1", card: {} }).data, { id: "c1", card: {} });
  assert.deepEqual(clientFrame("scenario_delete", { id: "c1" }).data, { id: "c1" });
  const cards = [{ id: "c1", title: "A pier.", card: { setting: "A pier." }, updated_at: 1 }];
  const back = parseFrame({ v: 1, type: "scenarios", id: "x", thread: null, data: { cards } });
  assert.equal(back.kind, "frame");
  assert.deepEqual(back.frame.data.cards, cards);
});

test("v1 frames parse; anything else, a flat message included, is a stated problem (D-062)", () => {
  assert.equal(parseFrame({ type: "speak", text: "hi" }).kind, "error");
  assert.equal(parseFrame("nope").kind, "error");
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
