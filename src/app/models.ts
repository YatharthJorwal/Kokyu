// The model chip's pure helpers (K1-10; FR-M-1..7, D-054): filtering the
// picker's rows, short labels, sizes, and the "waking up" lines shown while the
// kernel loads the chat model. No React, no DOM: tested in Node.

import type { ModelRow } from "../net/protocol";

/** `local:ollama/qwen3.5:9b` -> `qwen3.5:9b`: the id, for when the kernel has not
 * named the model yet (the names come with the model list, D-084). */
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
    const hay = `${r.label} ${r.full ?? ""} ${r.ref} ${r.detail ?? ""} ${(r.tags ?? []).join(" ")}`.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

// D-127: the picker's order and companies, kept by this window like Appearance (D-073).
export type ModelOrder = "company" | "name" | "cheap" | "pricey";

export const MODEL_ORDERS: { id: ModelOrder; label: string }[] = [
  { id: "company", label: "By company" },
  { id: "name", label: "Name A–Z" },
  { id: "cheap", label: "Cheapest first" },
  { id: "pricey", label: "Priciest first" },
];

export interface PickerPrefs {
  order: ModelOrder;
  /** Companies to show; empty = all. */
  companies: string[];
  /** Every model the endpoint has, not only the user's list: an older version stays one click away. */
  all: boolean;
}

export const DEFAULT_PICKER_PREFS: PickerPrefs = { order: "company", companies: [], all: false };

/** A stored value, checked field by field: anything unknown falls back to the default. */
export function parsePickerPrefs(raw: string | null): PickerPrefs {
  let data: unknown;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = null;
  }
  const d = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const order = MODEL_ORDERS.some((o) => o.id === d.order) ? (d.order as ModelOrder) : DEFAULT_PICKER_PREFS.order;
  const companies = Array.isArray(d.companies) ? d.companies.filter((c): c is string => typeof c === "string").slice(0, 100) : [];
  return { order, companies, all: d.all === true };
}

/** Input plus output, per 1M tokens: one number to compare by; null when the catalog has no price. */
function blendedPrice(r: ModelRow): number | null {
  return r.price_in || r.price_out ? (r.price_in ?? 0) + (r.price_out ?? 0) : null;
}

const byName = (a: ModelRow, b: ModelRow) => a.label.localeCompare(b.label, undefined, { numeric: true, sensitivity: "base" });

/** Rows in the chosen order. "company" keeps the kernel's order (sorted by id, so a
 * company's models sit together); priced orders put models with no price last. */
export function sortRows(rows: ModelRow[], order: ModelOrder): ModelRow[] {
  if (order === "company") return rows;
  if (order === "name") return [...rows].sort(byName);
  const sign = order === "cheap" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const pa = blendedPrice(a);
    const pb = blendedPrice(b);
    if (pa === null || pb === null) return pa === pb ? byName(a, b) : pa === null ? 1 : -1;
    return (pa - pb) * sign || byName(a, b);
  });
}

/** The companies the rows come from, A–Z. */
export function companiesOf(rows: ModelRow[]): string[] {
  return [...new Set(rows.map((r) => r.group).filter((g): g is string => !!g))].sort((a, b) => a.localeCompare(b));
}

/** Only the picked companies' rows; with none picked, or none of them in the list any
 * more, every row (a filter that hides everything would look like an empty list). */
export function filterCompanies(rows: ModelRow[], picked: string[]): ModelRow[] {
  const present = new Set(companiesOf(rows));
  const live = picked.filter((c) => present.has(c));
  return live.length ? rows.filter((r) => r.group && live.includes(r.group)) : rows;
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

// Tags worth a badge on a row (FR-M-4 "variant badges"; local rows carry Ollama's
// own capabilities, D-068), always in this order so a badge keeps its column;
// anything else stays searchable but unshown, so a row never gets a wall of tags.
const BADGE_TAGS: Record<string, string> = {
  vision: "vision",
  reasoning: "thinking",
  thinking: "thinking",
  tools: "tools",
  "tool-use": "tools",   // AI Router's spelling
  free: "free",
  zdr: "no retention",
};

const BADGE_ORDER = [...new Set(Object.values(BADGE_TAGS))];

/** The muted second line under a model's full id (D-084): backend, quantization,
 * context, size, price per 1M tokens, and why it cannot be picked. */
export function modelFacts(row: ModelRow): string {
  const price =
    row.price_in || row.price_out ? `$${(row.price_in ?? 0).toFixed(2)} / $${(row.price_out ?? 0).toFixed(2)} per 1M` : null;
  return [row.detail, formatSize(row.size_bytes), price, row.note].filter(Boolean).join(" · ");
}

export function badgesFor(row: Pick<ModelRow, "tags">): string[] {
  const have = new Set((row.tags ?? []).map((tag) => BADGE_TAGS[tag.toLowerCase()]));
  return BADGE_ORDER.filter((badge) => have.has(badge)).slice(0, 3);
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
// One short word beside her face and the heart while a reply is on its way
// (FR-C-5, D-096), in a fresh random order each turn. The app's words, the same
// for every companion (FR-W-3); none repeats the waking-up lines.

export const THINKING_WORDS = [
  // the user's list (D-096)
  "Blushing", "Pouting", "Swooning", "Fluttering", "Melting", "Nuzzling", "Teasing", "Yearning",
  "Giggling", "Whimpering", "Cuddling", "Sparkening", "Heart-fluttering", "Softening", "Clinging",
  "Blush-loading", "Affectioning", "Flustered-thinking", "Headpatting-self",
  // the user's own, kept as an approved exception to D-082 (D-097)
  "Waifu-mode-engaging",
  // more in the same voice
  "Daydreaming", "Twirling-hair", "Humming", "Doodling-hearts", "Kicking-feet", "Starry-eyeing",
  "Swaying", "Peeking", "Fidgeting", "Pillow-hugging", "Lovestruck-loading", "Squealing-softly",
  "Cheek-squishing", "Sighing-dreamily",
];

export const THINKING_STEP_S = 2.4;

/** The words in a fresh order for one turn, so each shows once before any repeats. */
export function thinkingOrder(random: () => number = Math.random): string[] {
  const words = [...THINKING_WORDS];
  for (let i = words.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [words[i], words[j]] = [words[j], words[i]];
  }
  return words;
}

