// A roleplay's own pages, from the composer's story tray (D-101): History, every
// roleplay with her (open one to go back to it), and Memory, a box the user writes
// that she keeps in mind every turn of this story, with the story's pinned messages
// (FR-MODE-11). Both belong to roleplay only; a chat has neither.

import { useEffect, useRef, useState } from "react";

import { canActOnMessages, canStartThread } from "../chat-state";
import { messageTime } from "../history";
import { actions, useChat } from "../store";
import { Icon } from "./Icon";

/** The longest Memory the engine keeps (KASANE protocol NOTE_MAX). */
export const NOTE_MAX = 1000;

export function StoryDialog() {
  const panel = useChat((s) => s.story);
  const dirty = useRef(false);   // an unsaved Memory note: Esc and the backdrop leave it open
  useEffect(() => {
    if (!panel) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape" && !dirty.current) actions.closeStory();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [panel]);
  if (!panel) return null;
  return (
    <div className="settings-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !dirty.current && actions.closeStory()}>
      <div className="story-dialog" role="dialog" aria-modal="true" aria-labelledby="story-title">
        <button type="button" className="settings-close ghost" aria-label="Close" onClick={() => actions.closeStory()}>
          ✕
        </button>
        {panel === "history" ? <History /> : <Memory dirty={dirty} />}
      </div>
    </div>
  );
}

function History() {
  const name = useChat((s) => s.companion?.name ?? "her");
  const id = useChat((s) => s.companion?.id ?? null);
  const current = useChat((s) => s.thread?.id ?? null);
  const threads = useChat((s) => s.threads);
  const canOpen = useChat(canStartThread);
  const stories = threads
    .filter((t) => t.mode === "roleplay" && t.active_waifu_id === id)
    .sort((a, b) => b.updated_at - a.updated_at);
  const now = Date.now();
  return (
    <>
      <h2 id="story-title">History</h2>
      <p className="muted">Every roleplay with {name}, newest first.</p>
      <ul className="story-list">
        {stories.map((t) => (
          <li key={t.id}>
            <button
              type="button"
              className={t.id === current ? "story-row current" : "story-row"}
              aria-current={t.id === current ? "page" : undefined}
              disabled={!canOpen && t.id !== current}
              onClick={() => {
                if (t.id !== current) actions.openThread(t.id);
                actions.closeStory();
              }}
            >
              <span className="story-row-title">{t.title || "New story"}</span>
              <span className="muted small">{t.id === current ? "Open now" : messageTime(t.updated_at, now)}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

function Memory({ dirty }: { dirty: { current: boolean } }) {
  const saved = useChat((s) => s.thread?.note ?? "");
  const name = useChat((s) => s.companion?.name ?? "She");
  const messages = useChat((s) => s.messages);
  const pins = messages.filter((m) => m.pinned && m.id !== undefined);
  const acting = useChat(canActOnMessages);
  const [draft, setDraft] = useState(saved);
  useEffect(() => setDraft(saved), [saved]);
  const changed = draft.trim() !== saved.trim();
  dirty.current = changed;
  useEffect(() => () => void (dirty.current = false), [dirty]);   // History has no draft
  return (
    <>
      <h2 id="story-title">Memory</h2>
      <p className="muted">{name} keeps this in mind for the whole story. It stays in this roleplay and never reaches your chats.</p>
      <textarea
        className="story-note"
        aria-label="What she should remember in this story"
        placeholder="Names, places, how she feels about you, what happened before…"
        maxLength={NOTE_MAX}
        rows={6}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      <div className="story-note-foot">
        <span className="muted small">
          {draft.length}/{NOTE_MAX}
        </span>
        <button type="button" className="primary" disabled={!changed || !acting} onClick={() => actions.saveStoryNote(draft.trim())}>
          Save
        </button>
      </div>
      <h3 className="story-pins-head">Pinned messages</h3>
      {pins.length === 0 ? (
        <p className="muted small">Pin a message from its ⋯ menu and it shows here; she always keeps it in mind.</p>
      ) : (
        <ul className="story-pins">
          {pins.map((m) => (
            <li key={m.key}>
              <span className="story-pin-who">{m.role === "user" ? "You" : (m.speaker ?? name)}</span>
              <span className="story-pin-text">{m.text}</span>
              {acting ? (
                <button type="button" className="msg-action icon-action" aria-label="Unpin" title="Unpin" onClick={() => actions.pinMessage(m.id as number, false)}>
                  <Icon name="pin" />
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
