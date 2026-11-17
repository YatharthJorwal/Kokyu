// The effort slider (K1-11; FR-M-8, FR-M-9): detents for the levels the model
// supports, a thumb that follows the pointer while dragged and glides to the
// nearest detent on release (the change is sent once, then), and a fill
// whose glow brightens and pulses faster as the effort rises. Reduced motion
// (the prop or the OS setting) leaves a static fill. Nothing supported: no slider.
// Logic in ../effort-slider.ts; the caller owns the value (per model per thread).

import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";

import {
  detents,
  glowFor,
  indexOf,
  levelLabel,
  nearestIndex,
  positionFor,
  stepFor,
} from "../effort-slider";
import "./effort-slider.css";

export interface EffortSliderProps {
  /** Effort levels the selected model supports, any order (FR-M-10). */
  supported: readonly string[];
  /** The current effort; null = the model's default (no detent picked yet). */
  value: string | null;
  onChange: (effort: string) => void;
  /** Force the static look even when the OS allows motion. */
  reducedMotion?: boolean;
}

export function EffortSlider({ supported, value, onChange, reducedMotion = false }: EffortSliderProps) {
  const track = useRef<HTMLDivElement>(null);
  /** While dragged: where the pointer is on the track, 0..1; null otherwise. */
  const [drag, setDrag] = useState<number | null>(null);
  /** The level just picked, shown until the engine confirms it (or briefly, if it never does). */
  const [held, setHeld] = useState<string | null>(null);
  useEffect(() => setHeld(null), [value]);
  useEffect(() => {
    if (held === null) return;
    const t = window.setTimeout(() => setHeld(null), 1500);
    return () => window.clearTimeout(t);
  }, [held]);
  const stops = detents(supported);
  if (stops.length === 0) return null;

  const shownValue = held ?? value;
  const dragIndex = drag === null ? -1 : nearestIndex(drag, stops.length);
  const index = drag === null ? indexOf(stops, shownValue) : dragIndex;
  const current = index >= 0 ? stops[index] : null;
  const glow = glowFor(current);
  const style = {
    "--effort-pos": drag ?? positionFor(index, stops.length),
    "--effort-glow": glow.intensity,
    "--effort-period": `${glow.periodS || 1}s`,
  } as CSSProperties;

  const pick = (next: string | undefined) => {
    if (!next || next === shownValue) return;
    setHeld(next);
    onChange(next);
  };

  const fractionAt = (clientX: number): number | null => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return null;
    return Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const next = stepFor(stops, shownValue, e.key);
    if (next === null) return;
    e.preventDefault();
    pick(next);
  };

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag(fractionAt(e.clientX));
  };

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (drag !== null) setDrag(fractionAt(e.clientX) ?? drag);
  };

  // Release: the thumb glides to the nearest detent, and that is the pick.
  const onPointerUp = () => {
    if (drag === null) return;
    setDrag(null);
    pick(stops[dragIndex]);
  };

  const onPointerCancel = () => setDrag(null);

  const classes = ["effort-slider"];
  if (reducedMotion) classes.push("reduced");
  if (glow.periodS === 0) classes.push("still");
  if (drag !== null) classes.push("dragging");

  return (
    <div
      className={classes.join(" ")}
      style={style}
      data-level={current ?? "default"}
      role="slider"
      tabIndex={0}
      aria-label="Effort"
      aria-valuemin={0}
      aria-valuemax={stops.length - 1}
      aria-valuenow={index >= 0 ? index : undefined}
      aria-valuetext={levelLabel(current)}
      onKeyDown={onKeyDown}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
    >
      <div className="effort-track" ref={track}>
        <span className="effort-glow" aria-hidden="true" />
        <span className="effort-fill" aria-hidden="true" />
        {stops.map((stop, i) => (
          <span
            key={stop}
            className={`effort-stop${index >= 0 && i <= index ? " on" : ""}`}
            style={{ left: `${positionFor(i, stops.length) * 100}%` }}
            aria-hidden="true"
          />
        ))}
        {index >= 0 || drag !== null ? <span className="effort-thumb" aria-hidden="true" /> : null}
      </div>
      <div className="effort-labels" aria-hidden="true">
        {stops.map((stop, i) => (
          <span
            key={stop}
            className={i === index ? "current" : undefined}
            style={{ left: `${positionFor(i, stops.length) * 100}%` }}
          >
            {levelLabel(stop)}
          </span>
        ))}
      </div>
    </div>
  );
}
