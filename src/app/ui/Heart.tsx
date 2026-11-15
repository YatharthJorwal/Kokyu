// The status heart (K1-05, FR-C-5): calm when idle,
// a fast arc chasing round it while she thinks, a heartbeat while she replies,
// and a slow arc while the kernel is not reachable. CSS in app.css; it stops
// moving under prefers-reduced-motion.

import { useChat } from "../store";

const PATH =
  "M12 20.5C12 20.5 3 14.6 3 8.7C3 5.9 5.1 4 7.6 4C9.4 4 11 5 12 6.6C13 5 14.6 4 16.4 4C18.9 4 21 5.9 21 8.7C21 14.6 12 20.5 12 20.5Z";

const LABELS = { offline: "Connecting", idle: "Idle", thinking: "Thinking", replying: "Replying" } as const;

export function Heart() {
  const state = useChat((s) => (s.connection !== "online" ? "offline" : s.turn === "idle" ? "idle" : s.turn));
  return (
    <span className={`heart ${state}`} role="img" aria-label={LABELS[state]} title={LABELS[state]}>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path className="heart-fill" d={PATH} />
        <path className="heart-track" d={PATH} />
        <path className="heart-arc" d={PATH} pathLength={100} />
      </svg>
    </span>
  );
}
