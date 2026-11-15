// The effort slider (K1-11; FR-M-8, FR-M-9): detents for the levels the model
// supports, a thumb that glides between them with a short spring, and a fill
// whose glow brightens and pulses faster as the effort rises. Reduced motion
// (the prop or the OS setting) leaves a static fill. Nothing supported: no slider.
// Logic in ../effort-slider.ts; the caller owns the value (per model per thread).

import { useRef, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";

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
  const dragging = useRef(false);
  const stops = detents(supported);
  if (stops.length === 0) return null;

  const index = indexOf(stops, value);
  const current = index >= 0 ? stops[index] : null;
  const glow = glowFor(current);
  const style = {
    "--effort-pos": positionFor(index, stops.length),
    "--effort-glow": glow.intensity,
    "--effort-period": `${glow.periodS || 1}s`,
  } as CSSProperties;

  const pick = (next: string | undefined) => {
    if (next && next !== value) onChange(next);
  };

  const pickAt = (clientX: number) => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    pick(stops[nearestIndex((clientX - rect.left) / rect.width, stops.length)]);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const next = stepFor(stops, value, e.key);
    if (next === null) return;
    e.preventDefault();
    pick(next);
  };

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    dragging.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    pickAt(e.clientX);
  };

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (dragging.current) pickAt(e.clientX);
  };

  const stopDragging = () => {
    dragging.current = false;
  };

  const classes = ["effort-slider"];
  if (reducedMotion) classes.push("reduced");
  if (glow.periodS === 0) classes.push("still");

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
      onPointerUp={stopDragging}
      onPointerCancel={stopDragging}
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
        {index >= 0 ? <span className="effort-thumb" aria-hidden="true" /> : null}
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
