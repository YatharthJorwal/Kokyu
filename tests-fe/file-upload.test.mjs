import { test } from "node:test";
import assert from "node:assert/strict";

import { MAX_PICTURE_BYTES, MAX_TEXT_BYTES, classifyFile, pictureProblem } from "../src/app/file-upload.ts";

const file = (name, type, size = 10) => new File([new Uint8Array(size)], name, { type });

test("only PNG, JPEG, WebP and GIF pass as pictures, within the size limit (D-106)", () => {
  for (const type of ["image/png", "image/jpeg", "image/webp", "image/gif"]) assert.equal(pictureProblem(file("a", type)), null);
  for (const type of ["image/svg+xml", "image/heic", "image/bmp", "image/tiff", ""]) assert.match(pictureProblem(file("a", type)), /PNG, JPEG/);
  assert.match(pictureProblem(file("a.png", "image/png", MAX_PICTURE_BYTES + 1)), /too big/);
  assert.match(pictureProblem(file("a.png", "image/png", 0)), /empty/);
});

test("chat files: pictures by type, text by extension only, each with its own limit", () => {
  assert.equal(classifyFile(file("cat.png", "image/png")).kind, "image");
  assert.equal(classifyFile(file("cat.svg", "image/svg+xml")).kind, "unsupported");
  assert.equal(classifyFile(file("notes.md", "")).kind, "text");
  assert.equal(classifyFile(file("evil.exe", "text/plain")).kind, "unsupported");
  assert.equal(classifyFile(file("README", "text/plain")).kind, "unsupported");
  assert.match(classifyFile(file("big.txt", "text/plain", MAX_TEXT_BYTES + 1)).reason, /too big/);
});
