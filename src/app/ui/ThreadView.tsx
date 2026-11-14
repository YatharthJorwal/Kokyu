// The open thread (K1-02, K1-04): saved messages, companion dividers, the reply
// being streamed. Replies render as Markdown (FR-C-8) with Copy, and the last one
// with Regenerate (FR-C-9). The user's own lines stay plain text.

import { useEffect, useRef } from "react";

import { canRegenerate, visibleStream, type ChatMessage } from "../chat-state";
import { actions, useChat } from "../store";
import { CopyButton } from "./CopyButton";
import { Markdown } from "./Markdown";
import { WakingCard } from "./WakingCard";

function Message({ m, last }: { m: ChatMessage; last: boolean }) {
  const regenerable = useChat((s) => last && m.role === "assistant" && canRegenerate(s));
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
      <div className="bubble">{m.role === "assistant" ? <Markdown text={m.text} /> : m.text}</div>
      {m.stopped ? <div className="meta">Stopped</div> : null}
      {m.failed ? <div className="meta">Not answered</div> : null}
      {m.role === "assistant" ? (
        <div className="msg-actions">
          <CopyButton text={m.text} label="Copy reply" />
          {regenerable ? (
            <button type="button" className="msg-action" onClick={() => actions.regenerate()} title="Ask for another reply">
              Regenerate
            </button>
          ) : null}
        </div>
      ) : null}
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
      {messages.map((m, i) => (
        <Message key={m.key} m={m} last={i === messages.length - 1} />
      ))}
      <WakingCard />
      {turn !== "idle" ? (
        <div className="msg assistant streaming">
          {companion ? <div className="speaker">{companion}</div> : null}
          <div className="bubble">
            {streaming ? <Markdown text={streaming} /> : <span className="typing" aria-label="Thinking">•••</span>}
          </div>
        </div>
      ) : null}
      <div ref={end} />
    </div>
  );
}
