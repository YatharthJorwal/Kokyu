// Shown only when this window has not reached Kōkyū's engine for a few seconds
// (D-082): a start-up or a short blip never shows it. Reconnect starts the engine
// again if it has stopped (desktop app) and retries at once.

import { useEffect, useState } from "react";

import { actions, useChat } from "../store";

const GRACE_MS = 6000;
const STARTING_MS = 8000;

export function ConnectionBanner() {
  const online = useChat((s) => s.connection === "online");
  const [late, setLate] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    setLate(false);
    setStarting(false);
    if (online) return;
    const timer = window.setTimeout(() => setLate(true), GRACE_MS);
    return () => window.clearTimeout(timer);
  }, [online]);

  useEffect(() => {
    if (!starting) return;
    const timer = window.setTimeout(() => setStarting(false), STARTING_MS);
    return () => window.clearTimeout(timer);
  }, [starting]);

  if (online || !late) return null;
  return (
    <div className="notice connection" role="alert">
      <span className="notice-text">
        {starting ? "Starting Kōkyū's engine…" : "Kōkyū's engine is not responding. Your chats are safe on this PC."}
      </span>
      <span className="notice-actions">
        <button
          type="button"
          disabled={starting}
          onClick={() => {
            setStarting(true);
            void actions.reconnect();
          }}
        >
          Reconnect
        </button>
      </span>
    </div>
  );
}
