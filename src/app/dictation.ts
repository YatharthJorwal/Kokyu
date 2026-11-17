// Dictation (D-097): the mic button, or its key (F9 unless changed in Settings),
// records what the user says; the engine writes it down on this PC (faster-whisper on
// the CPU) and the words go into the input box at the caret. Nothing is ever sent by
// itself. The key works while the window has focus; a system-wide one can come later.
// Pure functions, tested in Node; the recorder and the key's storage are elsewhere.

export const DEFAULT_DICTATION_KEY = "F9";

/** A recording stops by itself after this long. */
export const MAX_DICTATION_S = 120;

/** A keydown as the parts that name a key binding. */
export interface KeyLike {
  key: string;
  code?: string;
  ctrlKey: boolean;
  metaKey?: boolean;
  altKey: boolean;
  shiftKey: boolean;
  repeat?: boolean;
  isComposing?: boolean;
}

/** Keys the window or the webview already uses: never a dictation key. */
const TAKEN: Record<string, string> = {
  "Ctrl+N": "new chat",
  "Ctrl+K": "the palette",
  "Ctrl+A": "select all",
  "Ctrl+C": "copy",
  "Ctrl+V": "paste",
  "Ctrl+X": "cut",
  "Ctrl+Z": "undo",
  "Ctrl+Y": "redo",
  F5: "reloading the window",
  F12: "the developer tools",
};

const MODIFIERS = new Set(["Control", "Shift", "Alt", "Meta", "AltGraph", "CapsLock", "OS"]);

/** The base key's name: F1..F12, a letter, a digit or Space; null for anything else. */
function baseKey(e: KeyLike): string | null {
  if (/^F([1-9]|1[0-2])$/.test(e.key)) return e.key;
  const code = e.code ?? "";
  const letter = /^Key([A-Z])$/.exec(code)?.[1] ?? (/^[a-z]$/i.test(e.key) ? e.key.toUpperCase() : null);
  if (letter) return letter;
  const digit = /^Digit([0-9])$/.exec(code)?.[1] ?? (/^[0-9]$/.test(e.key) ? e.key : null);
  if (digit) return digit;
  if (code === "Space" || e.key === " ") return "Space";
  return null;
}

/** The binding a keydown names, as stored and shown ("F9", "Ctrl+Shift+D"), or null
 * for a lone modifier or a key that is not one (Enter, Escape, Tab, arrows…). */
export function keyName(e: KeyLike): string | null {
  if (MODIFIERS.has(e.key)) return null;
  const base = baseKey(e);
  if (!base) return null;
  const parts: string[] = [];
  if (e.ctrlKey || e.metaKey) parts.push("Ctrl");
  if (e.altKey) parts.push("Alt");
  if (e.shiftKey) parts.push("Shift");
  return [...parts, base].join("+");
}

/** Why a key cannot start dictation, or null when it can. A function key works on
 * its own; anything else needs Ctrl or Alt, or typing it would dictate. */
export function keyProblem(name: string | null): string | null {
  if (!name) return "Press a function key (F1 to F12), or a letter or digit with Ctrl or Alt.";
  if (TAKEN[name]) return `${name} is already used for ${TAKEN[name]}.`;
  const parts = name.split("+");
  const base = parts[parts.length - 1];
  if (/^F\d+$/.test(base)) return null;
  if (!parts.includes("Ctrl") && !parts.includes("Alt")) return `${name} types text. Add Ctrl or Alt, or use a function key.`;
  return null;
}

/** This keydown is the dictation key (a held key's repeats are not). */
export function isDictationKey(e: KeyLike, name: string): boolean {
  return !e.repeat && !e.isComposing && keyName(e) === name;
}

/** A stored binding, or the default when there is none or it is no longer usable. */
export function parseDictationKey(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_DICTATION_KEY;
  const name = raw.trim();
  return /^((Ctrl|Alt|Shift)\+)*(F([1-9]|1[0-2])|[A-Z0-9]|Space)$/.test(name) && keyProblem(name) === null
    ? name
    : DEFAULT_DICTATION_KEY;
}

/** The input box after dictated words replace the selection [start, end): a space
 * keeps them apart from the words around them. `caret` is where they end. */
export function insertDictation(value: string, words: string, start: number, end: number = start): { value: string; caret: number } {
  const said = words.trim();
  const from = Math.max(0, Math.min(start, value.length));
  const to = Math.max(from, Math.min(end, value.length));
  if (!said) return { value, caret: to };
  const before = value.slice(0, from);
  const after = value.slice(to);
  const lead = before && !/\s$/.test(before) ? " " : "";
  const trail = after && !/^[\s.,;:!?)]/.test(after) ? " " : "";
  const next = before + lead + said + trail + after;
  return { value: next, caret: (before + lead + said).length };
}

/** "0:07": how long the recording has run. */
export function recordingTime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** What to tell the user when the mic would not start (getUserMedia's error). */
export function micProblem(err: unknown): string {
  const name = typeof err === "object" && err !== null && "name" in err ? String((err as { name: unknown }).name) : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Kōkyū may not use the microphone. Allow it in Windows Settings → Privacy & security → Microphone.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No microphone was found.";
  if (name === "NotReadableError") return "The microphone is busy in another app.";
  return "The microphone could not start.";
}
