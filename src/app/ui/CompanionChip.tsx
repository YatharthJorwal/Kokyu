// The companion chip in the input row (K1-06, FR-S-1): her avatar and name, and a
// popover with a searchable list plus "＋ New waifu". Switching changes only her
// voice and persona (FR-W-3); mid-reply it waits for the reply to finish, and the
// chip says who comes next (FR-S-2). The kernel writes the divider. Her face is
// the portrait from her VRM (D-091). In a roleplay she stays (D-101): the chip opens
// her profile instead, and another companion means a new chat.

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { currentMode, type Companion } from "../chat-state";
import { actions, useChat } from "../store";
import { Portrait } from "./Portrait";

export function CompanionChip() {
  const companion = useChat((s) => s.companion);
  const pending = useChat((s) => s.pendingCompanion);
  const roster = useChat((s) => s.roster);
  const enabled = useChat((s) => s.role === "driver" && s.connection === "online" && s.roster.length > 0);
  const roleplay = useChat((s) => currentMode(s) === "roleplay");
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
  if (roleplay && companion) {
    return (
      <div className="model-picker companion-picker">
        <button
          type="button"
          className="model-chip companion-chip"
          title={`${companion.name} stays for this story. Start a new chat to talk to someone else.`}
          onClick={() => actions.openProfile(companion.id)}
        >
          <Portrait id={companion.id} name={companion.name} portrait={companion.portrait} className="avatar-dot" />
          <span className="model-name">{name}</span>
        </button>
      </div>
    );
  }
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
        <Portrait id={companion?.id} name={companion?.name} portrait={companion?.portrait} className="avatar-dot" />
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
  roster: Companion[];
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
                  <Portrait id={w.id} name={w.name} portrait={w.portrait} className="row-face" />
                  <span className="row-label">{w.name}</span>
                </span>
              </button>
              <button
                type="button"
                className="ghost profile-link"
                aria-label={`${w.name}'s profile`}
                onClick={() => {
                  onClose();
                  actions.openProfile(w.id);
                }}
              >
                Profile
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
