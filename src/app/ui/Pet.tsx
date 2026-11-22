// Her pet (D-103, FR-P-1..4): chibi her, walking along the window's bottom edge,
// in front of the input box. What she does comes from pet-brain.ts; this only draws
// it. Her position moves by style each frame (no React render); a render happens only
// when her pose or motion changes. She can be picked up and dropped (D-107).

import { useEffect, useRef, useState, type PointerEvent } from "react";

import { KERNEL_HTTP_URL } from "../../net/kernel";
import { gait, initialPet, poseFor, step, type Activity, type Motion, type PetState } from "../pet-brain";
import { useChat, usePetPrefs } from "../store";

const SAVED_HEIGHT = 320;   // KASANE/waifus/pet.py HEIGHT: idle's height in the saved poses
const DRAG_START = 5;       // px the pointer moves before a press is a drag, not a click

export function petPoseUrl(id: string, pose: string, stamp: string): string {
  return `${KERNEL_HTTP_URL}/waifus/${encodeURIComponent(id)}/pet/${pose}?v=${encodeURIComponent(stamp)}`;
}

export function petDraftUrl(id: string, cell: number, stamp: string): string {
  return `${KERNEL_HTTP_URL}/waifus/${encodeURIComponent(id)}/pet-draft/${cell}?v=${encodeURIComponent(stamp)}`;
}

export function Pet() {
  const companion = useChat((s) => s.companion);
  const inThread = useChat((s) => s.thread !== null);
  const show = usePetPrefs((p) => p.show);
  if (!show || !inThread || !companion?.pet) return null;
  return <PetWalker key={`${companion.id}:${companion.pet}`} id={companion.id} name={companion.name} stamp={companion.pet} poses={companion.petPoses ?? []} />;
}

function activityNow(): Activity {
  const s = useChat.getState();
  if (s.turn === "thinking") return "thinking";
  if (s.turn === "replying" || s.reading !== null) return "talking";
  return "idle";
}

function PetWalker({ id, name, stamp, poses }: { id: string; name: string; stamp: string; poses: string[] }) {
  const lane = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const clicked = useRef(false);
  // A press on her: where it began, where on her it holds, and (once it moved) where she is held.
  const press = useRef<{ id: number; x0: number; y0: number; dx: number; dy: number; dragging: boolean } | null>(null);
  const held = useRef<{ x: number; y: number } | null>(null);
  const brain = useRef<PetState | null>(null);   // kept across re-renders: a roster refresh must not reset her
  const posesKey = poses.join(",");
  const [look, setLook] = useState<{ pose: string; motion: Motion; dir: 1 | -1 }>({ pose: "idle", motion: "breathe", dir: -1 });
  const size = usePetPrefs((p) => p.size);
  const height = Math.round((SAVED_HEIGHT * size) / 100);

  // Each pose keeps its own saved size: a sitting or lying pose is shorter than idle,
  // so drawing every pose at idle's height would blow those up.
  const [natural, setNatural] = useState<Record<string, number>>({});
  useEffect(() => {
    for (const pose of posesKey.split(",")) {
      const img = new Image();   // also preloads, so the first switch does not flicker
      img.onload = () => setNatural((old) => ({ ...old, [pose]: img.naturalHeight }));
      img.src = petPoseUrl(id, pose, stamp);
    }
  }, [id, stamp, posesKey]);

  useEffect(() => {
    const has = posesKey.split(",");
    let last = performance.now();
    let turn = useChat.getState().turn;
    let frame = 0;
    let shown = { pose: "idle", motion: "breathe" as Motion, dir: -1 as 1 | -1 };
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      const width = lane.current?.clientWidth ?? 0;
      const top = lane.current?.clientHeight ?? 0;
      const self = body.current?.offsetWidth || height * 0.6;
      if (width === 0) return;
      let state = brain.current ?? initialPet(width);
      const chat = useChat.getState();
      // A turn just ended: happy after a reply, sad after a failure.
      const ended = turn !== "idle" && chat.turn === "idle";
      const failed = ended && (chat.notice?.code === "model_failed" || chat.notice?.code === "model_blocked");
      turn = chat.turn;
      const activity = activityNow();
      state = step(state, Math.min(0.1, (now - last) / 1000), {
        mode: usePetPrefs.getState().mode,
        activity,
        clicked: clicked.current,
        replied: ended && !failed,
        failed,
        width,
        self,
        height,
        top,
        held: held.current,
      });
      brain.current = state;
      clicked.current = false;
      last = now;
      // The walk's rise and sway follow the distance walked, so each step lands with her foot.
      const step_ = state.action === "walk" && !still ? gait(state.stride, height) : { bob: 0, tilt: 0 };
      if (body.current) {
        body.current.style.transform = `translate3d(${Math.round(state.x - self / 2)}px, ${-Math.round(state.y + step_.bob)}px, 0) rotate(${(step_.tilt * state.dir).toFixed(2)}deg)`;
      }
      const next = { ...poseFor(state, activity, has, height), dir: state.dir };
      if (next.pose !== shown.pose || next.motion !== shown.motion || next.dir !== shown.dir) {
        shown = next;
        setLook(next);
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [posesKey, height]);

  const laneBox = () => lane.current?.getBoundingClientRect();
  const down = (e: PointerEvent<HTMLImageElement>) => {
    const box = laneBox();
    const s = brain.current;
    if (e.button !== 0 || !box || !s) return;
    e.preventDefault();
    try {
      e.currentTarget.setPointerCapture(e.pointerId);   // keeps the drag when the pointer outruns her
    } catch {
      /* a pointer already gone: the drag still works while over her */
    }
    press.current = {
      id: e.pointerId,
      x0: e.clientX,
      y0: e.clientY,
      dx: e.clientX - box.left - s.x,
      dy: box.bottom - e.clientY - s.y,
      dragging: false,
    };
  };
  const move = (e: PointerEvent<HTMLImageElement>) => {
    const p = press.current;
    const box = laneBox();
    if (!p || p.id !== e.pointerId || !box) return;
    if (!p.dragging && Math.hypot(e.clientX - p.x0, e.clientY - p.y0) < DRAG_START) return;
    p.dragging = true;
    held.current = { x: e.clientX - box.left - p.dx, y: box.bottom - e.clientY - p.dy };
  };
  const up = (e: PointerEvent<HTMLImageElement>) => {
    const p = press.current;
    if (!p || p.id !== e.pointerId) return;
    if (!p.dragging && e.type === "pointerup") clicked.current = true;
    press.current = null;
    held.current = null;   // let go: the brain drops her
  };

  return (
    <div className="pet-lane" ref={lane} aria-hidden="true">
      <div className="pet" ref={body} data-motion={look.motion}>
        <div className={look.dir === 1 ? "pet-face" : "pet-face left"}>
          <img
            src={petPoseUrl(id, look.pose, stamp)}
            alt=""
            draggable={false}
            style={{ height: Math.round(((natural[look.pose] ?? SAVED_HEIGHT) * size) / 100) }}
            title={name}
            onPointerDown={down}
            onPointerMove={move}
            onPointerUp={up}
            onPointerCancel={up}
          />
        </div>
      </div>
    </div>
  );
}
