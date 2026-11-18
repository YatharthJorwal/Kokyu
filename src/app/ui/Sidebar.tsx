// The sidebar (K1-03, FR-C-6; laid out to the reference in K1-15, D-068): the
// logo, New chat and search at the top, history in the middle (grouped Today /
// Yesterday / Previous 7 days / Older, each with its companion's badge,
// searchable, renamable, deletable) and the Settings gear at the bottom. The
// companions moved to the chip in the top bar. A roleplay thread carries a badge
// (K1c-08; FR-MODE-6, 7). UI1-09: New is a split button (Chat, or Roleplay… from
// its arrow), and each conversation has a menu (right-click, or its ⋯ button):
// Pin, Rename, Delete (asked in the window first). Pinned ones list first (D-094).
// D-100: a button at the top hides the sidebar (the top bar brings it back), and a
// filter under the search shows all conversations, only chats or only roleplays.

import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";

import type { ThreadInfo } from "../../net/protocol";
import type { Companion } from "../chat-state";
import { groupThreads } from "../history";
import { actions, useChat } from "../store";
import { Icon } from "./Icon";
import { Menu } from "./Menu";
import { Portrait } from "./Portrait";

/** New chat, with Chat and Roleplay… under its arrow (UI1-09). */
function NewButton({ disabled }: { disabled: boolean }) {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  return (
    <div className="new-split">
      <button type="button" className="new-chat" onClick={() => actions.newThread()} disabled={disabled}>
        <Icon name="plus" size={18} />
        New chat
      </button>
      <button
        type="button"
        className="new-more"
        aria-label="More ways to start"
        title="Chat or roleplay"
        aria-haspopup="menu"
        aria-expanded={menu !== null}
        disabled={disabled}
        onClick={(e) => {
          const r = e.currentTarget.parentElement?.getBoundingClientRect() ?? e.currentTarget.getBoundingClientRect();
          setMenu(menu ? null : { x: r.left, y: r.bottom + 6 });
        }}
      >
        <Icon name="chevron" size={18} />
      </button>
      {menu ? (
        <Menu
          label="Start"
          at={menu}
          onClose={() => setMenu(null)}
          items={[
            { label: "Chat", hint: "Ctrl+N", onSelect: () => actions.newThread() },
            // FR-MODE-6: a story from a scenario card, or blank
            { label: "Roleplay…", onSelect: () => actions.openRoleplay() },
          ]}
        />
      ) : null}
    </div>
  );
}

const SEARCH_DELAY_MS = 250;

type Filter = "all" | "chat" | "roleplay";
const FILTERS: { value: Filter; label: string; none: string }[] = [
  { value: "all", label: "All", none: "No conversations yet." },
  { value: "chat", label: "Chats", none: "No chats yet." },
  { value: "roleplay", label: "Roleplays", none: "No roleplays yet." },
];

export function Sidebar({ onHide }: { onHide: () => void }) {
  const threads = useChat((s) => s.threads);
  const search = useChat((s) => s.search);
  const roster = useChat((s) => s.roster);
  const busy = useChat((s) => s.turn !== "idle");
  const connection = useChat((s) => s.connection);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const shown = (list: ThreadInfo[]) => (filter === "all" ? list : list.filter((t) => t.mode === filter));

  // Search as the user types, a moment after they stop.
  useEffect(() => {
    if (!query.trim()) return;
    const t = window.setTimeout(() => actions.searchThreads(query), SEARCH_DELAY_MS);
    return () => window.clearTimeout(t);
  }, [query]);

  const searching = query.trim() !== "";
  const found = searching && search?.query === query.trim() ? search.threads : null;
  const results = found && shown(found);
  const listed = shown(threads);

  return (
    <aside className="sidebar" aria-label="Conversations">
      <div className="brand">
        <img className="brand-mark" src="/favicon.png" alt="" />
        <span className="brand-name">Kōkyū</span>
        <button type="button" className="sidebar-toggle" aria-label="Hide the sidebar" title="Hide the sidebar" onClick={onHide}>
          <Icon name="sidebar" size={18} />
        </button>
      </div>

      <NewButton disabled={busy || connection !== "online"} />

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
            if (e.key === "Escape" && query) {
              e.preventDefault(); // clearing the search, not stopping a reply (UI1-10)
              setQuery("");
            }
          }}
        />
      </label>

      <div className="thread-filter" role="radiogroup" aria-label="Show">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            role="radio"
            aria-checked={filter === f.value}
            className={filter === f.value ? "on" : undefined}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <nav className="history" aria-label="History">
        {searching ? (
          results === null ? (
            <p className="muted small">Searching…</p>
          ) : results.length === 0 ? (
            <p className="muted small">Nothing matches “{query.trim()}”.</p>
          ) : (
            <ThreadList threads={results} roster={roster} busy={busy} />
          )
        ) : listed.length === 0 ? (
          <p className="muted small">{FILTERS.find((f) => f.value === filter)?.none}</p>
        ) : (
          groupThreads(listed, Date.now()).map((g) => (
            <section key={g.name} aria-label={g.name}>
              <h3 className="group-head">{g.name}</h3>
              <ThreadList threads={g.threads} roster={roster} busy={busy} />
            </section>
          ))
        )}
      </nav>

      <div className="sidebar-footer">
        <button type="button" className="settings" aria-label="Settings" title="Settings (Ctrl+,)" onClick={() => actions.openSettings()}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="3.2" />
            <path d="M12 2.8l1.6 2.3 2.7-.7.9 2.6 2.6.9-.7 2.7 2.3 1.6-2.3 1.6.7 2.7-2.6.9-.9 2.6-2.7-.7L12 21.2l-1.6-2.3-2.7.7-.9-2.6-2.6-.9.7-2.7L2.8 12l2.3-1.6-.7-2.7 2.6-.9.9-2.6 2.7.7z" />
          </svg>
        </button>
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
  const [mode, setMode] = useState<"view" | "rename">("view");
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
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
      else if (e.key === "Escape") {
        e.preventDefault();
        done(false);
      }
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

  const openMenu = (e: MouseEvent<HTMLElement>, below: boolean) => {
    e.preventDefault();
    const r = e.currentTarget.getBoundingClientRect();
    // The keyboard's menu key reports no pointer: open under the row instead.
    const keyboard = e.clientX === 0 && e.clientY === 0;
    setMenu(below || keyboard ? { x: r.left, y: r.bottom + 2 } : { x: e.clientX, y: e.clientY });
  };

  return (
    <li className="thread-row" onContextMenu={(e) => openMenu(e, false)}>
      <button
        type="button"
        className={current ? "thread-item active" : "thread-item"}
        aria-current={current ? "page" : undefined}
        onClick={() => actions.openThread(thread.id)}
        disabled={busy && !current}
        title={label}
      >
        {waifu ? (
          <>
            <Portrait id={waifu.id} name={waifu.name} portrait={waifu.portrait} className="thread-badge" title={waifu.name} />
            <span className="sr-only">with {waifu.name}</span>
          </>
        ) : null}
        {thread.pinned ? (
          <span className="thread-pin" title="Pinned">
            <Icon name="pin" size={13} />
            <span className="sr-only">Pinned</span>
          </span>
        ) : null}
        <span className="thread-title">{label}</span>
        {thread.mode === "roleplay" ? <span className="badge">Roleplay</span> : null}
        {thread.temp ? <span className="badge">Temp</span> : null}
      </button>
      <span className="thread-actions">
        <button
          type="button"
          aria-label={`More for ${label}`}
          title="More"
          aria-haspopup="menu"
          aria-expanded={menu !== null}
          onClick={(e) => (menu ? setMenu(null) : openMenu(e, true))}
        >
          <Icon name="more" />
        </button>
      </span>
      {menu ? (
        <Menu
          label={label}
          at={menu}
          onClose={() => setMenu(null)}
          items={[
            { label: thread.pinned ? "Unpin" : "Pin", onSelect: () => actions.pinThread(thread.id, !thread.pinned) },
            {
              label: "Rename",
              onSelect: () => {
                setTitle(thread.title);
                setMode("rename");
              },
            },
            {
              label: "Delete…",
              danger: true,
              disabled: busy,
              onSelect: () => {
                void actions
                  .confirm({
                    title: "Delete this conversation?",
                    body: `“${label}” and its messages are removed from this PC. This cannot be undone.`,
                    action: "Delete",
                    danger: true,
                  })
                  .then((yes) => yes && actions.deleteThread(thread.id));
              },
            },
          ]}
        />
      ) : null}
    </li>
  );
}
