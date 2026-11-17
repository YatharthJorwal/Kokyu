import { test } from "node:test";
import assert from "node:assert/strict";

import { parseInline, parseMarkdown } from "../src/app/markdown.ts";
import { EMPTY_FORM, cardFromForm, formFromCard, isBlankCard, sameCard, SCENARIO_FIELDS } from "../src/app/scenario.ts";

// K1c-08 (FR-MODE-7): roleplay threads render *actions* and out-of-character asides
// their own way; chat threads keep ordinary Markdown (FR-C-8).

const RP = { roleplay: true };
const text = (v) => ({ t: "text", v });

test("roleplay parsing: actions, bold, asides (FR-MODE-7)", () => {
  const table = [
    ['*smiles* "Hi."', [{ t: "action", c: [text("smiles")] }, text(' "Hi."')]],
    ["**Stop.** *grabs your arm*", [{ t: "strong", c: [text("Stop.")] }, text(" "), { t: "action", c: [text("grabs your arm")] }]],
    // bold inside an action belongs to it; the inner ** never closes the action
    ["*she says **loudly** hi*", [{ t: "action", c: [text("she says "), { t: "strong", c: [text("loudly")] }, text(" hi")] }]],
    ["*She leans in, **very** close.*", [{ t: "action", c: [text("She leans in, "), { t: "strong", c: [text("very")] }, text(" close.")] }]],
    // _…_ stays ordinary emphasis: only asterisks mark an action
    ["_softly_", [{ t: "em", c: [text("softly")] }]],
    ["(OOC: brb) ok", [{ t: "ooc", c: [text("(OOC: brb)")] }, text(" ok")]],
    ["(ooc - can we skip ahead?)", [{ t: "ooc", c: [text("(ooc - can we skip ahead?)")] }]],
    ["((back in 5))", [{ t: "ooc", c: [text("((back in 5))")] }]],
    // nested parentheses inside a ((…)) aside belong to it
    ["((this is (very) nested)) yes", [{ t: "ooc", c: [text("((this is (very) nested))")] }, text(" yes")]],
    // an action may hold an aside
    ["*waves (OOC: lol)*", [{ t: "action", c: [text("waves "), { t: "ooc", c: [text("(OOC: lol)")] }] }]],
    // inside an aside, ordinary Markdown: *x* is emphasis, not an action
    ["((*sigh* fine))", [{ t: "ooc", c: [text("(("), { t: "em", c: [text("sigh")] }, text(" fine))")] }]],
    // ordinary parentheses are not asides, in a story either
    ["she hums (badly)", [text("she hums (badly)")]],
    ["install it (with pip)", [text("install it (with pip)")]],
    // a ((…)) that does not close with )) is not an aside
    ["((a) b)", [text("((a) b)")]],
    // still streaming: an unclosed aside or action stays text until it closes
    ["(OOC still typing", [text("(OOC still typing")]],
    ["*she smi", [text("*she smi")]],
    // an escaped parenthesis is text
    ["\\(OOC x)", [text("(OOC x)")]],
    // an aside does not run across lines
    ["(OOC one\ntwo)", [text("(OOC one"), { t: "br" }, text("two)")]],
  ];
  for (const [input, expected] of table) assert.deepEqual(parseInline(input, RP), expected, input);
});

test("chat parsing is unchanged: parentheses stay text, *x* stays emphasis (FR-MODE-7, FR-C-8)", () => {
  assert.deepEqual(parseInline("install it (with pip)"), [text("install it (with pip)")]);
  assert.deepEqual(parseInline("(OOC: brb)"), [text("(OOC: brb)")]);
  assert.deepEqual(parseInline("((back in 5))"), [text("((back in 5))")]);
  assert.deepEqual(parseInline("*smiles*"), [{ t: "em", c: [text("smiles")] }]);
  assert.deepEqual(parseMarkdown("*smiles*", {}), parseMarkdown("*smiles*"));
});

test("roleplay options reach every block: lists, quotes, headings (FR-MODE-7)", () => {
  const [list, quote] = parseMarkdown("- *nods*\n\n> (OOC: aside)", RP);
  assert.deepEqual(list.items[0].c, [{ t: "action", c: [text("nods")] }]);
  assert.deepEqual(quote.c[0].c, [{ t: "ooc", c: [text("(OOC: aside)")] }]);
  assert.deepEqual(parseMarkdown("## *bows*", RP)[0].c, [{ t: "action", c: [text("bows")] }]);
});

test("hostile asides stay cheap and never throw (FR-MODE-7)", () => {
  const started = Date.now();
  assert.doesNotThrow(() => parseMarkdown("(".repeat(20000), RP));
  assert.doesNotThrow(() => parseMarkdown("((".repeat(10000) + "x" + "))".repeat(10000), RP));
  assert.doesNotThrow(() => parseMarkdown("(OOC ".repeat(5000), RP));
  assert.ok(Date.now() - started < 5000);
});

// FR-MODE-6: the New roleplay dialog's card.

test("a form becomes a card of its filled-in, trimmed fields", () => {
  const form = { ...EMPTY_FORM, title: "  Rainy café ", setting: "", rules: "   ", opening: "*looks up* Oh, it's you." };
  assert.deepEqual(cardFromForm(form), { title: "Rainy café", opening: "*looks up* Oh, it's you." });
  assert.equal(isBlankCard(cardFromForm(EMPTY_FORM)), true);
  assert.equal(isBlankCard(cardFromForm({ ...EMPTY_FORM, rules: "  " })), true);
  assert.equal(isBlankCard(cardFromForm(form)), false);
});

test("a card's fields are cut to the kernel's limits", () => {
  const long = cardFromForm({ ...EMPTY_FORM, title: "t".repeat(500), opening: "o".repeat(9000), setting: "s".repeat(3000) });
  assert.equal(long.title.length, 120);
  assert.equal(long.opening.length, 4000);
  assert.equal(long.setting.length, 2000);
});

test("a saved card fills the form; the dialog's fields are the card's, in order", () => {
  assert.deepEqual(
    SCENARIO_FIELDS.map((f) => f.key),
    ["title", "setting", "user_role", "her_role", "opening", "rules"],
  );
  assert.deepEqual(formFromCard({ title: "A", her_role: "your rival" }), { ...EMPTY_FORM, title: "A", her_role: "your rival" });
  assert.equal(sameCard({ title: "A" }, { title: "A ", setting: "" }), true);
  assert.equal(sameCard({ title: "A" }, { title: "B" }), false);
});
