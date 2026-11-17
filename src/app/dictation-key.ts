// The dictation key (D-097), kept by this page in localStorage like Appearance
// (D-073): the key works inside the window, so the engine never needs it. Settings →
// Voice changes it; the composer listens for it.

import { create } from "zustand";

import { DEFAULT_DICTATION_KEY, parseDictationKey } from "./dictation";

const STORAGE_KEY = "kokyu.dictationKey";

function load(): string {
  try {
    return parseDictationKey(localStorage.getItem(STORAGE_KEY));
  } catch {
    return DEFAULT_DICTATION_KEY; // no storage (a test, a locked-down webview)
  }
}

export const useDictationKey = create<{ key: string }>(() => ({ key: load() }));

/** Use `key` from now on, and remember it. The caller checked it (keyProblem). */
export function setDictationKey(key: string): void {
  useDictationKey.setState({ key });
  try {
    localStorage.setItem(STORAGE_KEY, key);
  } catch {
    // kept for this run only
  }
}
