// The companion chip in the input row (K1-06, FR-S-1): her avatar and name, and a
// popover with a searchable list plus "＋ New waifu". Switching changes only her
// voice and persona (FR-W-3); mid-reply it waits for the reply to finish, and the
// chip says who comes next (FR-S-2). The kernel writes the divider.
//
// shortcut: the avatar is her initial until packs carry a portrait (the creator, K3).

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { actions, useChat } from "../store";
import { Initial } from "./Sidebar";

export function CompanionChip() {
  const companion = useChat((s) => s.companion);
  const pending = useChat((s) => s.pendingCompanion);
  const roster = useChat((s) => s.roster);
  const enabled = useChat((s) => s.role === "driver" && s.connection === "online" && s.roster.length > 0);
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const name = companion?.name ?? "No companion";
  const title = pending ? `${pending.name} takes over after this reply` : "Choose who you talk to";

  return (
    <div className="model-picker companion-picker" ref={wrapper}>
      <button
        type="button"
        className={open ? "model-chip companion-chip open" : "model-chip companion-chip"}
        title={title}
        aria-haspopup="dialog"
        aria-expanded={open}
        disabled={!enabled && !open}
        onClick={() => setOpen((o) => !o)}
      >
        <Initial name={companion?.name} />
        <span className="model-name">{name}</span>
        {pending ? <span className="effort-label">then {pending.name}</span> : null}
        <span className="caret" aria-hidden="true">
          ▾
        </span>
      </button>
      {open ? (
        <CompanionPopover
          roster={roster}
          active={pending?.id ?? companion?.id ?? null}
          onPick={(id) => {
            actions.switchWaifu(id);
            setOpen(false);
          }}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </div>
  );
}

function CompanionPopover({
  roster,
  active,
  onPick,
  onClose,
}: {
  roster: { id: string; name: string }[];
  active: string | null;
  onPick: (id: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const shown = needle ? roster.filter((w) => w.name.toLowerCase().includes(needle)) : roster;

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "Enter" && shown.length > 0) {
      e.preventDefault();
      onPick(shown[0].id);
    }
  };

  return (
    <div className="model-popover companion-popover" role="dialog" aria-label="Choose a companion">
      <input
        autoFocus
        className="model-search"
        type="search"
        placeholder="Search companions"
        aria-label="Search companions"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKeyDown}
      />
      {shown.length === 0 ? <p className="list-hint">Nobody called “{query.trim()}”.</p> : null}
      <div className="model-list">
        <ul aria-label="Companions">
          {shown.map((w) => (
            <li key={w.id}>
              <button
                type="button"
                className={w.id === active ? "model-row current" : "model-row"}
                aria-pressed={w.id === active}
                onClick={() => onPick(w.id)}
              >
                <span className="check" aria-hidden="true">
                  {w.id === active ? "✓" : ""}
                </span>
                <span className="row-main">
                  <span className="row-label">{w.name}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
