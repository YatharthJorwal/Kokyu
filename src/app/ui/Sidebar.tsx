// The sidebar (K1-03, FR-C-6; laid out to the reference in K1-15, D-068): the
// logo, New chat and search at the top, history in the middle (grouped Today /
// Yesterday / Previous 7 days / Older, each with its companion's badge,
// searchable, renamable, deletable) and the Settings gear at the bottom. The
// companions moved to the chip in the top bar.

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import type { ThreadInfo } from "../../net/protocol";
import type { Companion } from "../chat-state";
import { groupThreads } from "../history";
import { actions, useChat } from "../store";

const SEARCH_DELAY_MS = 250;

export function Initial({ name }: { name: string | null | undefined }) {
  return (
    <span className="avatar-dot" aria-hidden="true">
      {(name ?? "?").slice(0, 1).toUpperCase()}
    </span>
  );
}

export function Sidebar() {
  const threads = useChat((s) => s.threads);
  const search = useChat((s) => s.search);
  const roster = useChat((s) => s.roster);
  const busy = useChat((s) => s.turn !== "idle");
  const connection = useChat((s) => s.connection);
  const [query, setQuery] = useState("");

  // Search as the user types, a moment after they stop.
  useEffect(() => {
    if (!query.trim()) return;
    const t = window.setTimeout(() => actions.searchThreads(query), SEARCH_DELAY_MS);
    return () => window.clearTimeout(t);
  }, [query]);

  const searching = query.trim() !== "";
  const results = searching && search?.query === query.trim() ? search.threads : null;

  return (
    <aside className="sidebar" aria-label="Conversations">
      <div className="brand">
        <img className="brand-mark" src="/favicon.png" alt="" />
        <span className="brand-name">Kōkyū</span>
      </div>

      <button
        type="button"
        className="new-chat"
        onClick={() => actions.newThread()}
        disabled={busy || connection !== "online"}
      >
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path d="M8 2.5v11M2.5 8h11" />
        </svg>
        New chat
      </button>

      <label className="thread-search">
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="7" cy="7" r="4.5" />
          <path d="M10.5 10.5l3 3" />
        </svg>
        <input
          type="search"
          placeholder="Search chats"
          maxLength={200}
          aria-label="Search chats"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setQuery("");
          }}
        />
      </label>

      <nav className="history" aria-label="History">
        {searching ? (
          results === null ? (
            <p className="muted small">Searching…</p>
          ) : results.length === 0 ? (
            <p className="muted small">Nothing matches “{query.trim()}”.</p>
          ) : (
            <ThreadList threads={results} roster={roster} busy={busy} />
          )
        ) : threads.length === 0 ? (
          <p className="muted small">No conversations yet.</p>
        ) : (
          groupThreads(threads, Date.now()).map((g) => (
            <section key={g.name} aria-label={g.name}>
              <h3 className="group-head">{g.name}</h3>
              <ThreadList threads={g.threads} roster={roster} busy={busy} />
            </section>
          ))
        )}
      </nav>

      <div className="sidebar-footer">
        <button type="button" className="settings" aria-label="Settings" title="Settings" onClick={() => actions.openSettings()}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="3.2" />
            <path d="M12 2.8l1.6 2.3 2.7-.7.9 2.6 2.6.9-.7 2.7 2.3 1.6-2.3 1.6.7 2.7-2.6.9-.9 2.6-2.7-.7L12 21.2l-1.6-2.3-2.7.7-.9-2.6-2.6-.9.7-2.7L2.8 12l2.3-1.6-.7-2.7 2.6-.9.9-2.6 2.7.7z" />
          </svg>
        </button>
        <span className={`conn conn-${connection}`} role="status">
          {connection === "online" ? "Connected" : connection === "connecting" ? "Connecting…" : "Kernel offline"}
        </span>
      </div>
    </aside>
  );
}

function ThreadList({ threads, roster, busy }: { threads: ThreadInfo[]; roster: Companion[]; busy: boolean }) {
  return (
    <ul>
      {threads.map((t) => (
        <ThreadRow key={t.id} thread={t} roster={roster} busy={busy} />
      ))}
    </ul>
  );
}

function ThreadRow({ thread, roster, busy }: { thread: ThreadInfo; roster: Companion[]; busy: boolean }) {
  const current = useChat((s) => s.thread?.id === thread.id);
  const [mode, setMode] = useState<"view" | "rename" | "delete">("view");
  const [title, setTitle] = useState(thread.title);
  const input = useRef<HTMLInputElement>(null);
  const waifu = roster.find((w) => w.id === thread.active_waifu_id);
  const label = thread.title || "New chat";

  useEffect(() => {
    if (mode === "rename") input.current?.select();
  }, [mode]);

  if (mode === "rename") {
    const done = (save: boolean) => {
      if (save && title.trim() && title.trim() !== thread.title) actions.renameThread(thread.id, title);
      setMode("view");
    };
    const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") done(true);
      else if (e.key === "Escape") done(false);
    };
    return (
      <li className="thread-row">
        <input
          ref={input}
          className="thread-rename"
          aria-label="New title"
          value={title}
          maxLength={200}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={onKey}
          onBlur={() => done(true)}
        />
      </li>
    );
  }

  if (mode === "delete") {
    return (
      <li className="thread-row confirm" role="group" aria-label={`Delete ${label}?`}>
        <span className="confirm-text">Delete “{label}”?</span>
        <button
          type="button"
          className="danger"
          disabled={busy}
          onClick={() => {
            actions.deleteThread(thread.id);
            setMode("view");
          }}
        >
          Delete
        </button>
        {/* the safe choice gets the focus */}
        <button type="button" autoFocus onClick={() => setMode("view")}>
          Cancel
        </button>
      </li>
    );
  }

  return (
    <li className="thread-row">
      <button
        type="button"
        className={current ? "thread-item active" : "thread-item"}
        aria-current={current ? "page" : undefined}
        onClick={() => actions.openThread(thread.id)}
        disabled={busy && !current}
        title={label}
      >
        {waifu ? (
          <span className="thread-badge" title={waifu.name} aria-label={`with ${waifu.name}`}>
            {waifu.name.slice(0, 1).toUpperCase()}
          </span>
        ) : null}
        <span className="thread-title">{label}</span>
        {thread.temp ? <span className="badge">Temp</span> : null}
      </button>
      <span className="thread-actions">
        <button
          type="button"
          aria-label={`Rename ${label}`}
          title="Rename"
          onClick={() => {
            setTitle(thread.title);
            setMode("rename");
          }}
        >
          ✎
        </button>
        <button type="button" aria-label={`Delete ${label}`} title="Delete" disabled={busy} onClick={() => setMode("delete")}>
          🗑
        </button>
      </span>
    </li>
  );
}
