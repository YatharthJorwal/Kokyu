// The Stage (K2-01/02, D-104, FR-ST-1..5, 7): her VRM in place of the conversation,
// with her latest words as a caption above the same input box. The scene itself is
// src/engine/stage.ts; this mounts its canvas, feeds it her mood and shows the panel
// when her model cannot be loaded (FR-ST-5).

import { useEffect, useRef, useState } from "react";

import { createStage, type Stage as StageApi } from "../../engine/stage";
import { KERNEL_HTTP_URL } from "../../net/kernel";
import { visibleStream } from "../chat-state";
import { useChat } from "../store";

export function Stage() {
  const id = useChat((s) => s.companion?.id ?? null);
  const name = useChat((s) => s.companion?.name ?? "");
  return (
    <div className="stage">
      {id ? <StageScene key={id} id={id} name={name} /> : null}
      <Caption />
    </div>
  );
}

function StageScene({ id, name }: { id: string; name: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");

  useEffect(() => {
    let stage: StageApi | null = null;
    let gone = false;
    // A fresh canvas per mount: two renderers on one canvas share its WebGL context
    // and corrupt each other's state (React mounts twice in development).
    const canvas = document.createElement("canvas");
    canvas.className = "stage-canvas";
    box.current?.appendChild(canvas);
    const url = `${KERNEL_HTTP_URL}/waifus/${encodeURIComponent(id)}/vrm`;
    createStage(canvas, url, { busy: () => useChat.getState().turn !== "idle" })
      .then((s) => {
        if (gone) return s.dispose();
        stage = s;
        setState("ready");
      })
      .catch((err) => {
        console.warn("[kokyu] the stage could not load her model", err);
        if (!gone) setState("failed");
      });
    // Her mood follows each finished reply's emotion tag (FR-ST-7).
    const unsubscribe = useChat.subscribe((s, before) => {
      if (s.mood !== before.mood && s.mood) stage?.setEmotion(s.mood.emotion);
    });
    return () => {
      gone = true;
      unsubscribe();
      stage?.dispose();
      canvas.remove();
    };
  }, [id]);

  return (
    <>
      <div ref={box} className={state === "ready" ? "stage-box" : "stage-box hidden"} />
      {state === "loading" ? <p className="stage-note">Bringing {name} in…</p> : null}
      {state === "failed" ? (
        <div className="stage-note failed">
          <strong>{name}'s model could not be loaded.</strong>
          <span>Her pack needs a working .vrm file. Settings → Doctor checks Kōkyū's engine; switch back to Chat to keep talking.</span>
        </div>
      ) : null}
    </>
  );
}

/** The end of a long reply, cut at a word: the caption shows what she is saying now. */
function tail(text: string): string {
  return text.length <= 240 ? text : "…" + text.slice(-240).replace(/^\S*\s/, "");
}

/** Her latest words: the reply being written, else her last reply. */
function Caption() {
  const text = useChat((s) => {
    if (s.turn === "replying") return visibleStream(s);
    for (let i = s.messages.length - 1; i >= 0; i -= 1) {
      const m = s.messages[i];
      if (m.role === "assistant") return m.text;
      if (m.role === "user") return "";
    }
    return "";
  });
  const thinking = useChat((s) => s.turn === "thinking");
  if (!text && !thinking) return null;
  return (
    <p className="stage-caption" aria-live="polite">
      {thinking && !text ? "…" : tail(text)}
    </p>
  );
}
