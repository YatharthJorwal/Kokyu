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
export type Action = "idle" | "walk" | "sit" | "eat" | "sleep" | "wave" | "happy" | "sad" | "held" | "fall" | "land";
/** How code moves the still pose: app.css has one keyframe set per motion; "walk"
 * is moved by Pet.tsx from `gait`, in step with her feet. */
export type Motion = "breathe" | "walk" | "talk" | "doze" | "hop" | "dangle" | "none";

export interface PetState {
  /** Her centre, in px from the lane's left edge. */
  x: number;
  /** Her feet above the floor (the window's bottom), px; above 0 only while held or falling. */
  y: number;
  /** Falling speed, px per second downwards. */
  vy: number;
  /** Distance walked since this walk began, px: the gait's phase (so her feet never slide). */
  stride: number;
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
  /** The lane's size and her own drawn size, in px. */
  width: number;
  self: number;
  /** Her drawn height: walking speed and step length scale with it. Default 160. */
  height?: number;
  /** The lane's height: how high she may be held. Default: no limit. */
  top?: number;
  /** Where the pointer holds her (her centre, her feet's height); null or absent: not held. */
  held?: { x: number; y: number } | null;
}

export const SLEEPY_AFTER = 120;  // seconds of quiet
export const GRAVITY = 2400;      // px per second squared
export const WALK_SPEED_PER_HEIGHT = 0.45;   // her height per second at full stride
export const STEP_PER_HEIGHT = 0.16;         // one step is this much of her height
const REACTION: Partial<Record<Action, number>> = { wave: 1.8, happy: 2.4, sad: 3, land: 0.7 };

export function initialPet(width: number): PetState {
  return { x: width * 0.8, y: 0, vy: 0, stride: 0, dir: -1, action: "idle", left: 2, target: 0, quiet: 0, clock: 0 };
}

/** The walk's rise, sway and which foot: one step per STEP_PER_HEIGHT of distance,
 * rising mid-step and settling as the foot lands. */
export function gait(stride: number, height: number): { frame: 0 | 1; bob: number; tilt: number } {
  const phase = stride / (height * STEP_PER_HEIGHT);
  const frame = (Math.floor(phase) % 2) as 0 | 1;
  const lift = Math.sin(Math.PI * (phase - Math.floor(phase)));
  return { frame, bob: lift * height * 0.025, tilt: (frame === 0 ? 1 : -1) * lift * 2 };
}

/** `rand` returns [0, 1), so tests can pass a fixed sequence. */
export function step(s: PetState, dt: number, input: PetInput, rand: () => number = Math.random): PetState {
  const lo = input.self / 2;
  const hi = Math.max(lo, input.width - input.self / 2);
  const height = input.height ?? 160;
  const clampX = (x: number) => Math.min(hi, Math.max(lo, x));
  let next: PetState = { ...s, clock: s.clock + dt, x: clampX(s.x) };
  next.quiet = input.activity === "idle" && !input.clicked ? s.quiet + dt : 0;

  // Held by the pointer: one pose, wherever she is put. Let go: she falls, then lands.
  if (input.held) {
    const ceiling = Math.max(0, (input.top ?? Infinity) - height);
    return { ...next, action: "held", x: clampX(input.held.x), y: Math.min(ceiling, Math.max(0, input.held.y)), vy: 0, quiet: 0 };
  }
  if (next.action === "held" || next.action === "fall") {
    const vy = next.vy + GRAVITY * dt;
    const y = next.y - vy * dt;
    if (y > 0) return { ...next, action: "fall", y, vy };
    return { ...next, action: "land", y: 0, vy: 0, left: REACTION.land ?? 0.7 };
  }

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
    // Eases in over her first steps and out over the last one, so she neither
    // jumps to full speed nor stops dead.
    const ramp = Math.min(1, 0.35 + next.stride / (height * 0.3), 0.35 + Math.abs(gap) / (height * 0.3));
    const move = height * WALK_SPEED_PER_HEIGHT * ramp * dt;
    if (Math.abs(gap) <= move) return { ...next, x: next.target, action: "idle", left: 1.5 + rand() * 2 };
    return { ...next, x: next.x + Math.sign(gap) * move, stride: next.stride + move, dir: gap > 0 ? 1 : -1 };
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
    return { ...s, action: "walk", target, stride: 0, dir: target > s.x ? 1 : -1, left: 0 };
  }
  if (r < 0.65) return { ...s, action: "idle", left: 3 + rand() * 3 };
  if (r < 0.85) return { ...s, action: "sit", left: 6 + rand() * 6 };
  return { ...s, action: "eat", left: 4 + rand() * 2 };
}

/** The pose to draw and its motion. `has` lists the poses her pet has; a missing one
 * falls back to idle (FR-P-3). */
export function poseFor(s: PetState, activity: Activity, has: readonly string[], height = 160): { pose: string; motion: Motion } {
  const pick = (want: Pose, motion: Motion): { pose: string; motion: Motion } =>
    has.includes(want) ? { pose: want, motion } : { pose: "idle", motion };
  if (s.action === "held") return pick("surprised", "dangle");
  if (s.action === "fall") return pick("surprised", "none");
  if (s.action === "land") return pick("sit", "none");
  if (s.action === "wave") return pick("wave", "none");
  if (s.action === "happy") return pick("happy", "hop");
  if (s.action === "sad") return pick("sad", "none");
  if (s.action === "sleep") return pick("sleep", "doze");
  if (activity === "thinking") return pick("think", "breathe");
  if (activity === "talking") return pick("talk", "talk");
  if (s.action === "walk") {
    const second = gait(s.stride, height).frame === 1 && has.includes("walk_2");
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
