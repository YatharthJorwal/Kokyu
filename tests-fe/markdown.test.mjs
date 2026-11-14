import { test } from "node:test";
import assert from "node:assert/strict";

import { parseInline, parseMarkdown, safeHref } from "../src/app/markdown.ts";

// K1-04 (FR-C-8): replies render as Markdown, never as raw HTML.

test("blocks: paragraphs, headings, lists, quotes, rules and code fences", () => {
  const md = [
    "# Title",
    "Some *soft* and **bold** text",
    "on two lines.",
    "",
    "- one",
    "- two `x`",
    "",
    "3. third",
    "4. fourth",
    "",
    "> quoted",
    "",
    "---",
    "```py",
    "print('<b>hi</b>')",
    "```",
  ].join("\n");
  const blocks = parseMarkdown(md);
  assert.deepEqual(
    blocks.map((b) => b.t),
    ["h", "p", "list", "list", "quote", "hr", "code"],
  );
  assert.deepEqual(blocks[0], { t: "h", level: 1, c: [{ t: "text", v: "Title" }] });
  assert.deepEqual(blocks[1].c, [
    { t: "text", v: "Some " },
    { t: "em", c: [{ t: "text", v: "soft" }] },
    { t: "text", v: " and " },
    { t: "strong", c: [{ t: "text", v: "bold" }] },
    { t: "text", v: " text" },
    { t: "br" },
    { t: "text", v: "on two lines." },
  ]);
  assert.equal(blocks[2].ordered, false);
  assert.deepEqual(blocks[2].items[1], [{ t: "text", v: "two " }, { t: "code", v: "x" }]);
  assert.deepEqual([blocks[3].ordered, blocks[3].start, blocks[3].items.length], [true, 3, 2]);
  assert.deepEqual(blocks[4].c, [{ t: "p", c: [{ t: "text", v: "quoted" }] }]);
  // HTML inside code stays text; the renderer never sets innerHTML
  assert.deepEqual(blocks[6], { t: "code", lang: "py", v: "print('<b>hi</b>')", open: false });
});

test("a reply still streaming: an unclosed fence is code so far, marked open", () => {
  const [p, code] = parseMarkdown("Here:\n```js\nconst a = 1;\n");
  assert.equal(p.t, "p");
  assert.deepEqual(code, { t: "code", lang: "js", v: "const a = 1;\n", open: true });
});

test("links: only http(s) and mailto become links; bare URLs too", () => {
  assert.deepEqual(parseInline("[docs](https://example.com/a)"), [
    { t: "link", href: "https://example.com/a", c: [{ t: "text", v: "docs" }] },
  ]);
  assert.deepEqual(parseInline("[x](javascript:alert(1))"), [{ t: "text", v: "[x](javascript:alert(1))" }]);
  assert.equal(safeHref("data:text/html,hi"), null);
  assert.equal(safeHref("MAILTO:a@b.c"), "MAILTO:a@b.c");
  assert.deepEqual(parseInline("see https://example.com/x."), [
    { t: "text", v: "see " },
    { t: "link", href: "https://example.com/x", c: [{ t: "text", v: "https://example.com/x" }] },
    { t: "text", v: "." },
  ]);
});

test("ordinary text is left alone", () => {
  // snake_case, a lone asterisk, maths and escapes are not emphasis
  assert.deepEqual(parseInline("use snake_case_names"), [{ t: "text", v: "use snake_case_names" }]);
  assert.deepEqual(parseInline("2 * 3 = 6"), [{ t: "text", v: "2 * 3 = 6" }]);
  assert.deepEqual(parseInline("\\*not em\\*"), [{ t: "text", v: "*not em*" }]);
  assert.deepEqual(parseInline("an `unclosed tick"), [{ t: "text", v: "an `unclosed tick" }]);
  assert.deepEqual(parseMarkdown(""), []);
});

test("review findings: fences in lists, info strings, C#, deep nesting, parenthesised links", () => {
  // a fence inside a list item opens a code block instead of flipping every later fence
  const listed = parseMarkdown(["1. Run this:", "   ```bash", "   npm i", "   ```", "2. Then this"].join("\n"));
  assert.deepEqual(listed.map((b) => b.t), ["list", "code", "list"]);
  // the language is the info string's first word
  const titled = parseMarkdown(['```python title="a.py"', "x = 1", "```", "after"].join("\n"));
  assert.deepEqual(titled.map((b) => [b.t, b.lang]), [["code", "python"], ["p", undefined]]);
  // a closing # sequence goes; a # that is part of the word stays
  assert.deepEqual(parseMarkdown("## C#")[0].c, [{ t: "text", v: "C#" }]);
  assert.deepEqual(parseMarkdown("## Title ##")[0].c, [{ t: "text", v: "Title" }]);
  // hostile nesting comes back as text instead of overflowing the stack
  assert.doesNotThrow(() => parseMarkdown("*".repeat(20000) + "x" + "*".repeat(20000)));
  assert.doesNotThrow(() => parseMarkdown(">".repeat(20000) + " deep"));
  // one level of parentheses belongs to the address; sentence punctuation does not
  const wiki = "https://en.wikipedia.org/wiki/Foo_(bar)";
  assert.equal(parseInline(`[Foo](${wiki})`)[0].href, wiki);
  assert.equal(parseInline(`see ${wiki}.`)[1].href, wiki);
  assert.equal(parseInline("(https://x.com)")[1].href, "https://x.com");
});
