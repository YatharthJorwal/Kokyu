import { test } from "node:test";
import assert from "node:assert/strict";

import { highlight, languageLabel } from "../src/app/highlight.ts";
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
  assert.deepEqual(blocks[2].items[1], { c: [{ t: "text", v: "two " }, { t: "code", v: "x" }], blocks: [] });
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
  // a fence inside a list item is that item's code block (UI1-08), and the list goes on
  const listed = parseMarkdown(["1. Run this:", "   ```bash", "   npm i", "   ```", "2. Then this"].join("\n"));
  assert.deepEqual(listed.map((b) => b.t), ["list"]);
  assert.deepEqual(listed[0].items[0].blocks, [{ t: "code", lang: "bash", v: "npm i", open: false }]);
  assert.equal(listed[0].items.length, 2);
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

// UI1-08 (D-093): tables, nested lists, coloured code

const text = (v) => ({ t: "text", v });

test("a GitHub-style table: header, alignment, rows fitted to the header, escaped pipes", () => {
  const [intro, table, after] = parseMarkdown(
    ["Prices:", "| Item | Cost | Note |", "|:-----|-----:|:----:|", "| tea | 2 | a \\| b |", "| cake | 4 |", "| x | 1 | y | extra |", "", "Done."].join("\n"),
  );
  assert.equal(intro.t, "p");
  assert.equal(table.t, "table");
  assert.deepEqual(table.align, ["left", "right", "center"]);
  assert.deepEqual(table.head, [[text("Item")], [text("Cost")], [text("Note")]]);
  assert.deepEqual(table.rows[0][2], [text("a | b")]);
  assert.deepEqual(table.rows[1][2], []); // a short row is padded
  assert.equal(table.rows[2].length, 3); // a long row is cut to the header
  assert.equal(after.t, "p");
});

test("not a table: pipes without a rule, or a rule with the wrong number of cells", () => {
  assert.deepEqual(parseMarkdown("a | b\nc | d").map((b) => b.t), ["p"]);
  assert.deepEqual(parseMarkdown("| a | b |\n|---|").map((b) => b.t), ["p"]);
  // a header still streaming in, before its rule, is text for now
  assert.deepEqual(parseMarkdown("| a | b |").map((b) => b.t), ["p"]);
});

test("nested lists: indented items belong to the item above, at any depth", () => {
  const [list] = parseMarkdown(["- fruit", "  - apple", "    - green", "  - pear", "- veg", "\t1. leek"].join("\n"));
  assert.equal(list.items.length, 2);
  const [fruit, veg] = list.items;
  assert.deepEqual(fruit.c, [text("fruit")]);
  const sub = fruit.blocks[0];
  assert.equal(sub.t, "list");
  assert.deepEqual(sub.items.map((it) => it.c), [[text("apple")], [text("pear")]]);
  assert.deepEqual(sub.items[0].blocks[0].items[0].c, [text("green")]);
  assert.deepEqual([veg.blocks[0].ordered, veg.blocks[0].items[0].c], [true, [text("leek")]]);
});

test("a loose list stays one list; a continuation line stays in its item", () => {
  const [list] = parseMarkdown(["1. first", "   more of it", "", "2. second", "", "Next paragraph"].join("\n"));
  assert.equal(list.items.length, 2);
  assert.deepEqual(list.items[0].c, [text("first"), { t: "br" }, text("more of it")]);
  assert.equal(parseMarkdown(["1. first", "", "2. second", "", "Next paragraph"].join("\n")).length, 2);
});

test("hostile list nesting stays cheap and never throws", () => {
  const deep = Array.from({ length: 400 }, (_, n) => " ".repeat(n * 2) + "- x").join("\n");
  assert.doesNotThrow(() => parseMarkdown(deep));
});

test("code colouring: keywords, strings, comments, numbers, calls; unknown languages stay plain", () => {
  const kinds = (code, lang) => highlight(code, lang).filter((t) => t.k).map((t) => [t.k, t.v]);
  assert.deepEqual(kinds('const n = 42; // why\nprint("hi")', "js"), [
    ["kw", "const"],
    ["num", "42"],
    ["com", "// why"],
    ["fn", "print"],
    ["str", '"hi"'],
  ]);
  assert.deepEqual(kinds('def f():\n    """doc\n    more"""\n    return None', "py"), [
    ["kw", "def"],
    ["fn", "f"],
    ["str", '"""doc\n    more"""'],
    ["kw", "return"],
    ["lit", "None"],
  ]);
  assert.deepEqual(kinds("echo $HOME # note\ncurl a#b", "bash"), [["kw", "echo"], ["fn", "$HOME"], ["com", "# note"]]);
  assert.deepEqual(kinds('{"a": 1, "b": "x", "c": true}', "json"), [
    ["fn", '"a"'],
    ["num", "1"],
    ["fn", '"b"'],
    ["str", '"x"'],
    ["fn", '"c"'],
    ["lit", "true"],
  ]);
  assert.deepEqual(kinds('<div class="a"><!-- c --></div>', "html"), [
    ["kw", "div"],
    ["str", '"a"'],
    ["com", "<!-- c -->"],
    ["kw", "div"],
  ]);
  assert.deepEqual(highlight("whatever 1 2", "brainfudge"), [{ k: "", v: "whatever 1 2" }]);
  // the text always comes back whole, an unclosed string included (a reply still streaming)
  for (const [code, lang] of [["x = 'open", "py"], ["/* never closed", "ts"], ['"a\\"b" c', "js"]]) {
    assert.equal(highlight(code, lang).map((t) => t.v).join(""), code);
  }
});

test("a code block's header names its language", () => {
  assert.equal(languageLabel("py"), "Python");
  assert.equal(languageLabel("TSX"), "TSX");
  assert.equal(languageLabel("zig"), "zig");
  assert.equal(languageLabel(""), "Code");
});
