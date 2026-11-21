import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_PET_PREFS, POSES, SLEEPY_AFTER, WALK_SPEED, initialPet, parsePetPrefs, petPrompt, poseFor, step,
} from "../src/app/pet-brain.ts";

const lane = { width: 800, self: 100 };
const idle = { mode: "roam", activity: "idle", ...lane };
const ALL = [...POSES];
const seq = (...values) => () => values.shift() ?? 0.5;

test("roaming, she walks to a spot at her speed, then stops (D-103, FR-P-3)", () => {
  let s = { ...initialPet(800), x: 400, left: 0 };
  s = step(s, 0.1, idle, seq(0.1, 1));          // 0.1 < 0.4: walk; target 50 + 1 * 700 = 750, to her right
  assert.equal(s.action, "walk");
  assert.equal(s.dir, 1);
  s = step(s, 1, idle);
  assert.equal(s.x, 400 + WALK_SPEED);
  assert.equal(poseFor(s, "idle", ALL).motion, "walk");
  s = step(s, 10, idle);                        // arrives and stops
  assert.equal(s.x, 750);
  assert.equal(s.action, "idle");
});

test("stay put never walks; sleep mode always sleeps", () => {
  const s = step({ ...initialPet(800), left: 0 }, 0.1, { ...idle, mode: "stay" }, seq(0.1));
  assert.notEqual(s.action, "walk");
  const z = step(initialPet(800), 0.1, { ...idle, mode: "sleep" });
  assert.deepEqual(poseFor(z, "idle", ALL), { pose: "sleep", motion: "doze" });
});

test("the chat drives her: think, talk, happy after a reply, sad after a failure, wave on a click", () => {
  const s = initialPet(800);
  assert.equal(poseFor(step(s, 0.1, { ...idle, activity: "thinking" }), "thinking", ALL).pose, "think");
  assert.equal(poseFor(step(s, 0.1, { ...idle, activity: "talking" }), "talking", ALL).pose, "talk");
  const happy = step(s, 0.1, { ...idle, replied: true });
  assert.equal(poseFor(happy, "idle", ALL).pose, "happy");
  assert.equal(poseFor(step(s, 0.1, { ...idle, failed: true }), "idle", ALL).pose, "sad");
  assert.equal(poseFor(step(s, 0.1, { ...idle, clicked: true }), "idle", ALL).pose, "wave");
  // the reaction lasts, then she goes back to her own business
  assert.equal(step(happy, 1, idle).action, "happy");
  assert.notEqual(step(step(happy, 3, idle), 0.1, idle, seq(0.7)).action, "happy");
});

test("a long quiet puts her to sleep until something happens", () => {
  let s = { ...initialPet(800), quiet: SLEEPY_AFTER, left: 0 };
  s = step(s, 0.1, idle);
  assert.equal(s.action, "sleep");
  assert.equal(step(s, 30, idle).action, "sleep");
  assert.notEqual(step(s, 0.1, { ...idle, activity: "thinking" }).action, "sleep");
});

test("a missing pose falls back to idle; walk alternates its two steps", () => {
  const s = { ...initialPet(800), action: "sit" };
  assert.equal(poseFor(s, "idle", ["idle"]).pose, "idle");
  const walk = { ...initialPet(800), action: "walk" };
  assert.equal(poseFor({ ...walk, clock: 0.1 }, "idle", ALL).pose, "walk_1");
  assert.equal(poseFor({ ...walk, clock: 0.4 }, "idle", ALL).pose, "walk_2");
  assert.equal(poseFor({ ...walk, clock: 0.4 }, "idle", ["idle", "walk_1"]).pose, "walk_1");
});

test("she stays inside the lane", () => {
  const s = step({ ...initialPet(800), x: 5000 }, 0.1, idle);
  assert.equal(s.x, 750);
});

test("stored pet settings are read field by field", () => {
  assert.deepEqual(parsePetPrefs(null), DEFAULT_PET_PREFS);
  assert.deepEqual(parsePetPrefs("junk"), DEFAULT_PET_PREFS);
  assert.deepEqual(parsePetPrefs('{"show":false,"mode":"stay","size":999}'), { show: false, mode: "stay", size: 100 });
  assert.equal(parsePetPrefs('{"mode":"fly"}').mode, "roam");
});

test("the prompt names her and asks for the sheet in the engine's order", () => {
  const p = petPrompt("Luna");
  assert.match(p, /Luna/);
  assert.match(p, /4 columns and 3 rows/);
  assert.equal(POSES.length, 12);
});
