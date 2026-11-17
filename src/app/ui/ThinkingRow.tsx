// The status heart, just above the input box (K1-05, FR-C-5, D-063): calm while
// idle; spinning beside a line that changes every few seconds while she thinks;
// one beat when the first word of the reply arrives, as the line fades. The
// waking-up card speaks while the model loads, so the line waits for it. Reduced
// motion: no spin and no fade, only the words change.

import { useEffect, useRef, useState } from "react";

import { modelLoadingHere } from "../chat-state";
import { THINKING_LINES, THINKING_STEP_S, thinkingLine } from "../models";
import { useChat } from "../store";
import { Heart } from "./Heart";

const FADE_MS = 600;

export function ThinkingRow() {
  const name = useChat((s) => s.companion?.name ?? null);
  const thinking = useChat((s) => s.turn === "thinking" && !modelLoadingHere(s));
  const [step, setStep] = useState(0);
  const [line, setLine] = useState<"off" | "on" | "fading">("off");
  const start = useRef(0);

  useEffect(() => {
    if (thinking) {
      start.current = Math.floor(Math.random() * THINKING_LINES.length);
      setStep(0);
      setLine("on");
      const t = window.setInterval(() => setStep((n) => n + 1), THINKING_STEP_S * 1000);
      return () => window.clearInterval(t);
    }
    setLine((was) => (was === "on" ? "fading" : was));
    const t = window.setTimeout(() => setLine("off"), FADE_MS);
    return () => window.clearTimeout(t);
  }, [thinking]);

  const text = thinkingLine(name, step, start.current);
  return (
    <div className="thinking-row">
      <Heart />
      {line !== "off" ? (
        <span className={line === "fading" ? "thinking-line fading" : "thinking-line"} role="status">
          {/* Screen readers hear it once; the changing words are for the eyes. */}
          <span className="sr-only">{name ?? "She"} is thinking</span>
          <span aria-hidden="true" key={text}>
            {text}
          </span>
        </span>
      ) : null}
    </div>
  );
}
