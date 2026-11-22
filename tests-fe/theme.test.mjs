import { test } from "node:test";
import assert from "node:assert/strict";

import { DEFAULT_THEME, PRESETS, inkFor, parseTheme, themeVars } from "../src/app/theme.ts";

test("a stored theme is read field by field; junk falls back to the default (D-073)", () => {
  assert.deepEqual(parseTheme(null), DEFAULT_THEME);
  assert.deepEqual(parseTheme("not json"), DEFAULT_THEME);
  assert.deepEqual(parseTheme('"a string"'), DEFAULT_THEME);
  assert.deepEqual(
    parseTheme('{"preset":"midnight","accent":"#ABCDEF","messages":"bubbles","size":"large"}'),
    { preset: "midnight", accent: "#abcdef", messages: "bubbles", size: "large", glow: null },
  );
  // an unknown preset, a CSS injection in the accent, an unknown size
  assert.deepEqual(
    parseTheme('{"preset":"neon","accent":"red;}body{display:none","messages":"bubbles","size":"huge"}'),
    { ...DEFAULT_THEME, messages: "bubbles" },
  );
});

test("text on the accent is dark on a light accent and white on a dark one", () => {
  assert.equal(inkFor("#a8b4ff"), "#1a1320");
  assert.equal(inkFor("#2a2a8a"), "#ffffff");
});

test("a theme sets its preset's colors, the accent, its ink and the chat text size", () => {
  const vars = themeVars({ preset: "light", accent: null, messages: "open", size: "small" });
  assert.equal(vars["--bg"], PRESETS.light.vars["--bg"]);
  assert.equal(vars["--accent"], PRESETS.light.vars["--accent"]);
  assert.equal(vars["--chat-size"], "14px");
  const custom = themeVars({ preset: "midnight", accent: "#8fd4a4", messages: "open", size: "normal" });
  assert.equal(custom["--accent"], "#8fd4a4");
  assert.equal(custom["--on-accent"], "#1a1320");
  // every preset sets the same variables, so switching never leaves one behind
  const names = (p) => Object.keys(PRESETS[p].vars).sort().join();
  assert.equal(names("kokyu"), names("midnight"));
  assert.equal(names("kokyu"), names("light"));
});

test("her name and lit icons stay readable whatever the accent (D-112)", async () => {
  const { accentText, contrast } = await import("../src/app/theme.ts");
  assert.ok(contrast("#ffffff", "#000000") > 20);
  assert.equal(accentText("#ffffff", PRESETS.light.vars["--bg"], PRESETS.light.vars["--text"]), PRESETS.light.vars["--text"]);
  assert.equal(accentText("#d3477e", PRESETS.light.vars["--bg"], PRESETS.light.vars["--text"]), "#d3477e");
  const vars = themeVars({ preset: "light", accent: "#fafafa", messages: "open", size: "normal" });
  assert.equal(vars["--accent-text"], PRESETS.light.vars["--text"]);
});

test("every preset reads: text 7:1 and accent 3:1 on its background (D-113)", async () => {
  const { contrast } = await import("../src/app/theme.ts");
  for (const [id, p] of Object.entries(PRESETS)) {
    assert.ok(contrast(p.vars["--text"], p.vars["--bg"]) >= 7, `${id} text`);
    assert.ok(contrast(p.vars["--accent"], p.vars["--bg"]) >= 3, `${id} accent`);
    assert.ok(contrast(p.vars["--muted"], p.vars["--bg"]) >= 3, `${id} muted`);
  }
});
