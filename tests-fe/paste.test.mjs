import { test } from "node:test";
import assert from "node:assert/strict";

import { pasteNote, pasteOverflow } from "../src/app/paste.ts";

// D-123: a paste over a field's limit is said, never cut without a word.
test("what a paste loses is the text kept plus the paste, past the limit", () => {
  assert.equal(pasteOverflow(0, 0, 25_000, 20_000), 5_000);
  assert.equal(pasteOverflow(19_990, 0, 5, 20_000), 0); // fits
  assert.equal(pasteOverflow(19_990, 100, 105, 20_000), 0); // replaces a selection: fits
  assert.equal(pasteOverflow(10, 0, 5_000, -1), 0); // no maxLength
  assert.equal(pasteNote(25_000, 5_000, 20_000), "Only 20,000 of the 25,000 pasted characters fit. The limit here is 20,000.");
});
