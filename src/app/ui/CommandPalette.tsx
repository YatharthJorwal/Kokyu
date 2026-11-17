// The keyboard layer (UI1-10, D-095): one listener for the window's shortcuts
// (Ctrl+N a new chat, Ctrl+K this palette, Ctrl+, Settings, Esc stops a reply) and
// the palette itself: type to filter actions, companions and conversations, arrows
// to move, Enter to run, Esc to close. What it lists comes from keys.ts.

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { anyModal, paletteItems, shortcutFor, type PaletteAction } from "../keys";
import { actions, useChat } from "../store";

function run(action: PaletteAction): void {
  switch (action.kind) {
    case "new_chat":
      return actions.newThread();
    case "new_roleplay":
      return actions.openRoleplay();
    case "model":
      return actions.openPicker();
    case "settings":
      return actions.openSettings(action.section);
    case "companion":
      return actions.switchWaifu(action.id);
    case "profile":
      return actions.openProfile(action.id);
    case "thread":
      return actions.openThread(action.id);
  }
}

/** The window-wide shortcuts. Registered once, first, so a dialog's own Escape (which
 * closes it) is seen here while the dialog is still open and is left to it. */
function useShortcuts(): void {
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      const cut = shortcutFor(e);
      if (!cut) return;
      const s = useChat.getState();
      if (cut === "stop") {
        if (s.turn !== "idle" && !anyModal(s)) {
          e.preventDefault();
          actions.stop();
        }
        return;
      }
      e.preventDefault(); // Ctrl+N must not open a browser window, Ctrl+K its search
      if (cut === "palette") {
        if (s.palette) actions.closePalette();
        else if (!anyModal(s)) actions.openPalette();
        return;
      }
      // Another dialog is open: the shortcut waits (the palette gives way to it).
      if (anyModal(s) && !s.palette) return;
      actions.closePalette();
      if (cut === "new_chat") actions.newThread();
      else actions.openSettings();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
}

export function CommandPalette() {
  useShortcuts();
  const open = useChat((s) => s.palette);
  if (!open) return null;
  return (
    <div className="settings-backdrop palette-backdrop" onMouseDown={(e) => e.target === e.currentTarget && actions.closePalette()}>
      <Palette />
    </div>
  );
}

function Palette() {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const state = useChat();
  const items = useMemo(() => paletteItems(state, query), [state, query]);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const back = document.activeElement as HTMLElement | null;
    input.current?.focus();
    return () => {
      if (document.activeElement === document.body || document.activeElement === null) back?.focus?.();
    };
  }, []);

  useEffect(() => setActive(0), [query]);

  useEffect(() => {
    list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const pick = (n: number) => {
    const item = items[n];
    if (!item) return;
    actions.closePalette();
    run(item.action);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (items.length ? (i + step + items.length) % items.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(active);
    } else if (e.key === "Escape") {
      e.preventDefault();
      actions.closePalette();
    }
  };

  return (
    <div className="palette" role="dialog" aria-modal="true" aria-label="Go to">
      <input
        ref={input}
        className="palette-input"
        type="text"
        role="combobox"
        aria-expanded="true"
        aria-controls="palette-list"
        aria-activedescendant={items[active] ? `palette-${items[active].key}` : undefined}
        aria-label="Type a command or a conversation"
        placeholder="Type a command or a conversation…"
        value={query}
        maxLength={200}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKey}
      />
      {items.length === 0 ? (
        <p className="palette-empty">Nothing matches “{query.trim()}”.</p>
      ) : (
        <ul id="palette-list" ref={list} className="palette-list" role="listbox" aria-label="Results">
          {items.map((it, n) => (
            <li key={it.key} className="palette-row" role="presentation">
              {n === 0 || items[n - 1].group !== it.group ? (
                <span className="palette-group" aria-hidden="true">
                  {it.group}
                </span>
              ) : null}
              <div
                id={`palette-${it.key}`}
                role="option"
                aria-selected={n === active}
                data-index={n}
                className={n === active ? "palette-item active" : "palette-item"}
                onMouseMove={() => setActive(n)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(n)}
              >
                <span>{it.label}</span>
                {it.hint ? <span className="menu-hint">{it.hint}</span> : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
