import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
// The edge build: the Node one does `require("util")`, which the ESM bundle cannot,
// and the browser one opens a MessageChannel at import that keeps the test alive.
import { renderToStaticMarkup } from "react-dom/server.edge";

import {
  EFFORT_LEVELS,
  detents,
  glowFor,
  indexOf,
  levelLabel,
  nearestIndex,
  positionFor,
  stepFor,
} from "../src/app/effort-slider.ts";
import { EffortSlider } from "../src/app/ui/EffortSlider.tsx";

test("detents keep the canonical order and only what the model supports (FR-M-8)", () => {
  assert.deepEqual(EFFORT_LEVELS, ["off", "low", "medium", "high", "max"]);
  assert.deepEqual(detents(["high", "off", "low", "high"]), ["off", "low", "high"]);
  assert.deepEqual(detents(["minimal", "medium"]), ["medium"]); // unknown names are not detents
  assert.deepEqual(detents([]), []);
});

test("the value's place, with the model default off every detent", () => {
  const stops = detents(["off", "low", "high"]);
  assert.equal(indexOf(stops, "low"), 1);
  assert.equal(indexOf(stops, null), -1);
  assert.equal(indexOf(stops, "medium"), -1); // not supported by this model
});

test("keys step between detents and stop at the ends", () => {
  const stops = detents(["off", "low", "medium", "high"]);
  assert.equal(stepFor(stops, "low", "ArrowRight"), "medium");
  assert.equal(stepFor(stops, "low", "ArrowUp"), "medium");
  assert.equal(stepFor(stops, "low", "ArrowLeft"), "off");
  assert.equal(stepFor(stops, "low", "ArrowDown"), "off");
  assert.equal(stepFor(stops, "high", "ArrowRight"), "high");
  assert.equal(stepFor(stops, "off", "ArrowLeft"), "off");
  assert.equal(stepFor(stops, "medium", "Home"), "off");
  assert.equal(stepFor(stops, "low", "End"), "high");
  assert.equal(stepFor(stops, null, "ArrowRight"), "off"); // from the model default
  assert.equal(stepFor(stops, "low", "Enter"), null); // not ours: the popover keeps it
  assert.equal(stepFor([], "low", "ArrowRight"), null);
});

test("thumb position and pointer snapping", () => {
  assert.equal(positionFor(0, 4), 0);
  assert.equal(positionFor(3, 4), 1);
  assert.equal(positionFor(1, 3), 0.5);
  assert.equal(positionFor(0, 1), 0.5); // a single detent sits in the middle
  assert.equal(positionFor(-1, 4), 0);
  assert.equal(nearestIndex(0.4, 4), 1);
  assert.equal(nearestIndex(0.9, 4), 3);
  assert.equal(nearestIndex(-2, 4), 0);
  assert.equal(nearestIndex(7, 4), 3);
  assert.equal(nearestIndex(0.7, 1), 0);
});

test("the glow grows brighter and pulses faster with the level (FR-M-9)", () => {
  assert.deepEqual(glowFor("off"), { intensity: 0, periodS: 0 });
  assert.deepEqual(glowFor(null), { intensity: 0, periodS: 0 });
  const levels = ["low", "medium", "high", "max"].map(glowFor);
  for (let i = 1; i < levels.length; i++) {
    assert.ok(levels[i].intensity > levels[i - 1].intensity);
    assert.ok(levels[i].periodS < levels[i - 1].periodS);
  }
  assert.deepEqual(glowFor("max"), { intensity: 1, periodS: 0.9 });
  assert.deepEqual(glowFor("low"), { intensity: 0.25, periodS: 2.4 });
});

test("labels come from the app", () => {
  assert.equal(levelLabel("off"), "No thinking");
  assert.equal(levelLabel("high"), "High");
  assert.equal(levelLabel("max"), "Max");
  assert.equal(levelLabel(null), "Model default");
});

const render = (props) =>
  renderToStaticMarkup(createElement(EffortSlider, { onChange: () => {}, ...props }));

test("no supported level means no slider", () => {
  assert.equal(render({ supported: [], value: null }), "");
});

test("the slider is an accessible slider over detent indexes", () => {
  const html = render({ supported: ["off", "low", "medium", "high"], value: "medium" });
  assert.match(html, /role="slider"/);
  assert.match(html, /tabindex="0"/);
  assert.match(html, /aria-valuemin="0"/);
  assert.match(html, /aria-valuemax="3"/);
  assert.match(html, /aria-valuenow="2"/);
  assert.match(html, /aria-valuetext="Medium"/);
  assert.match(html, /data-level="medium"/);
  // ticks for the inner levels only: no dots at the track's ends (D-097)
  assert.equal((html.match(/class="effort-stop/g) ?? []).length, 2);
  assert.equal((html.match(/effort-stop on/g) ?? []).length, 2); // low and medium
  assert.match(html, /effort-thumb/);
  assert.doesNotMatch(html, / still/); // medium pulses
});

test("the model default shows no thumb and no value, and off does not pulse", () => {
  const unset = render({ supported: ["off", "high"], value: null });
  assert.doesNotMatch(unset, /aria-valuenow/);
  assert.match(unset, /aria-valuetext="Model default"/);
  assert.doesNotMatch(unset, /effort-thumb/);
  assert.match(render({ supported: ["off", "high"], value: "off" }), /effort-slider still/);
  assert.doesNotMatch(render({ supported: ["off", "high"], value: "high" }), /effort-stop/); // two levels: no ticks
});

test("reduced motion is a class the CSS turns static", () => {
  assert.match(render({ supported: ["low", "high"], value: "high", reducedMotion: true }), /effort-slider reduced/);
});
