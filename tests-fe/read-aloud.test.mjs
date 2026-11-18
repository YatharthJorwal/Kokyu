import { test } from "node:test";
import assert from "node:assert/strict";

import { reduce, initialState } from "../src/app/chat-state.ts";
import { readAloudLine, voiceStarting, VOICE_START_S } from "../src/app/read-aloud.ts";

// D-097: Read aloud replaces voice mode. The chip says when her voice is starting
// (about 47 s), when it reads, and when it failed; nothing while off.

const st = (state, on = true, message = null) => ({ on, state, message, elapsed_s: null });

test("no chip while Read aloud is off", () => {
  assert.equal(readAloudLine(null, "Luna", 0), null);
  assert.equal(readAloudLine(st("ready", false), "Luna", 0), null);
  assert.equal(voiceStarting(st("loading", false)), false);
});

test("starting counts up to about 47 s, then just counts", () => {
  assert.equal(VOICE_START_S, 47);
  assert.equal(readAloudLine(st("idle"), "Luna", 0), "Starting Luna's voice, about 47 s…");
  assert.equal(readAloudLine(st("loading"), "Luna", 0), "Starting Luna's voice, about 47 s…");
  assert.equal(readAloudLine(st("loading"), "Luna", 12.7), "Starting Luna's voice… 12 s of about 47");
  assert.equal(readAloudLine(st("loading"), "Yuri", 63), "Starting Yuri's voice… 63 s");
  assert.equal(voiceStarting(st("loading")), true);
  assert.equal(voiceStarting(st("idle")), true);
  assert.equal(voiceStarting(st("ready")), false);
});

test("ready and failed say so", () => {
  assert.equal(readAloudLine(st("ready"), "Luna", 50), "Read aloud: Luna reads her replies");
  assert.equal(
    readAloudLine(st("failed", true, "Check logs/gpt_sovits.log."), "Luna", 0),
    "Luna's voice couldn't start. Check logs/gpt_sovits.log.",
  );
  assert.equal(readAloudLine(st("failed"), "Luna", 0), "Luna's voice couldn't start.");
});

test("the engine's read_aloud_status lands in the state and goes on disconnect", () => {
  let s = reduce(initialState, { kind: "status", status: "online" });
  s = reduce(s, { kind: "frame", frame: { v: 1, type: "read_aloud_status", data: st("loading"), thread: null } });
  assert.deepEqual(s.readAloud, st("loading"));
  s = reduce(s, { kind: "status", status: "offline" });
  assert.equal(s.readAloud, null); // the engine re-sends it on reconnect (kept in settings.json)
});

test("the message being read on request is the window's own state, gone on disconnect (D-099)", () => {
  let s = reduce(initialState, { kind: "status", status: "online" });
  assert.equal(s.reading, null);
  s = reduce(s, { kind: "reading", key: "m7" });
  assert.equal(s.reading, "m7");
  s = reduce(s, { kind: "reading", key: null });
  assert.equal(s.reading, null);
  s = reduce(reduce(s, { kind: "reading", key: "m8" }), { kind: "status", status: "offline" });
  assert.equal(s.reading, null);
});
