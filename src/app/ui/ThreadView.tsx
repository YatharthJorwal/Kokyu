// The open thread (K1-02, K1-04): saved messages, companion dividers, the reply
// being streamed. Replies render as Markdown (FR-C-8) with Copy, and the last one
// with Regenerate (FR-C-9). The user's own lines stay plain text in a chat; in a
// roleplay thread both sides render the story's way (FR-MODE-7).

import { useEffect, useRef } from "react";

import {
  canPickModel,
  canRegenerate,
  currentMode,
  lastExchange,
  modelLabel,
  turnFailure,
  visibleStream,
  type ChatMessage,
} from "../chat-state";
import { actions, useChat } from "../store";
import { CopyButton } from "./CopyButton";
import { Markdown } from "./Markdown";
import { Portrait } from "./Portrait";
import { WakingCard } from "./WakingCard";

/** Her face in a circle, shown when Appearance → Messages is "Bubbles" (D-073, D-091). */
function Avatar({ id, name }: { id: string | null | undefined; name: string | null }) {
  const portrait = useChat((s) => s.roster.find((w) => w.id === id)?.portrait ?? null);
  return <Portrait id={id} name={name ?? ""} portrait={portrait} className="avatar" />;
}

function Message({ m, lastReply, roleplay }: { m: ChatMessage; lastReply: boolean; roleplay: boolean }) {
  const regenerable = useChat((s) => lastReply && canRegenerate(s));
  const sentTo = useChat((s) => (m.sentTo ? modelLabel(s, m.sentTo) : null));
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
      {m.role === "assistant" ? <Avatar id={m.speakerId} name={m.speaker ?? null} /> : null}
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
      <div className="bubble">
        {m.role === "assistant" || roleplay ? <Markdown text={m.text} roleplay={roleplay} /> : m.text}
      </div>
      {m.stopped ? <div className="meta">Stopped</div> : null}
      {m.failed ? <div className="meta">Not answered</div> : null}
      {m.sentTo ? (
        <div className="meta" title="This attachment left your PC for the chosen API model">
          Sent to {sentTo}
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
  const companionId = useChat((s) => s.companion?.id ?? null);
  const modelState = useChat((s) => s.modelStatus?.state ?? null);
  // The mode is the open thread's (FR-MODE-1), never the companion's.
  const roleplay = useChat((s) => currentMode(s) === "roleplay");
  const scenario = useChat((s) => s.thread?.scenario ?? null);
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
        roleplay ? (
          <div className="empty">
            <p className="empty-title">{scenario?.title || "A new story"}</p>
            {scenario?.setting ? <p className="empty-setting">{scenario.setting}</p> : null}
            <p className="muted">Write *actions* in asterisks, and (OOC …) to step out of the story.</p>
          </div>
        ) : (
          <div className="empty">
            <p className="empty-title">{companion ? `Talk to ${companion}` : "Start a conversation"}</p>
            <p className="muted">Your conversations are saved on this PC.</p>
          </div>
        )
      ) : (
        // A short thread sits on the input box, like a messenger; a long one scrolls as usual.
        <div className="thread-spacer" aria-hidden="true" />
      )}
      {messages.map((m) => (
        <Message key={m.key} m={m} lastReply={m.key === lastReplyKey} roleplay={roleplay} />
      ))}
      <TurnFailure />
      <WakingCard />
      {turn !== "idle" && streaming ? (
        // While she thinks, the line above the input box says so (ThinkingRow).
        <div className="msg assistant streaming">
          <Avatar id={companionId} name={companion} />
          <div className="msg-head">{companion ? <span className="speaker">{companion}</span> : null}</div>
          <div className="bubble">
            <Markdown text={streaming} roleplay={roleplay} />
          </div>
        </div>
      ) : null}
      <div ref={end} />
    </div>
  );
}
