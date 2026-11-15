// The open thread (K1-02, K1-04): saved messages, companion dividers, the reply
// being streamed. Replies render as Markdown (FR-C-8) with Copy, and the last one
// with Regenerate (FR-C-9). The user's own lines stay plain text.

import { useEffect, useRef } from "react";

import { canPickModel, canRegenerate, lastExchange, turnFailure, visibleStream, type ChatMessage } from "../chat-state";
import { shortRef } from "../models";
import { actions, useChat } from "../store";
import { CopyButton } from "./CopyButton";
import { Markdown } from "./Markdown";
import { WakingCard } from "./WakingCard";

/** Her initial in a circle, shown when Appearance → Messages is "Bubbles" (D-073). */
function Avatar({ name }: { name: string | null }) {
  return (
    <span className="avatar" aria-hidden="true">
      {name ? name.slice(0, 1).toUpperCase() : ""}
    </span>
  );
}

function Message({ m, lastReply }: { m: ChatMessage; lastReply: boolean }) {
  const regenerable = useChat((s) => lastReply && canRegenerate(s));
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
      {m.role === "assistant" ? <Avatar name={m.speaker ?? null} /> : null}
      {m.role === "assistant" ? (
        // The actions share the name's line (shown on hover), so the reply ends at its text.
        <div className="msg-head">
          {m.speaker ? <span className="speaker">{m.speaker}</span> : null}
          <span className="msg-actions">
            <CopyButton text={m.text} label="Copy reply" />
            {regenerable ? (
              <button type="button" className="msg-action" onClick={() => actions.regenerate()} title="Ask for another reply">
                Regenerate
              </button>
            ) : null}
          </span>
        </div>
      ) : null}
      <div className="bubble">{m.role === "assistant" ? <Markdown text={m.text} /> : m.text}</div>
      {m.stopped ? <div className="meta">Stopped</div> : null}
      {m.failed ? <div className="meta">Not answered</div> : null}
      {m.sentTo ? (
        <div className="meta" title="This attachment left your PC for the chosen API model">
          Sent to {shortRef(m.sentTo)}
        </div>
      ) : null}
    </div>
  );
}

/** FR-R-5 (K1-12): a failed turn says why on the turn itself, with Retry and
 * Switch model. Never a quiet answer from another model. */
function TurnFailure() {
  const failure = useChat(turnFailure);
  const canPick = useChat(canPickModel);
  const canRetry = useChat(canRegenerate);
  if (!failure) return null;
  return (
    <div className="turn-failure" role="alert">
      <p className="turn-failure-text">{failure.text}</p>
      {failure.detail ? (
        <details className="turn-failure-detail">
          <summary>Details</summary>
          <code>{failure.detail}</code>
        </details>
      ) : null}
      <div className="turn-failure-actions">
        {failure.actions.includes("retry") && canRetry ? (
          <button type="button" onClick={() => actions.regenerate()}>
            Retry
          </button>
        ) : null}
        {failure.actions.includes("switch_model") && canPick ? (
          <button type="button" onClick={() => actions.openPicker()}>
            Switch model
          </button>
        ) : null}
        <button type="button" className="ghost" aria-label="Dismiss" onClick={() => actions.dismissNotice()}>
          ✕
        </button>
      </div>
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
  // Regenerate sits on the reply the kernel would replace, even with a divider after it.
  const exchange = lastExchange(messages);
  const lastReplyKey = exchange && exchange.length === 2 ? messages[exchange[1]].key : null;
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
      ) : (
        // A short thread sits on the input box, like a messenger; a long one scrolls as usual.
        <div className="thread-spacer" aria-hidden="true" />
      )}
      {messages.map((m) => (
        <Message key={m.key} m={m} lastReply={m.key === lastReplyKey} />
      ))}
      <TurnFailure />
      <WakingCard />
      {turn !== "idle" && streaming ? (
        // While she thinks, the line above the input box says so (ThinkingRow).
        <div className="msg assistant streaming">
          <Avatar name={companion} />
          <div className="msg-head">{companion ? <span className="speaker">{companion}</span> : null}</div>
          <div className="bubble">
            <Markdown text={streaming} />
          </div>
        </div>
      ) : null}
      <div ref={end} />
    </div>
  );
}
