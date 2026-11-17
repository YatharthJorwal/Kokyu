// Chat memory (D-098): the model's context length, in the picker under Effort. The
// effort slider's look and drag (effort-slider.css): detents from 8K doubling to the
// model's maximum, a thumb that follows the pointer and settles on release, where the
// one change is sent. For a local model, a faint mark where it stops fitting in
// graphics memory and a line saying so past it: a warning, never a block.

import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";

import type { ModelContext } from "../../net/protocol";
import { contextDetents, contextLabel, contextNote, nearestDetent, trackPosition } from "../context-slider";
import "./effort-slider.css";

export function ContextSlider({
  context,
  local,
  onChange,
}: {
  context: ModelContext;
  local: boolean;
  onChange: (tokens: number) => void;
}) {
  const track = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<number | null>(null);
  const [held, setHeld] = useState<number | null>(null);
  useEffect(() => setHeld(null), [context.value]);
  useEffect(() => {
    if (held === null) return;
    const t = window.setTimeout(() => setHeld(null), 4000); // the engine answers with a new list
    return () => window.clearTimeout(t);
  }, [held]);
  const stops = contextDetents(context.max);
  if (stops.length < 2) return null;

  const last = stops.length - 1;
  const shown = held ?? context.value ?? stops[0];
  const index = drag === null ? Math.max(nearestDetent(stops, shown), 0) : Math.round(drag * last);
  const tokens = stops[index];
  const fitAt = local && context.fit !== null && context.fit < stops[last] ? trackPosition(stops, context.fit) : null;
  const note = contextNote(context, tokens, local);
  const style = { "--effort-pos": drag ?? index / last, "--effort-glow": 0, "--effort-period": "1s" } as CSSProperties;

  const pick = (i: number) => {
    const next = stops[Math.min(Math.max(i, 0), last)];
    if (next === shown) return;
    setHeld(next);
    onChange(next);
  };
  const fractionAt = (clientX: number): number | null => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return null;
    return Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, Home: -last, End: last }[e.key];
    if (step === undefined) return;
    e.preventDefault();
    pick(index + step);
  };
  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag(fractionAt(e.clientX));
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (drag !== null) setDrag(fractionAt(e.clientX) ?? drag);
  };
  const onPointerUp = () => {
    if (drag === null) return;
    setDrag(null);
    pick(index);
  };

  const classes = ["effort-slider", "context-slider", "still"];
  if (drag !== null) classes.push("dragging");
  if (note?.warn) classes.push("over");

  return (
    <>
      <div
        className={classes.join(" ")}
        style={style}
        role="slider"
        tabIndex={0}
        aria-label="Chat memory"
        aria-valuemin={0}
        aria-valuemax={last}
        aria-valuenow={index}
        aria-valuetext={`${contextLabel(tokens)} tokens`}
        title="How much of this chat she can keep in mind"
        onKeyDown={onKeyDown}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => setDrag(null)}
      >
        <div className="effort-track" ref={track}>
          <span className="effort-fill" aria-hidden="true" />
          {stops.map((stop, i) =>
            i === 0 || i === last ? null : (
              <span
                key={stop}
                className={`effort-stop${i <= index ? " on" : ""}`}
                style={{ left: `${(i / last) * 100}%` }}
                aria-hidden="true"
              />
            ),
          )}
          {fitAt !== null ? <span className="context-fit" style={{ left: `${fitAt * 100}%` }} aria-hidden="true" /> : null}
          <span className="effort-thumb" aria-hidden="true" />
        </div>
        <div className="effort-labels" aria-hidden="true">
          {stops.map((stop, i) => (
            <span key={stop} className={i === index ? "current" : undefined} style={{ left: `${(i / last) * 100}%` }}>
              {contextLabel(stop)}
            </span>
          ))}
        </div>
      </div>
      {note ? (
        <p className={note.warn ? "context-note past-fit" : "context-note"} role={note.warn ? "status" : undefined}>
          {note.text}
        </p>
      ) : null}
    </>
  );
}
