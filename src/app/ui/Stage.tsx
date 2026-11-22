// The Stage (K2-01/02, D-104, FR-ST-1..5, 7): her VRM in place of the conversation,
// with her latest words as a caption above the same input box. The scene itself is
// src/engine/stage.ts; this mounts its canvas, feeds it her mood and shows the panel
// when her model cannot be loaded (FR-ST-5).

import { useEffect, useRef, useState } from "react";

import { getSpeechProgress } from "../../engine/lipsync";
import { createStage, type Stage as StageApi } from "../../engine/stage";
import { KERNEL_HTTP_URL } from "../../net/kernel";
import { activeWord, sentences, silentDuration, splitWords, wordStarts, wordState } from "../caption";
import { actions, speakingLine, useChat } from "../store";

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

const HOLD_MS = 900;   // a finished line stays this long before it fades
const GAP_MS = 450;    // and the next waits for the fade

type Reply = { key: string; text: string } | null;

function lastReply(messages: readonly { key: string; role: string; text: string }[]): Reply {
  const m = messages[messages.length - 1];
  return m && m.role === "assistant" ? { key: m.key, text: m.text } : null;
}

/** On the Stage she speaks: Read aloud goes on when it opens, and back off when it closes
 *  if the Stage turned it on (D-113). */
function useStageVoice() {
  const known = useChat((s) => s.readAloud !== null);
  const turnedOn = useRef(false);
  useEffect(() => {
    const status = useChat.getState().readAloud;
    if (status && !status.on && !turnedOn.current) {
      turnedOn.current = true;
      actions.setReadAloud(true);
    }
  }, [known]);
  useEffect(
    () => () => {
      if (turnedOn.current && useChat.getState().readAloud?.on) actions.setReadAloud(false);
    },
    [],
  );
}

/** Her words, Yuri's way (D-111, D-113): one line at a time, word by word at speaking
 *  pace, then gone. With her voice the line is the clip playing; without it (Read aloud
 *  off, or her voice failed) the finished reply is paced out sentence by sentence. */
function Caption() {
  useStageVoice();
  const busy = useChat((s) => s.turn !== "idle");
  const box = useRef<HTMLDivElement>(null);
  const [speaking, setSpeaking] = useState(false);

  // Drawn straight into the DOM from one rAF loop, as in Yuri: no React render per word.
  useEffect(() => {
    let frame = 0;
    let line: string | null = null;
    let spans: HTMLSpanElement[] = [];
    let starts: number[] = [];
    let active = -1;
    let seen = lastReply(useChat.getState().messages)?.key ?? null;   // never replay an old reply
    let wasBusy = false;
    let queue: string[] = [];
    let started = 0;
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
    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      const s = useChat.getState();
      if (s.turn !== "idle") {
        wasBusy = true;
        queue = [];
      } else if (wasBusy) {
        wasBusy = false;
        const reply = lastReply(s.messages);
        if (reply && reply.key !== seen) {
          seen = reply.key;
          const voiced = s.readAloud?.on === true && s.readAloud.state !== "failed";
          queue = voiced ? [] : sentences(reply.text);
          started = now;
        }
      }
      const voiceLine = speakingLine();
      let text: string | null = voiceLine;
      let fraction = 0;
      if (voiceLine !== null) {
        queue = [];
        const progress = getSpeechProgress();
        if (progress && progress.duration > 0) fraction = Math.min(1, progress.elapsed / progress.duration);
      } else if (queue.length > 0) {
        const ms = silentDuration(queue[0]) * 1000;
        const at = now - started;
        if (at >= ms + HOLD_MS + GAP_MS) {
          queue.shift();
          started = now;
        } else if (at < ms + HOLD_MS) {
          text = queue[0];
          fraction = Math.min(1, at / ms);
        }
      }
      if (text !== line) {
        line = text;
        setSpeaking(text !== null);
        const el = box.current;
        if (!el) return;
        if (text === null) return;   // the old words fade out with the box, then are replaced
        const words = splitWords(text);
        starts = wordStarts(words);
        spans = words.map((word) => {
          const span = document.createElement("span");
          span.className = "caption-word";
          span.textContent = word;
          return span;
        });
        el.replaceChildren(...spans);
        active = -1;
        show(0);   // at once: a clip's length is not known for a frame or two
      }
      if (line !== null) show(activeWord(starts, fraction));
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <>
      <div ref={box} className={speaking ? "stage-caption visible" : "stage-caption"} aria-live="polite" />
      {busy && !speaking ? <p className="stage-caption-text">…</p> : null}
    </>
  );
}
