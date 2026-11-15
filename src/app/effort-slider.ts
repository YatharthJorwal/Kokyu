// Effort slider logic (K1-11; FR-M-8, FR-M-9). Pure, so tests-fe can run it.
// The component (ui/EffortSlider.tsx) only renders what these functions say.

import { effortLabel } from "./models";

/** The canonical detents, lowest first (FR-M-8). */
export const EFFORT_LEVELS = ["off", "low", "medium", "high", "max"] as const;
export type EffortLevel = (typeof EFFORT_LEVELS)[number];

/** The detents to draw: canonical order, only what the model supports. Empty = no slider. */
export function detents(supported: readonly string[]): EffortLevel[] {
  return EFFORT_LEVELS.filter((level) => supported.includes(level));
}

/** Where `value` sits among the detents; -1 when it is not one of them (the model's default). */
export function indexOf(stops: readonly EffortLevel[], value: string | null): number {
  return value === null ? -1 : stops.indexOf(value as EffortLevel);
}

/** The detent a key moves to, or null for a key the slider does not handle. From
 * the model's default (no detent), the arrows land on the nearest end. */
export function stepFor(stops: readonly EffortLevel[], value: string | null, key: string): EffortLevel | null {
  if (stops.length === 0) return null;
  const last = stops.length - 1;
  const at = indexOf(stops, value);
  switch (key) {
    case "Home":
      return stops[0];
    case "End":
      return stops[last];
    case "ArrowRight":
    case "ArrowUp":
      return stops[at < 0 ? 0 : Math.min(at + 1, last)];
    case "ArrowLeft":
    case "ArrowDown":
      return stops[at < 0 ? 0 : Math.max(at - 1, 0)];
    default:
      return null;
  }
}

/** The thumb's place on the track, 0..1 (also the fill). One detent sits in the middle. */
export function positionFor(index: number, count: number): number {
  if (index < 0 || count === 0) return 0;
  return count === 1 ? 0.5 : index / (count - 1);
}

/** The detent nearest to a point on the track (0..1, clamped). */
export function nearestIndex(fraction: number, count: number): number {
  if (count <= 1) return 0;
  const clamped = Math.min(Math.max(fraction, 0), 1);
  return Math.round(clamped * (count - 1));
}

export interface Glow {
  /** 0 (none) to 1 (max): how bright the glow is. */
  intensity: number;
  /** Seconds per pulse; 0 = no pulse. Faster as the effort rises. */
  periodS: number;
}

/** The glow for a level (FR-M-9). By canonical rank, so "high" looks the same on
 * every model whatever its other detents. Reusable for the chip while it generates. */
export function glowFor(level: string | null): Glow {
  const rank = level === null ? -1 : EFFORT_LEVELS.indexOf(level as EffortLevel);
  if (rank <= 0) return { intensity: 0, periodS: 0 };   // off, or the model's default
  const top = EFFORT_LEVELS.length - 1;
  return { intensity: rank / top, periodS: Number((2.4 - (1.5 * (rank - 1)) / (top - 1)).toFixed(2)) };
}

/** The word for a level (the app's labels); null is the model's own default. */
export function levelLabel(level: string | null): string {
  return effortLabel(level) ?? "Model default";
}
