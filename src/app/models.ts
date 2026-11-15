// The model chip's pure helpers (K1-10; FR-M-1..7, D-054): filtering the
// picker's rows, short labels, sizes, and the "waking up" lines shown while the
// kernel loads the chat model. No React, no DOM: tested in Node.

import type { ModelRow } from "../net/protocol";

/** `local:ollama/qwen3.5:9b` -> `qwen3.5:9b`. */
export function shortRef(ref: string): string {
  const m = /^[a-z]+:[a-z][a-z0-9_]*\/(.+)$/.exec(ref);
  return m ? m[1] : ref;
}

export function isLocalRef(ref: string | null): boolean {
  return ref === null || ref.startsWith("local:");
}

/** Every word of the query must appear in the label, reference or detail. */
export function filterRows(rows: ModelRow[], query: string): ModelRow[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return rows;
  return rows.filter((r) => {
    const hay = `${r.label} ${r.ref} ${r.detail ?? ""} ${(r.tags ?? []).join(" ")}`.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

export function formatSize(bytes: number | null | undefined): string | null {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes) || bytes <= 0) return null;
  const gb = bytes / 1e9;
  if (gb >= 1) return `${gb >= 10 ? Math.round(gb) : gb.toFixed(1)} GB`;
  return `${Math.max(1, Math.round(bytes / 1e6))} MB`;
}

/** `0:07`, `2:05`. */
export function formatElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function formatUsd(value: number): string {
  return value < 10 ? `$${value.toFixed(2)}` : `$${Math.round(value)}`;
}

// Catalog tags worth a badge on an API row (FR-M-4 "variant badges"), in this
// order; anything else stays searchable but unshown, so a row never gets a wall
// of tags.
const BADGE_TAGS: Record<string, string> = {
  reasoning: "reasoning",
  thinking: "reasoning",
  vision: "vision",
  tools: "tools",
  "tool-use": "tools",   // AI Router's spelling
  free: "free",
  zdr: "no retention",
};

export function badgesFor(row: Pick<ModelRow, "tags">): string[] {
  const out: string[] = [];
  for (const tag of row.tags ?? []) {
    const badge = BADGE_TAGS[tag.toLowerCase()];
    if (badge && !out.includes(badge)) out.push(badge);
  }
  return out.slice(0, 3);
}

const EFFORT_LABELS: Record<string, string> = { off: "No thinking", low: "Low", medium: "Medium", high: "High", max: "Max" };

export function effortLabel(effort: string | null): string | null {
  return effort ? (EFFORT_LABELS[effort] ?? effort) : null;
}

// ── waking up ────────────────────────────────────────────────────────────────
// The user asked for this to sound like the app it is (a companion waking up),
// not like a progress bar. `{name}` is the active companion; with none it is
// "Your waifu". A line changes every few seconds; the first is always the same.

export const WAKING_FIRST = "{name} is waking up…";

export const WAKING_LINES = [
  "{name} is stretching… and yawning…",
  "Rubbing the sleep out of {name}'s eyes…",
  "{name} hit snooze. Nudging again…",
  "Brewing {name}'s morning tea…",
  "{name} is taming a serious case of bedhead…",
  "{name} is picking an outfit for you…",
  "{name} is gathering scattered thoughts…",
  "{name} is looking for the other slipper…",
  "Warming up {name}'s neurons, one by one…",
  "{name} is practising a good-morning smile…",
];

/** Said when another model replaces one that was already up. */
export const SWITCHING_LINES = ["{name} is swapping brains. Hold still…", "{name} is getting used to a new brain…"];

/** After this long, say honestly that a big model takes a while. */
export const SLOW_AFTER_S = 60;
export const SLOW_LINE = "Big brains take a minute. {name} is worth the wait…";

export const WAKING_STEP_S = 4;

function withName(line: string, name: string | null): string {
  const who = name?.trim() || "Your waifu";
  // "Your waifu" mid-sentence reads better lower-cased; a sentence start keeps the capital.
  return line.replace(/\{name\}/g, (_m, offset: number) => {
    const before = line.slice(0, offset).trimEnd();
    const startsSentence = before === "" || /[.!?…]$/.test(before);
    return startsSentence || who !== "Your waifu" ? who : "your waifu";
  });
}

export function wakingLine(name: string | null, elapsedS: number, switching = false): string {
  const step = Math.floor(Math.max(0, elapsedS) / WAKING_STEP_S);
  if (step === 0) return withName(switching ? SWITCHING_LINES[0] : WAKING_FIRST, name);
  if (elapsedS >= SLOW_AFTER_S && step % 4 === 0) return withName(SLOW_LINE, name);
  const pool = switching ? [...SWITCHING_LINES.slice(1), ...WAKING_LINES] : WAKING_LINES;
  return withName(pool[(step - 1) % pool.length], name);
}

export function awakeLine(name: string | null): string {
  return withName("{name} is awake.", name);
}

export function failedLine(name: string | null): string {
  return withName("{name} couldn't wake up.", name);
}

// ── thinking ─────────────────────────────────────────────────────────────────
// Beside the heart above the input box while a reply is on its way (FR-C-5,
// D-063). The app's words, not the companion's: she supplies only her name (FR-W-3).

export const THINKING_LINES = [
  "{name} is mulling it over…",
  "{name} is choosing her words…",
  "{name} is thinking it through…",
  "{name} is connecting the dots…",
  "{name} is chewing on that…",
  "{name} is untangling a thought…",
  "{name} is weighing a few answers…",
  "{name} is turning it over in her head…",
  "{name} is having a little think…",
  "{name} is gathering her thoughts…",
];

export const THINKING_STEP_S = 3;

/** The line for the `step`-th change of a turn. `start` is where this turn begins
 * in the list, so turns do not all open with the same words. */
export function thinkingLine(name: string | null, step: number, start = 0): string {
  const n = THINKING_LINES.length;
  return withName(THINKING_LINES[(((start + step) % n) + n) % n], name);
}
