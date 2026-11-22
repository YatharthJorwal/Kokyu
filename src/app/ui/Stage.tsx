// The Stage (K2-01/02, D-104, FR-ST-1..5, 7): her VRM in place of the conversation,
// with her latest words as a caption above the same input box. The scene itself is
// src/engine/stage.ts; this mounts its canvas, feeds it her mood and shows the panel
// when her model cannot be loaded (FR-ST-5).

import { useEffect, useRef, useState } from "react";

import { getSpeechProgress } from "../../engine/lipsync";
import { createStage, type Stage as StageApi } from "../../engine/stage";
import { KERNEL_HTTP_URL } from "../../net/kernel";
import { activeWord, splitWords, wordStarts, wordState } from "../caption";
import { visibleStream } from "../chat-state";
import { speakingLine, useChat } from "../store";

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
  const box = useRef<HTMLDivElement>(null);
  const [speaking, setSpeaking] = useState(false);

  // Yuri's caption (D-111): while her voice plays, its words pop in one at a time
  // with the clip, the one being said glowing. Drawn straight into the DOM from one
  // rAF loop, as in Yuri: no React render per word.
  useEffect(() => {
    let frame = 0;
    let line: string | null = null;
    let spans: HTMLSpanElement[] = [];
    let starts: number[] = [];
    let active = -1;
    const show = (index: number) => {
      if (index === active) return;
      active = index;
      spans.forEach((el, i) => {
        const state = wordState(i, index);
        const first = state === "active" && !el.classList.contains("shown");
        el.className = state === "hidden" ? "caption-word" : `caption-word shown ${state}`;
        if (first) {
          void el.offsetWidth;   // restart the pop for a word shown for the first time
          el.classList.add("pop");
        }
      });
    };
    const tick = () => {
      frame = requestAnimationFrame(tick);
      const now = speakingLine();
      if (now !== line) {
        line = now;
        setSpeaking(now !== null);
        const el = box.current;
        if (!el) return;
        const words = now ? splitWords(now) : [];
        starts = wordStarts(words);
        spans = words.map((word) => {
          const span = document.createElement("span");
          span.className = "caption-word";
          span.textContent = word;
          return span;
        });
        el.replaceChildren(...spans);
        active = -1;
        if (spans.length > 0) show(0);   // at once: the clip's length is not known for a frame or two
      }
      const progress = line ? getSpeechProgress() : null;
      if (progress && progress.duration > 0) show(activeWord(starts, Math.min(1, progress.elapsed / progress.duration)));
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <>
      <div ref={box} className={speaking ? "stage-caption visible" : "stage-caption"} aria-live="polite" />
      {/* Read aloud off, or before her voice starts: the latest words, in the same lettering. */}
      {!speaking && (text || thinking) ? <p className="stage-caption-text">{thinking && !text ? "…" : tail(text)}</p> : null}
    </>
  );
}
