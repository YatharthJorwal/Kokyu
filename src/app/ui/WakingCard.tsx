// The model loading strip (K1-10, FR-M-6, D-054; compact above the input box since
// D-096): which model is loading, a changing line ("<companion> is waking up…") so a
// two-minute load reads as her getting ready, and the time so far. A failed load says so
// with Try again and Switch model (and Unload X when graphics memory is what is
// missing, K1-09b); a finished one says she is awake, briefly.

import { useEffect, useRef, useState } from "react";

import { canPickModel, modelStatusHere } from "../chat-state";
import { awakeLine, failedLine, formatElapsed, wakingLine } from "../models";
import { actions, useChat } from "../store";
import { Icon } from "./Icon";

const AWAKE_MS = 2600;

export function WakingCard() {
  const status = useChat(modelStatusHere);
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

  if (status.state === "loading") {
    const elapsed = (status.elapsed_s ?? 0) + (now - receivedAt.current) / 1000;
    const line = wakingLine(name, elapsed, switching.current);
    // Screen readers hear the line and the model, not a timer ticking every second.
    return (
      <div className="waking" role="status">
        <span className="spinner" aria-hidden="true" />
        <span className="waking-main">Loading {status.label ?? "the model"}</span>
        {/* keyed on the text so each new line fades in */}
        <span className="waking-line" key={line}>
          {line}
        </span>
        <span className="waking-time" aria-hidden="true">
          {formatElapsed(elapsed)}
        </span>
      </div>
    );
  }

  if (status.state === "failed") {
    return (
      <div className="waking failed" role="alert">
        <span className="waking-main">{failedLine(name)}</span>
        <span className="waking-line">
          {status.label ?? "The model"}: {status.message ?? "unknown error"}
        </span>
        {/* Only the window that drives the kernel can act; others just watch. */}
        {canPick ? (
          <span className="waking-actions">
            {(status.unload ?? []).map((u) => (
              <button key={u.ref} type="button" onClick={() => actions.unloadModel(u.ref)}>
                Unload {u.label}
              </button>
            ))}
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
        <Icon name="check" size={14} />
        <span className="waking-main">{awakeLine(name)}</span>
      </div>
    );
  }
  return null;
}
