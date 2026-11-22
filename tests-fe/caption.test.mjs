import { test } from "node:test";
import assert from "node:assert/strict";

import { TRAIL_WORDS, activeWord, splitWords, wordStarts, wordState } from "../src/app/caption.ts";
import { DEFAULT_GLOW, parseTheme, themeVars } from "../src/app/theme.ts";

test("each word gets a share of the clip by its length (D-111)", () => {
  const words = splitWords("  a  bb cccc ");
  assert.deepEqual(words, ["a", "bb", "cccc"]);
  assert.deepEqual(wordStarts(words), [0, 1 / 7, 3 / 7]);
  assert.equal(activeWord(wordStarts(words), 0), 0);
  assert.equal(activeWord(wordStarts(words), 0.2), 1);
  assert.equal(activeWord(wordStarts(words), 1), 2);
});

test("the said word glows, the few behind it dim, older ones fold away", () => {
  assert.equal(wordState(5, 5), "active");
  assert.equal(wordState(6, 5), "hidden");
  assert.equal(wordState(5 - TRAIL_WORDS, 5), "spoken");
  assert.equal(wordState(4 - TRAIL_WORDS, 5), "fading");
});

test("the caption's glow is a stored color, checked like the accent", () => {
  assert.equal(parseTheme('{"glow":"#A0B0C0"}').glow, "#a0b0c0");
  assert.equal(parseTheme('{"glow":"red;}x{"}').glow, null);
  assert.equal(themeVars(parseTheme(null))["--caption-glow"], DEFAULT_GLOW);
  assert.equal(themeVars(parseTheme('{"glow":"#a0b0c0"}'))["--caption-glow"], "#a0b0c0");
});

test("without her voice a reply becomes sentence lines, paced like speech (D-113)", async () => {
  const { sentences, silentDuration } = await import("../src/app/caption.ts");
  assert.deepEqual(sentences("*smiles* Hi there! How are you?\n\nI'm fine… ok"), ["Hi there!", "How are you?", "I'm fine…", "ok"]);
  assert.deepEqual(sentences("  ...  "), []);
  assert.equal(silentDuration("Hi"), 1.6);
  assert.ok(silentDuration("x".repeat(100)) > 6);
});
