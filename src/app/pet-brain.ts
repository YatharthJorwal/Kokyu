// Her pet's behaviour (D-103, FR-P-3): pure logic, no DOM. `step` moves her on by
// `dt` seconds; `poseFor` says which of her poses to draw and how code moves it.
// What she does is decided here; Pet.tsx only draws it.

export const POSES = [
  "idle", "walk_1", "walk_2", "sit",
  "sleep", "eat", "wave", "think",
  "talk", "happy", "sad", "surprised",
] as const;
export type Pose = (typeof POSES)[number];

export type PetMode = "roam" | "stay" | "sleep";
export type Activity = "idle" | "thinking" | "talking";
export type Action = "idle" | "walk" | "sit" | "eat" | "sleep" | "wave" | "happy" | "sad";
/** How code moves the still pose (app.css has one keyframe set per motion). */
export type Motion = "breathe" | "walk" | "talk" | "doze" | "hop" | "none";

export interface PetState {
  /** Her centre, in px from the lane's left edge. */
  x: number;
  /** 1: facing right. */
  dir: 1 | -1;
  action: Action;
  /** Seconds left in the action (walks end on arrival instead). */
  left: number;
  target: number;
  /** Seconds with nothing happening in the chat; a long quiet puts her to sleep. */
  quiet: number;
  clock: number;
}

export interface PetInput {
  mode: PetMode;
  activity: Activity;
  /** One-off events since the last step. */
  clicked?: boolean;
  replied?: boolean;
  failed?: boolean;
  /** The lane's width and her own width, in px. */
  width: number;
  self: number;
}

export const WALK_SPEED = 70;     // px per second
export const SLEEPY_AFTER = 120;  // seconds of quiet
const REACTION: Partial<Record<Action, number>> = { wave: 1.8, happy: 2.4, sad: 3 };

export function initialPet(width: number): PetState {
  return { x: width * 0.8, dir: -1, action: "idle", left: 2, target: 0, quiet: 0, clock: 0 };
}

/** `rand` returns [0, 1), so tests can pass a fixed sequence. */
export function step(s: PetState, dt: number, input: PetInput, rand: () => number = Math.random): PetState {
  const lo = input.self / 2;
  const hi = Math.max(lo, input.width - input.self / 2);
  let next: PetState = { ...s, clock: s.clock + dt, x: Math.min(hi, Math.max(lo, s.x)) };
  next.quiet = input.activity === "idle" && !input.clicked ? s.quiet + dt : 0;

  const react = (action: Action): PetState => ({ ...next, action, left: REACTION[action] ?? 2 });
  if (input.clicked) return react("wave");
  if (input.failed) return react("sad");
  if (input.replied) return react("happy");
  if (next.action in REACTION && next.left > 0) return { ...next, left: next.left - dt };
  if (input.mode === "sleep") return { ...next, action: "sleep", left: 1 };
  // Thinking and talking are drawn from the activity; she stands still for them.
  if (input.activity !== "idle") return { ...next, action: "idle", left: 1 };

  if (next.action === "walk") {
    const gap = next.target - next.x;
    const move = WALK_SPEED * dt;
    if (Math.abs(gap) <= move) return { ...next, x: next.target, action: "idle", left: 1.5 + rand() * 2 };
    return { ...next, x: next.x + Math.sign(gap) * move, dir: gap > 0 ? 1 : -1 };
  }
  if (next.action === "sleep" && next.quiet >= SLEEPY_AFTER) return next;   // asleep until something happens
  next.left -= dt;
  if (next.left > 0) return next;
  return choose(next, input, lo, hi, rand);
}

function choose(s: PetState, input: PetInput, lo: number, hi: number, rand: () => number): PetState {
  if (s.quiet >= SLEEPY_AFTER) return { ...s, action: "sleep", left: 1 };
  const r = rand();
  if (input.mode === "roam" && r < 0.4 && hi > lo) {
    const target = lo + rand() * (hi - lo);
    return { ...s, action: "walk", target, dir: target > s.x ? 1 : -1, left: 0 };
  }
  if (r < 0.65) return { ...s, action: "idle", left: 3 + rand() * 3 };
  if (r < 0.85) return { ...s, action: "sit", left: 6 + rand() * 6 };
  return { ...s, action: "eat", left: 4 + rand() * 2 };
}

/** The pose to draw and its motion. `has` lists the poses her pet has; a missing one
 * falls back to idle (FR-P-3). */
export function poseFor(s: PetState, activity: Activity, has: readonly string[]): { pose: string; motion: Motion } {
  const pick = (want: Pose, motion: Motion): { pose: string; motion: Motion } =>
    has.includes(want) ? { pose: want, motion } : { pose: "idle", motion };
  if (s.action === "wave") return pick("wave", "none");
  if (s.action === "happy") return pick("happy", "hop");
  if (s.action === "sad") return pick("sad", "none");
  if (s.action === "sleep") return pick("sleep", "doze");
  if (activity === "thinking") return pick("think", "breathe");
  if (activity === "talking") return pick("talk", "talk");
  if (s.action === "walk") {
    const second = Math.floor(s.clock / 0.3) % 2 === 1 && has.includes("walk_2");
    return pick(second ? "walk_2" : "walk_1", "walk");
  }
  if (s.action === "sit") return pick("sit", "breathe");
  if (s.action === "eat") return pick("eat", "breathe");
  return pick("idle", "breathe");
}

// The window's own settings for her pet, kept like Appearance (D-073) in localStorage.
export interface PetPrefs {
  show: boolean;
  mode: PetMode;
  /** Percent of her saved height. */
  size: number;
}

export const DEFAULT_PET_PREFS: PetPrefs = { show: true, mode: "roam", size: 50 };
export const PET_SIZE_MIN = 25;
export const PET_SIZE_MAX = 100;
export const PET_PREFS_KEY = "kokyu.pet";

export function parsePetPrefs(raw: string | null): PetPrefs {
  let v: unknown;
  try {
    v = raw === null ? null : JSON.parse(raw);
  } catch {
    return DEFAULT_PET_PREFS;
  }
  if (typeof v !== "object" || v === null) return DEFAULT_PET_PREFS;
  const o = v as Record<string, unknown>;
  const size = typeof o.size === "number" && Number.isFinite(o.size) ? Math.round(o.size) : DEFAULT_PET_PREFS.size;
  return {
    show: typeof o.show === "boolean" ? o.show : DEFAULT_PET_PREFS.show,
    mode: o.mode === "roam" || o.mode === "stay" || o.mode === "sleep" ? o.mode : DEFAULT_PET_PREFS.mode,
    size: Math.min(PET_SIZE_MAX, Math.max(PET_SIZE_MIN, size)),
  };
}

/** What Create pet asks the image model for (D-103). The grid order is POSES'. */
export function petPrompt(name: string): string {
  return [
    `Make one pose sheet of ${name} as a cute chibi desktop pet, from the attached picture of her.`,
    "One image, a grid of 4 columns and 3 rows, 12 equal cells, one full-body pose per cell, in this order:",
    "row 1: standing idle; walking (left foot forward); walking (right foot forward); sitting on the floor.",
    "row 2: sleeping curled up on the floor; eating a snack; waving; thinking with a hand on her chin.",
    "row 3: talking happily; very happy, arms up; sad; surprised.",
    "Same character, outfit, colours and size in every cell; the whole body inside its cell with a little space around it; her feet at the same height in every cell of a row.",
    "Walking poses face to the right. Transparent background (or plain flat white if transparency is not possible). No text, no labels, no grid lines, no shadows on the ground.",
  ].join("\n");
}
