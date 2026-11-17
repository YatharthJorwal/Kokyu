import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server.edge";

import { parseInline, parseMarkdown } from "../src/app/markdown.ts";
import { Markdown } from "../src/app/ui/Markdown.tsx";

// D-097 (FR-C-8): her [emotion] tags stay in the text (the Luna and Yuri shells
// drive her expressions from them) and are shown muted and italic, like a
// roleplay *action*, in Chat and in Roleplay. A link [x](url) is never a tag.

const text = (v) => ({ t: "text", v });
const tag = (v) => ({ t: "tag", v });

test("a bracketed word is a tag in chat and in roleplay", () => {
  const line = "What? You think you can order me around like a database? [angry]";
  const expected = [text("What? You think you can order me around like a database? "), tag("[angry]")];
  assert.deepEqual(parseInline(line), expected);
  assert.deepEqual(parseInline(line, { roleplay: true }), expected);
  assert.deepEqual(parseInline("[teasing] Oh, really?"), [tag("[teasing]"), text(" Oh, really?")]);
  assert.deepEqual(parseInline("Fine.[sad]"), [text("Fine."), tag("[sad]")]);
});

test("tags of a few words, any case, with hyphens or apostrophes", () => {
  assert.deepEqual(parseInline("[Happy]"), [tag("[Happy]")]);
  assert.deepEqual(parseInline("[softly smiling]"), [tag("[softly smiling]")]);
  assert.deepEqual(parseInline("[half-asleep]"), [tag("[half-asleep]")]);
  assert.deepEqual(parseInline("[can't stop grinning]"), [tag("[can't stop grinning]")]);
});

test("links are never tags, nor are numbers, checkboxes, empty or long brackets", () => {
  assert.deepEqual(parseInline("[docs](https://example.com)"), [
    { t: "link", href: "https://example.com", c: [text("docs")] },
  ]);
  // an unsafe address stays text, and still not a tag
  assert.deepEqual(parseInline("[click](javascript:alert(1))"), [text("[click](javascript:alert(1))")]);
  assert.deepEqual(parseInline("see [1] and [x] and []"), [text("see [1] and [x] and []")]);
  assert.deepEqual(parseInline("arr[i] = 2"), [text("arr[i] = 2")]);
  assert.deepEqual(parseInline("use items[index] here"), [text("use items[index] here")]);
  assert.deepEqual(parseInline("[ref]: https://example.com"), [text("[ref]: "), { t: "link", href: "https://example.com", c: [text("https://example.com")] }]);
  const long = "[" + "a".repeat(25) + "]";
  assert.deepEqual(parseInline(long), [text(long)]);
  assert.deepEqual(parseInline("[angry"), [text("[angry")]);
  assert.deepEqual(parseInline("[two\nlines]"), [text("[two"), { t: "br" }, text("lines]")]);
});

test("a tag inside code stays code; inside an action or bold it is still a tag", () => {
  assert.deepEqual(parseInline("`[angry]`"), [{ t: "code", v: "[angry]" }]);
  assert.deepEqual(parseMarkdown("```\n[angry]\n```")[0], { t: "code", lang: "", v: "[angry]", open: false });
  assert.deepEqual(parseInline("*pouts [sad]*", { roleplay: true }), [{ t: "action", c: [text("pouts "), tag("[sad]")] }]);
  assert.deepEqual(parseInline("**no [angry]**"), [{ t: "strong", c: [text("no "), tag("[angry]")] }]);
});

test("an escaped bracket is text", () => {
  assert.deepEqual(parseInline("\\[angry]"), [text("[angry]")]);
});

test("rendered muted and italic, like an action, with the brackets kept", () => {
  const chat = renderToStaticMarkup(createElement(Markdown, { text: "No. [angry]\n\nFine, *maybe*." }));
  assert.match(chat, /<em class="emotion-tag">\[angry\]<\/em>/);
  const rp = renderToStaticMarkup(createElement(Markdown, { text: '*smirks* "Sure." [teasing]', roleplay: true }));
  assert.match(rp, /<em class="rp-action">smirks<\/em>/);
  assert.match(rp, /<em class="emotion-tag">\[teasing\]<\/em>/);
});
