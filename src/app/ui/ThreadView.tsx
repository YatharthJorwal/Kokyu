// The open thread (K1-02, K1-04, UI1-07): saved messages, companion dividers, the
// reply being streamed. Replies render as Markdown (FR-C-8). A run of messages from
// one voice shows her face and name once, with a speaker that reads the message aloud
// (D-099). Each message has a ⋯ beside it (D-100): a card with its time (and a reply's
// model), Copy, Edit on the last line (D-092), Rewind to here, Pin (roleplay) and New
// chat from here. Under her latest reply: Regenerate, and arrows through the replies
// it has written (swipes, D-100). The user's own lines stay plain text in a chat; in a
// roleplay thread both sides render the story's way (FR-MODE-7). Reading older
// messages is never interrupted: new text only scrolls the view when it is already
// at the bottom, and a pill jumps back down. While she thinks, her face, the heart
// and a changing word sit where her reply will appear; the reply then types out
// letter by letter (D-096).

import { Fragment, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";

import {
  canActOnMessages,
  canPickModel,
  canRegenerate,
  canSend,
  currentMode,
  editableKey,
  lastExchange,
  modelLabel,
  startsGroup,
  turnFailure,
  visibleStream,
  type ChatMessage,
} from "../chat-state";
import { TEXT_MAX } from "../../net/protocol";
import { messageTime } from "../history";
import { THINKING_STEP_S, thinkingOrder } from "../models";
import { actions, useChat } from "../store";
import { revealTo } from "../typewriter";
import { Heart } from "./Heart";
import { Icon } from "./Icon";
import { Markdown, openLink } from "./Markdown";
import { Menu, type MenuItem } from "./Menu";
import { Portrait } from "./Portrait";

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

/** D-100: the ⋯ beside a message and its card. Only what works now is listed. */
function MessageMenu({
  m,
  last,
  head,
  editable,
  roleplay,
  onEdit,
}: {
  m: ChatMessage;
  /** The thread's newest message: nothing after it to rewind. */
  last: boolean;
  /** Her name (and its speaker) shows above this message. */
  head: boolean;
  editable: boolean;
  roleplay: boolean;
  onEdit: () => void;
}) {
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);
  const model = useChat((s) => (m.role === "assistant" && m.model ? modelLabel(s, m.model) : null));
  const acting = useChat(canActOnMessages);
  const reading = useChat((s) => s.reading === m.key);
  const online = useChat((s) => s.connection === "online");
  const her = m.role === "assistant";
  const when = m.ts ? messageTime(m.ts, Date.now()) : null;
  const id = m.id;
  const items: MenuItem[] = [{ label: "Copy", icon: "copy", onSelect: () => actions.copyMessage(m.text) }];
  // Her name carries the speaker; a message under it without a name gets it here.
  if (her && !head && online && m.text.trim())
    items.push({ label: reading ? "Stop reading" : "Read aloud", icon: "speaker", onSelect: () => actions.readMessage(m.key, m.text, m.speakerId ?? null) });
  if (editable) items.push({ label: "Edit message", icon: "edit", onSelect: onEdit });
  if (id !== undefined && acting) {
    if (!last) items.push({ label: "Rewind to here", icon: "rewind", onSelect: () => void actions.rewind(id) });
    if (roleplay && m.text.trim())
      items.push({ label: m.pinned ? "Unpin message" : "Pin message", icon: "pin", onSelect: () => actions.pinMessage(id, !m.pinned) });
    items.push({ label: "New chat from here", icon: "branch", onSelect: () => actions.branchFrom(id) });
  }
  return (
    <>
      <button
        type="button"
        className={at ? "msg-more open" : "msg-more"}
        aria-label="Message options"
        title="More"
        aria-haspopup="menu"
        aria-expanded={at !== null}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          // Her card opens leftwards from the ⋯, the user's rightwards, like the bubble.
          setAt(at ? null : { x: her ? r.right - 220 : r.left, y: r.bottom + 4 });
        }}
      >
        <Icon name="more" />
      </button>
      {at ? <Menu label="Message" heading={[when, model].filter(Boolean).join(" · ") || undefined} at={at} items={items} onClose={() => setAt(null)} /> : null}
    </>
  );
}

/** D-100: under her latest reply: Regenerate (a new reply, the old ones kept), and
 * arrows through the replies written so far. */
function SwipeBar({ m }: { m: ChatMessage }) {
  const ready = useChat(canRegenerate);
  const acting = useChat(canActOnMessages);
  if (!ready) return null;
  const count = m.swipes ?? 1;
  const at = m.swipe ?? 0;
  const id = m.id;
  return (
    <div className="swipe-bar">
      <button type="button" className="msg-action icon-action" aria-label="Regenerate" title="Write another reply" onClick={() => actions.regenerate()}>
        <Icon name="regenerate" />
      </button>
      {count > 1 && id !== undefined && acting ? (
        <span className="swipes" role="group" aria-label="Her replies">
          {at > 0 ? (
            <button type="button" className="msg-action icon-action" aria-label="Previous reply" title="Previous reply" onClick={() => actions.swipe(id, at - 1, count)}>
              <Icon name="left" />
            </button>
          ) : (
            <span className="swipe-gap" />
          )}
          <span className="swipe-count">
            {at + 1}/{count}
          </span>
          {at < count - 1 ? (
            <button type="button" className="msg-action icon-action" aria-label="Next reply" title="Next reply" onClick={() => actions.swipe(id, at + 1, count)}>
              <Icon name="right" />
            </button>
          ) : (
            <span className="swipe-gap" />
          )}
        </span>
      ) : null}
    </div>
  );
}

/** D-099: read this message aloud now, in her voice, whether Read aloud is on or off.
 * While it is being read, the same button stops it. */
function ReadButton({ m }: { m: ChatMessage }) {
  const reading = useChat((s) => s.reading === m.key);
  const starting = useChat((s) => s.reading === m.key && s.readAloud?.state !== "ready");
  const online = useChat((s) => s.connection === "online");
  const label = reading ? (starting ? "Starting her voice… (about 47 s) Click to stop" : "Stop reading") : "Read aloud";
  return (
    <button
      type="button"
      className={`msg-action icon-action read-message${reading ? " reading" : ""}`}
      aria-label={reading ? "Stop reading" : "Read aloud"}
      aria-pressed={reading}
      title={label}
      disabled={!online}
      onClick={() => actions.readMessage(m.key, m.text, m.speakerId ?? null)}
    >
      <Icon name="speaker" />
    </button>
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
        maxLength={TEXT_MAX}
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

function Message({
  m,
  first,
  last,
  lastReply,
  editable,
  roleplay,
  typing = false,
}: {
  m: ChatMessage;
  first: boolean;
  /** The thread's newest message (D-100: nothing after it to rewind). */
  last: boolean;
  lastReply: boolean;
  editable: boolean;
  roleplay: boolean;
  /** Still typing out (D-096): the caret shows and the action bar waits. */
  typing?: boolean;
}) {
  const sentTo = useChat((s) => (m.sentTo ? modelLabel(s, m.sentTo) : null));
  const [editing, setEditing] = useState(false);
  if (m.role === "divider") {
    return (
      <div className="divider" role="separator">
        <span>{m.text}</span>
      </div>
    );
  }
  const classes = ["msg", m.role, first ? "" : "cont", m.pending ? "pending" : "", m.failed ? "failed" : "", editing ? "editing" : "", typing ? "streaming" : ""]
    .filter(Boolean)
    .join(" ");
  const her = m.role === "assistant" && first;
  return (
    <div className={classes}>
      {her ? <Avatar id={m.speakerId} name={m.speaker ?? null} /> : null}
      {her && m.speaker ? (
        <div className="msg-head">
          <span className="speaker">{m.speaker}</span>
          {m.text.trim() && !typing ? <ReadButton m={m} /> : null}
        </div>
      ) : null}
      {editing ? (
        <EditBox text={m.text} onDone={() => setEditing(false)} />
      ) : (
        <>
          <div className="bubble-row">
            <div className="bubble" dir="auto">{m.role === "assistant" || roleplay ? <Markdown text={m.text} roleplay={roleplay} /> : m.text}</div>
            {m.pending || typing ? null : (
              <MessageMenu m={m} last={last} head={her && !!m.speaker} editable={editable} roleplay={roleplay} onEdit={() => setEditing(true)} />
            )}
            {m.pinned && roleplay ? (
              <span className="msg-pin" title="Pinned: she always keeps it in mind">
                <Icon name="pin" size={13} />
                <span className="sr-only">Pinned</span>
              </span>
            ) : null}
          </div>
          {lastReply && !typing && !m.pending ? <SwipeBar m={m} /> : null}
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
/** D-121: under a line about suicide or self-harm, in place of a reply: where to find help. */
function HelpCard({ where, name }: { where: "user" | "reply"; name: string | null }) {
  const link = (href: string, label: string) => (
    <a href={href} target="_blank" rel="noopener noreferrer" onClick={(e) => openLink(e, href)}>
      {label}
    </a>
  );
  return (
    <div className="help-card" role="note">
      <p className="help-card-title">Help is available</p>
      <p>
        If you're thinking about hurting yourself, you don't have to go through it alone. Someone can talk with you
        right now, free and in confidence:
      </p>
      <ul>
        <li>{link("https://findahelpline.com", "findahelpline.com")}: a helpline in your country</li>
        <li>
          US: call or text <strong>988</strong>
        </li>
        <li>
          UK and Ireland: call <strong>116 123</strong> (Samaritans)
        </li>
      </ul>
      <p>If you are in danger now, call your local emergency number.</p>
      <p className="help-card-why">
        {where === "reply"
          ? `${name ? `${name}'s` : "Her"} reply was stopped: it could have encouraged self-harm.`
          : `This message was not sent to ${name ?? "her"}.`}
      </p>
    </div>
  );
}

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

/** While she thinks (D-096): her face, the heart, and a short word that changes,
 * where her reply will appear. Gone as soon as the reply starts typing. */
function ThinkingReply({ id, name }: { id: string | null; name: string | null }) {
  const portrait = useChat((s) => s.roster.find((w) => w.id === id)?.portrait ?? null);
  const [order] = useState(() => thinkingOrder());
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setStep((n) => n + 1), THINKING_STEP_S * 1000);
    return () => window.clearInterval(t);
  }, []);
  const word = order[step % order.length];
  return (
    <div className="thinking-now" role="status">
      <Portrait id={id} name={name ?? ""} portrait={portrait} className="avatar-dot thinking-face" />
      <span className="thinking-heart" aria-hidden="true">
        <Heart />
      </span>
      {/* keyed on the word, so each new one plays its entrance */}
      <span
        className="thinking-word"
        key={word}
        aria-hidden="true"
        style={{ "--step": `${THINKING_STEP_S}s` } as CSSProperties}
      >
        {Array.from(word).map((ch, i) => (
          <span key={i} className="letter" style={{ "--i": i } as CSSProperties}>
            {ch}
          </span>
        ))}
        <span className="thinking-dots">
          <span />
          <span />
          <span />
        </span>
      </span>
      {/* Screen readers hear it once; the changing words are for the eyes. */}
      <span className="sr-only">{name ?? "She"} is thinking</span>
    </div>
  );
}

/** The part of `text` shown so far, growing letter by letter (D-096); null when
 * there is nothing to type. Reduced motion shows it all at once. */
function useTypewriter(text: string | null): string | null {
  const [shown, setShown] = useState(0);
  const latest = useRef(text);
  latest.current = text;
  const idle = text === null;
  useEffect(() => {
    if (idle) setShown(0);
  }, [idle]);
  const behind = text !== null && shown < text.length;
  useEffect(() => {
    if (!behind) return;
    let frame = 0;
    let then = performance.now();
    const tick = (now: number) => {
      const target = latest.current;
      if (target === null) return;
      const dt = now - then; // read before the updater runs, which is later
      then = now;
      setShown((n) => revealTo(n, target, dt));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [behind]);
  if (text === null) return null;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return text;
  return text.slice(0, Math.min(shown, text.length));
}

export function ThreadView() {
  const messages = useChat((s) => s.messages);
  const turn = useChat((s) => s.turn);
  const streaming = useChat(visibleStream);
  const companion = useChat((s) => s.companion?.name ?? null);
  const companionId = useChat((s) => s.companion?.id ?? null);
  const modelState = useChat((s) => s.modelStatus?.state ?? null);
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

  // The reply types out (D-096): first the streamed text, then, once it is saved,
  // the same reply where it now sits in the list until the letters catch up.
  const live = turn !== "idle" && streaming ? streaming : null;
  const finishing = useRef<string | null>(null);
  const wasLive = useRef(false);
  if (live !== null) {
    wasLive.current = true;
    finishing.current = null;
  } else if (wasLive.current) {
    wasLive.current = false;
    finishing.current = last?.role === "assistant" ? last.key : null;
  } else if (turn !== "idle") {
    finishing.current = null; // a new turn: the last reply is done typing
  }
  const finishingText = finishing.current !== null && last?.key === finishing.current ? last.text : null;
  const typed = useTypewriter(live ?? finishingText);
  const typingKey = finishingText !== null && typed !== null && typed.length < finishingText.length ? finishing.current : null;

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
  }, [messages.length, typed?.length, turn, modelState, justSent]);

  return (
    <div className="thread-wrap">
      {/* Her reply is said once it is finished, not letter by letter as it types out. */}
      <p className="sr-only" aria-live="polite">
        {turn === "idle" && messages[messages.length - 1]?.role === "assistant" ? messages[messages.length - 1].text : ""}
      </p>
      <div
        ref={box}
        className="thread"
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
          <Fragment key={m.key}>
            <Message
              m={m.key === typingKey && typed !== null ? { ...m, text: typed } : m}
              typing={m.key === typingKey}
              first={startsGroup(messages, i)}
              last={i === messages.length - 1}
              lastReply={m.key === lastReplyKey}
              editable={m.key === editable}
              roleplay={roleplay}
            />
            {m.role === "user" && m.safety ? <HelpCard where={m.safety} name={companion} /> : null}
          </Fragment>
        ))}
        <TurnFailure />
        {turn !== "idle" && !typed ? <ThinkingReply id={companionId} name={companion} /> : null}
        {live !== null && typed ? (
          <div className="msg assistant streaming">
            <Avatar id={companionId} name={companion} />
            <div className="msg-head">{companion ? <span className="speaker">{companion}</span> : null}</div>
            <div className="bubble">
              <Markdown text={typed} roleplay={roleplay} />
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
