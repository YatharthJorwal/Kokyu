// The open thread (K1-02, K1-04, UI1-07): saved messages, companion dividers, the
// reply being streamed. Replies render as Markdown (FR-C-8). A run of messages from
// one voice shows her face and name once. Hovering a message shows its time (and a
// reply's model) with icon actions: Copy, Regenerate on the last reply (FR-C-9), Edit
// on the last line (D-092). The user's own lines stay plain text in a chat; in a
// roleplay thread both sides render the story's way (FR-MODE-7). Reading older
// messages is never interrupted: new text only scrolls the view when it is already
// at the bottom, and a pill jumps back down.

import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

import {
  canPickModel,
  canRegenerate,
  canSend,
  currentMode,
  editableKey,
  lastExchange,
  modelLabel,
  modelLoadingHere,
  startsGroup,
  turnFailure,
  visibleStream,
  type ChatMessage,
} from "../chat-state";
import { messageTime } from "../history";
import { THINKING_LINES, THINKING_STEP_S, thinkingLine } from "../models";
import { actions, useChat } from "../store";
import { CopyButton } from "./CopyButton";
import { Icon } from "./Icon";
import { Markdown } from "./Markdown";
import { Portrait } from "./Portrait";
import { WakingCard } from "./WakingCard";

/** Her face in a circle, shown when Appearance → Messages is "Bubbles" (D-073, D-091). */
function Avatar({ id, name }: { id: string | null | undefined; name: string | null }) {
  const portrait = useChat((s) => s.roster.find((w) => w.id === id)?.portrait ?? null);
  const known = useChat((s) => s.roster.some((w) => w.id === id));
  return (
    <Portrait
      id={id}
      name={name ?? ""}
      portrait={portrait}
      className="avatar"
      title={known && name ? `${name}'s profile` : undefined}
      onClick={known && id ? () => actions.openProfile(id) : undefined}
    />
  );
}

/** The bar that appears over a message on hover or focus (UI1-07). */
function ActionBar({ m, lastReply, editable, onEdit }: { m: ChatMessage; lastReply: boolean; editable: boolean; onEdit: () => void }) {
  const regenerable = useChat((s) => lastReply && canRegenerate(s));
  const model = useChat((s) => (m.role === "assistant" && m.model ? modelLabel(s, m.model) : null));
  const when = m.ts ? messageTime(m.ts, Date.now()) : null;
  const facts = [when, model].filter(Boolean).join(" · ");
  return (
    <div className="msg-actions">
      {facts ? <span className="msg-when">{facts}</span> : null}
      <CopyButton icon text={m.text} label={m.role === "assistant" ? "Copy reply" : "Copy message"} />
      {regenerable ? (
        <button type="button" className="msg-action icon-action" aria-label="Regenerate" title="Ask for another reply" onClick={() => actions.regenerate()}>
          <Icon name="regenerate" />
        </button>
      ) : null}
      {editable ? (
        <button type="button" className="msg-action icon-action" aria-label="Edit" title="Edit and send again" onClick={onEdit}>
          <Icon name="edit" />
        </button>
      ) : null}
    </div>
  );
}

/** Edit and resend the last line (D-092): the new words replace the old exchange. */
function EditBox({ text, onDone }: { text: string; onDone: () => void }) {
  const [draft, setDraft] = useState(text);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = box.current;
    el?.focus();
    el?.setSelectionRange(el.value.length, el.value.length);
  }, []);
  const send = () => {
    if (draft.trim() === text.trim() || actions.resend(draft)) onDone();
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      onDone();
    }
  };
  return (
    <div className="edit-box">
      <textarea
        ref={box}
        value={draft}
        aria-label="Edit your message"
        rows={Math.min(8, draft.split("\n").length + 1)}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKey}
      />
      <div className="edit-actions">
        <button type="button" className="ghost" onClick={onDone}>
          Cancel
        </button>
        <button type="button" className="primary" disabled={!draft.trim()} onClick={send}>
          Send
        </button>
      </div>
    </div>
  );
}

function Message({ m, first, lastReply, editable, roleplay }: { m: ChatMessage; first: boolean; lastReply: boolean; editable: boolean; roleplay: boolean }) {
  const sentTo = useChat((s) => (m.sentTo ? modelLabel(s, m.sentTo) : null));
  const [editing, setEditing] = useState(false);
  if (m.role === "divider") {
    return (
      <div className="divider" role="separator">
        <span>{m.text}</span>
      </div>
    );
  }
  const classes = ["msg", m.role, first ? "" : "cont", m.pending ? "pending" : "", m.failed ? "failed" : "", editing ? "editing" : ""]
    .filter(Boolean)
    .join(" ");
  const her = m.role === "assistant" && first;
  return (
    <div className={classes}>
      {her ? <Avatar id={m.speakerId} name={m.speaker ?? null} /> : null}
      {her && m.speaker ? (
        <div className="msg-head">
          <span className="speaker">{m.speaker}</span>
        </div>
      ) : null}
      {editing ? (
        <EditBox text={m.text} onDone={() => setEditing(false)} />
      ) : (
        <>
          <div className="bubble">{m.role === "assistant" || roleplay ? <Markdown text={m.text} roleplay={roleplay} /> : m.text}</div>
          {m.pending ? null : <ActionBar m={m} lastReply={lastReply} editable={editable} onEdit={() => setEditing(true)} />}
        </>
      )}
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

/** Ways to begin a new chat, one click each (UI1-09). Plain openers that suit any
 * companion; what she says back is hers. */
const STARTERS = ["How was your day?", "Tell me about yourself", "I could use some advice", "Let's play a game"];

/** A new chat (UI1-09): her face, her name and a few ways to begin. */
function EmptyChat() {
  const companion = useChat((s) => s.companion);
  const ready = useChat(canSend);
  return (
    <div className="empty">
      {companion ? (
        <Portrait
          id={companion.id}
          name={companion.name}
          portrait={companion.portrait}
          className="empty-face"
          title={`${companion.name}'s profile`}
          onClick={() => actions.openProfile(companion.id)}
        />
      ) : null}
      <p className="empty-title">{companion ? `Talk to ${companion.name}` : "Start a conversation"}</p>
      <p className="muted">Your conversations are saved on this PC.</p>
      {ready ? (
        <div className="starters">
          {STARTERS.map((line) => (
            <button key={line} type="button" className="starter" onClick={() => actions.send(line)}>
              {line}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** While she thinks, her reply's place says so (UI1-07, D-063's changing line). The
 * waking-up card speaks while the model loads, so this waits for it. */
function ThinkingReply({ id, name }: { id: string | null; name: string | null }) {
  const [step, setStep] = useState(0);
  const [start] = useState(() => Math.floor(Math.random() * THINKING_LINES.length));
  useEffect(() => {
    const t = window.setInterval(() => setStep((n) => n + 1), THINKING_STEP_S * 1000);
    return () => window.clearInterval(t);
  }, []);
  const text = thinkingLine(name, step, start);
  return (
    <div className="msg assistant thinking">
      <Avatar id={id} name={name} />
      <div className="msg-head">{name ? <span className="speaker">{name}</span> : null}</div>
      <div className="bubble">
        <span className="thinking-line" role="status">
          {/* Screen readers hear it once; the changing words are for the eyes. */}
          <span className="sr-only">{name ?? "She"} is thinking</span>
          <span aria-hidden="true" key={text}>
            {text}
          </span>
        </span>
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
  const loading = useChat(modelLoadingHere);
  const threadId = useChat((s) => s.thread?.id ?? null);
  const editable = useChat(editableKey);
  // The mode is the open thread's (FR-MODE-1), never the companion's.
  const roleplay = useChat((s) => currentMode(s) === "roleplay");
  const scenario = useChat((s) => s.thread?.scenario ?? null);
  const box = useRef<HTMLDivElement>(null);
  // Regenerate sits on the reply the kernel would replace, even with a divider after it.
  const exchange = lastExchange(messages);
  const lastReplyKey = exchange && exchange.length === 2 ? messages[exchange[1]].key : null;
  // Whether the view is pinned to the newest message. Someone reading history is
  // never pulled down by a reply, a model load or a remark.
  const atBottom = useRef(true);
  const [away, setAway] = useState(false);
  const last = messages[messages.length - 1];
  const justSent = last?.role === "user" && last.pending === true;

  const toEnd = (smooth = false) => {
    const el = box.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth && !reduce ? "smooth" : "auto" });
  };

  // Another thread opens at its newest message.
  useLayoutEffect(() => {
    atBottom.current = true;
    setAway(false);
    toEnd();
  }, [threadId]);

  // A smaller window (or a banner above the input) keeps the newest message in view.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const watch = new ResizeObserver(() => {
      if (atBottom.current) toEnd();
    });
    watch.observe(el);
    return () => watch.disconnect();
  }, []);

  useLayoutEffect(() => {
    // The user's own line always brings the view down to it.
    if (justSent) atBottom.current = true;
    if (atBottom.current) toEnd();
  }, [messages.length, streaming, turn, modelState, justSent]);

  return (
    <div className="thread-wrap">
      <div
        ref={box}
        className="thread"
        aria-live="polite"
        onScroll={(e) => {
          const el = e.currentTarget;
          const bottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
          atBottom.current = bottom;
          setAway(!bottom);
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
            <EmptyChat />
          )
        ) : (
          // A short thread sits on the input box, like a messenger; a long one scrolls as usual.
          <div className="thread-spacer" aria-hidden="true" />
        )}
        {messages.map((m, i) => (
          <Message
            key={m.key}
            m={m}
            first={startsGroup(messages, i)}
            lastReply={m.key === lastReplyKey}
            editable={m.key === editable}
            roleplay={roleplay}
          />
        ))}
        <TurnFailure />
        <WakingCard />
        {turn === "thinking" && !streaming && !loading ? <ThinkingReply id={companionId} name={companion} /> : null}
        {turn !== "idle" && streaming ? (
          <div className="msg assistant streaming">
            <Avatar id={companionId} name={companion} />
            <div className="msg-head">{companion ? <span className="speaker">{companion}</span> : null}</div>
            <div className="bubble">
              <Markdown text={streaming} roleplay={roleplay} />
            </div>
          </div>
        ) : null}
        <div className="thread-end" />
      </div>
      {away && messages.length > 0 ? (
        <button type="button" className="jump-latest" onClick={() => toEnd(true)}>
          <Icon name="down" size={14} />
          Jump to latest
        </button>
      ) : null}
    </div>
  );
}
