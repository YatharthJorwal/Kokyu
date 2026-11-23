import { test } from "node:test";
import assert from "node:assert/strict";

import { parseMarkdown } from "../src/app/markdown.ts";

test("a long line of unclosed asterisks parses in linear time (audit)", () => {
  const line = "*a ".repeat(32000 / 3);
  const start = performance.now();
  parseMarkdown(line);
  assert.ok(performance.now() - start < 150, "re-scanned the line once per marker");
});

test("an emphasis after an unclosable marker on the same line still closes", () => {
  const tree = JSON.stringify(parseMarkdown("a ** b *c* d"));
  assert.match(tree, /"t":"em"/);
});
