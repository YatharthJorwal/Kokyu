// Her pet (D-103, FR-P-1..4): chibi her, walking along the bottom of the
// conversation. What she does comes from pet-brain.ts; this only draws it. Her
// position moves by style each frame (no React render); a render happens only when
// her pose or motion changes. She never leaves the lane above the input box.

import { useEffect, useRef, useState } from "react";

import { KERNEL_HTTP_URL } from "../../net/kernel";
import { initialPet, poseFor, step, type Activity, type Motion, type PetState } from "../pet-brain";
import { useChat, usePetPrefs } from "../store";

const SAVED_HEIGHT = 320;   // KASANE/waifus/pet.py HEIGHT: idle's height in the saved poses

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
  const brain = useRef<PetState | null>(null);   // kept across re-renders: a roster refresh must not reset her
  const posesKey = poses.join(",");
  const [look, setLook] = useState<{ pose: string; motion: Motion; dir: 1 | -1 }>({ pose: "idle", motion: "breathe", dir: -1 });
  const size = usePetPrefs((p) => p.size);
  const height = Math.round((SAVED_HEIGHT * size) / 100);

  useEffect(() => {
    for (const pose of posesKey.split(",")) new Image().src = petPoseUrl(id, pose, stamp);   // no flicker on the first switch
  }, [id, stamp, posesKey]);

  useEffect(() => {
    const has = posesKey.split(",");
    let last = performance.now();
    let turn = useChat.getState().turn;
    let frame = 0;
    let shown = { pose: "idle", motion: "breathe" as Motion, dir: -1 as 1 | -1 };

    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      const width = lane.current?.clientWidth ?? 0;
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
      });
      brain.current = state;
      clicked.current = false;
      last = now;
      if (body.current) body.current.style.transform = `translateX(${Math.round(state.x - self / 2)}px)`;
      const next = { ...poseFor(state, activity, has), dir: state.dir };
      if (next.pose !== shown.pose || next.motion !== shown.motion || next.dir !== shown.dir) {
        shown = next;
        setLook(next);
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [posesKey, height]);

  return (
    <div className="pet-lane" ref={lane} aria-hidden="true">
      <div className="pet" ref={body} data-motion={look.motion}>
        <div className={look.dir === 1 ? "pet-face" : "pet-face left"}>
          <img
            src={petPoseUrl(id, look.pose, stamp)}
            alt=""
            draggable={false}
            style={{ height }}
            title={name}
            onClick={() => {
              clicked.current = true;
            }}
          />
        </div>
      </div>
    </div>
  );
}
