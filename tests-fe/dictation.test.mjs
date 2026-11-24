import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_DICTATION_KEY,
  insertDictation,
  isDictationKey,
  keyName,
  keyProblem,
  parseDictationKey,
  recordingTime,
} from "../src/app/dictation.ts";

// D-097: dictation fills the input box and is never sent; F9 toggles it unless the
// user picks another key in Settings.

const k = (key, mods = {}, code) => ({ key, code, ctrlKey: false, altKey: false, shiftKey: false, metaKey: false, ...mods });

test("F9 by default; a function key works alone", () => {
  assert.equal(DEFAULT_DICTATION_KEY, "F9");
  assert.equal(keyName(k("F9")), "F9");
  assert.equal(keyProblem("F9"), null);
  assert.equal(keyProblem("F2"), null);
  assert.equal(keyName(k("F9", { shiftKey: true })), "Shift+F9");
  assert.equal(keyProblem("Shift+F9"), null);
});

test("other keys need Ctrl or Alt, named the same whatever the layout", () => {
  assert.equal(keyName(k("d", { ctrlKey: true, shiftKey: true }, "KeyD")), "Ctrl+Shift+D");
  assert.equal(keyName(k("∂", { altKey: true }, "KeyD")), "Alt+D"); // a Mac-like Alt layer
  assert.equal(keyName(k(" ", { ctrlKey: true }, "Space")), "Ctrl+Space");
  assert.equal(keyName(k("7", { altKey: true }, "Digit7")), "Alt+7");
  assert.equal(keyName(k("m", { metaKey: true }, "KeyM")), "Ctrl+M");
  assert.equal(keyProblem("Ctrl+Shift+D"), null);
  assert.match(keyProblem("D"), /types text/);
  assert.match(keyProblem("Shift+D"), /types text/);
});

test("lone modifiers, Enter, Escape and the window's own shortcuts are refused", () => {
  assert.equal(keyName(k("Control", { ctrlKey: true }, "ControlLeft")), null);
  assert.equal(keyName(k("Enter")), null);
  assert.equal(keyName(k("Escape")), null);
  assert.equal(keyName(k("Tab")), null);
  assert.match(keyProblem(null), /function key/);
  assert.match(keyProblem("Ctrl+N"), /new chat/);
  assert.match(keyProblem("Ctrl+K"), /palette/);
  assert.match(keyProblem("Ctrl+V"), /paste/);
  assert.match(keyProblem("F5"), /reloading/);
  assert.match(keyProblem("F12"), /developer/);
});

test("the key matches only itself, and a held key's repeats do not toggle again", () => {
  assert.equal(isDictationKey(k("F9"), "F9"), true);
  assert.equal(isDictationKey(k("F9", { repeat: true }), "F9"), false);
  assert.equal(isDictationKey(k("F9", { shiftKey: true }), "F9"), false);
  assert.equal(isDictationKey(k("F8"), "F9"), false);
  assert.equal(isDictationKey(k("d", { ctrlKey: true, shiftKey: true }, "KeyD"), "Ctrl+Shift+D"), true);
  assert.equal(isDictationKey(k("F9", { isComposing: true }), "F9"), false);
});

test("a stored key is kept only while it is still usable", () => {
  assert.equal(parseDictationKey(null), "F9");
  assert.equal(parseDictationKey(""), "F9");
  assert.equal(parseDictationKey("F4"), "F4");
  assert.equal(parseDictationKey("Ctrl+Shift+D"), "Ctrl+Shift+D");
  assert.equal(parseDictationKey("Ctrl+N"), "F9");
  assert.equal(parseDictationKey("D"), "F9");
  assert.equal(parseDictationKey("Ctrl+Enter"), "F9");
  assert.equal(parseDictationKey("<script>"), "F9");
});

test("dictated words go in at the caret with spaces around them, replacing a selection", () => {
  assert.deepEqual(insertDictation("", " hello there ", 0), { value: "hello there", caret: 11 });
  assert.deepEqual(insertDictation("I said", "hello", 6), { value: "I said hello", caret: 12 });
  assert.deepEqual(insertDictation("I said ", "hello", 7), { value: "I said hello", caret: 12 });
  assert.deepEqual(insertDictation("Say  now", "it", 4), { value: "Say it now", caret: 6 });
  assert.deepEqual(insertDictation("Hi.", "how are you", 0), { value: "how are you Hi.", caret: 11 });
  assert.deepEqual(insertDictation("Well, ok", "fine", 0, 4), { value: "fine, ok", caret: 4 });
  assert.deepEqual(insertDictation("abc", "", 1), { value: "abc", caret: 1 }); // nothing heard: unchanged
  assert.deepEqual(insertDictation("abc", "x y", 99), { value: "abc x y", caret: 7 }); // a stale caret
  // D-123: never past the box's limit; what does not fit of the words is left out
  assert.deepEqual(insertDictation("abcd", "hello", 4, 4, 8), { value: "abcd hel", caret: 8 });
  assert.equal(insertDictation("x".repeat(10), "more words", 10, 10, 10).value, "x".repeat(10));
});

test("the recording time reads m:ss", () => {
  assert.equal(recordingTime(0), "0:00");
  assert.equal(recordingTime(7.9), "0:07");
  assert.equal(recordingTime(65), "1:05");
});

test("a mic that will not start says why in plain words", async () => {
  const { micProblem } = await import("../src/app/dictation.ts");
  assert.match(micProblem({ name: "NotAllowedError" }), /Privacy & security → Microphone/);
  assert.equal(micProblem({ name: "NotFoundError" }), "No microphone was found.");
  assert.equal(micProblem({ name: "NotReadableError" }), "The microphone is busy in another app.");
  assert.equal(micProblem(new Error("x")), "The microphone could not start.");
  assert.equal(micProblem(null), "The microphone could not start.");
});
