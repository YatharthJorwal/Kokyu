// "Yuri is waking up…" (K1-10, FR-M-6, D-054): shown in the chat while the
// kernel loads the chat model, so a two-minute load of a big model reads as the
// companion getting ready instead of a frozen app. The line changes every few
// seconds; the model and the time so far sit underneath. A failed load says so
// with Try again and Switch model; a finished one says she is awake, briefly.

import { useEffect, useRef, useState } from "react";

import { canPickModel, currentModelRef } from "../chat-state";
import { awakeLine, failedLine, formatElapsed, wakingLine } from "../models";
import { actions, useChat } from "../store";

const AWAKE_MS = 2600;

export function WakingCard() {
  const status = useChat((s) => s.modelStatus);
  const current = useChat(currentModelRef);
  const name = useChat((s) => s.companion?.name ?? null);
  const canPick = useChat(canPickModel);
  const [now, setNow] = useState(() => Date.now());
  const receivedAt = useRef(Date.now());
  const lastReady = useRef<string | null>(null);
  const switching = useRef(false);
  const [awake, setAwake] = useState(false);
  const previous = useRef(status?.state ?? null);

  // Each new status restarts the local clock from the kernel's elapsed time.
  useEffect(() => {
    receivedAt.current = Date.now();
    setNow(Date.now());
    const was = previous.current;
    previous.current = status?.state ?? null;
    if (status?.state === "loading") {
      switching.current = lastReady.current !== null && lastReady.current !== status.model_ref;
    }
    if (status?.state === "ready") {
      lastReady.current = status.model_ref;
      if (was === "loading") {
        setAwake(true);
        const t = window.setTimeout(() => setAwake(false), AWAKE_MS);
        return () => window.clearTimeout(t);
      }
    }
    setAwake(false);
    return undefined;
  }, [status]);

  const loading = status?.state === "loading";
  useEffect(() => {
    if (!loading) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [loading]);

  if (!status) return null;
  // A load of another thread's model (the kernel is shared) is not this chat's news.
  if (current !== null && status.model_ref !== null && status.model_ref !== current) return null;

  if (status.state === "loading") {
    const elapsed = (status.elapsed_s ?? 0) + (now - receivedAt.current) / 1000;
    const line = wakingLine(name, elapsed, switching.current);
    // Screen readers hear the line and the model, not a timer ticking every second.
    return (
      <div className="waking">
        <span className="waking-avatar" aria-hidden="true">
          <span className="zz">z</span>
          <span className="zz">z</span>
          <span className="zz">z</span>
        </span>
        <span className="waking-text" role="status">
          {/* keyed on the text so each new line fades in */}
          <span className="waking-line" key={line}>
            {line}
          </span>
          <span className="waking-meta">
            Loading {status.label ?? "the model"}
            <span aria-hidden="true"> · {formatElapsed(elapsed)}</span>
          </span>
        </span>
      </div>
    );
  }

  if (status.state === "failed") {
    return (
      <div className="waking failed" role="alert">
        <span className="waking-text">
          <span className="waking-line">{failedLine(name)}</span>
          <span className="waking-meta">
            {status.label ?? "The model"}: {status.message ?? "unknown error"}
          </span>
        </span>
        {/* Only the window that drives the kernel can act; others just watch. */}
        {canPick ? (
          <span className="waking-actions">
            <button type="button" onClick={() => actions.retryLoad()}>
              Try again
            </button>
            <button type="button" onClick={() => actions.openPicker()}>
              Switch model
            </button>
          </span>
        ) : null}
      </div>
    );
  }

  if (awake) {
    return (
      <div className="waking awake" role="status">
        <span className="waking-line">{awakeLine(name)}</span>
      </div>
    );
  }
  return null;
}
