// The open thread (K1-02): saved messages, companion dividers, the reply being
// streamed. Plain text for now; Markdown, Copy and Regenerate are K1-04.

import { useEffect, useRef } from "react";

import { visibleStream, type ChatMessage } from "../chat-state";
import { useChat } from "../store";
import { WakingCard } from "./WakingCard";

function Message({ m }: { m: ChatMessage }) {
  if (m.role === "divider") {
    return (
      <div className="divider" role="separator">
        <span>{m.text}</span>
      </div>
    );
  }
  const classes = ["msg", m.role, m.pending ? "pending" : "", m.failed ? "failed" : ""].filter(Boolean).join(" ");
  return (
    <div className={classes}>
      {m.role === "assistant" && m.speaker ? <div className="speaker">{m.speaker}</div> : null}
      <div className="bubble">{m.text}</div>
      {m.stopped ? <div className="meta">Stopped</div> : null}
      {m.failed ? <div className="meta">Not answered</div> : null}
    </div>
  );
}

export function ThreadView() {
  const messages = useChat((s) => s.messages);
  const turn = useChat((s) => s.turn);
  const streaming = useChat(visibleStream);
  const companion = useChat((s) => s.companion?.name ?? null);
  const modelState = useChat((s) => s.modelStatus?.state ?? null);
  const end = useRef<HTMLDivElement>(null);
  // Whether the view is pinned to the newest message. A model load finishing
  // must not yank someone who scrolled up to read history.
  const atBottom = useRef(true);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.length, streaming, turn]);

  useEffect(() => {
    if (atBottom.current) end.current?.scrollIntoView({ block: "end" });
  }, [modelState]);

  return (
    <div
      className="thread"
      aria-live="polite"
      onScroll={(e) => {
        const el = e.currentTarget;
        atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
      }}
    >
      {messages.length === 0 && turn === "idle" ? (
        <div className="empty">
          <p className="empty-title">{companion ? `Talk to ${companion}` : "Start a conversation"}</p>
          <p className="muted">Your conversations are saved on this PC.</p>
        </div>
      ) : null}
      {messages.map((m) => (
        <Message key={m.key} m={m} />
      ))}
      <WakingCard />
      {turn !== "idle" ? (
        <div className="msg assistant streaming">
          {companion ? <div className="speaker">{companion}</div> : null}
          <div className="bubble">
            {streaming || <span className="typing" aria-label="Thinking">•••</span>}
          </div>
        </div>
      ) : null}
      <div ref={end} />
    </div>
  );
}
