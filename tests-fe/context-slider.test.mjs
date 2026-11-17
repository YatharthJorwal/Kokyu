import { test } from "node:test";
import assert from "node:assert/strict";

import { MIN_CONTEXT, contextDetents, contextLabel, nearestDetent, trackPosition } from "../src/app/context-slider.ts";

// D-098: Chat memory, the model's context length, from 8K up to the model's own maximum.

test("detents double from 8K to the model's maximum", () => {
  assert.equal(MIN_CONTEXT, 8192);
  assert.deepEqual(contextDetents(262144), [8192, 16384, 32768, 65536, 131072, 262144]);
  assert.deepEqual(contextDetents(32768), [8192, 16384, 32768]);
});

test("a maximum that is not a power of two is its own last detent", () => {
  assert.deepEqual(contextDetents(200000), [8192, 16384, 32768, 65536, 131072, 200000]);
  assert.deepEqual(contextDetents(40960), [8192, 16384, 32768, 40960]);
});

test("a small or unknown maximum", () => {
  assert.deepEqual(contextDetents(4096), [4096]);
  assert.deepEqual(contextDetents(8192), [8192]);
  assert.deepEqual(contextDetents(null), []);
  assert.deepEqual(contextDetents(0), []);
  assert.deepEqual(contextDetents(Number.NaN), []);
});

test("labels read like the models' own pages", () => {
  assert.equal(contextLabel(8192), "8K");
  assert.equal(contextLabel(131072), "128K");
  assert.equal(contextLabel(1048576), "1M");
  assert.equal(contextLabel(200000), "200K");
  assert.equal(contextLabel(40960), "40K");
  assert.equal(contextLabel(1_572_864), "1.5M");
  assert.equal(contextLabel(512), "512");
});

test("a value between detents snaps to the nearest by doubling", () => {
  const stops = contextDetents(262144);
  assert.equal(nearestDetent(stops, 8192), 0);
  assert.equal(nearestDetent(stops, 40960), 2); // 40K is nearer 32K than 64K
  assert.equal(nearestDetent(stops, 50000), 3);
  assert.equal(nearestDetent(stops, 999999), 5);
  assert.equal(nearestDetent(stops, null), -1);
  assert.equal(nearestDetent([], 8192), -1);
});

test("the track spaces detents evenly", () => {
  const stops = contextDetents(65536); // 8K 16K 32K 64K
  assert.equal(trackPosition(stops, 8192), 0);
  assert.equal(trackPosition(stops, 16384), 1 / 3);
  assert.equal(trackPosition(stops, 65536), 1);
  assert.ok(Math.abs(trackPosition(stops, 23170) - 0.5) < 0.01); // halfway between 16K and 32K by doubling
  assert.equal(trackPosition([8192], 8192), 0);
});
