// A small pop-up menu (UI1-09): the sidebar's right-click menu and the New button's
// choices. Arrow keys move, Enter picks, Escape or a click outside closes and gives
// the focus back. Placed at a point and kept inside the window.

import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

export interface MenuItem {
  label: string;
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
  /** A shortcut shown muted at the right. */
  hint?: string;
}

export function Menu({ items, at, label, onClose }: { items: MenuItem[]; at: { x: number; y: number }; label: string; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState(at);
  // The latest onClose, so a parent's re-render never re-runs the open/close effect.
  const close = useRef(onClose);
  close.current = onClose;

  // Kept inside the window: flipped up or left when it would run off an edge.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    setPos({
      x: Math.max(4, Math.min(at.x, window.innerWidth - width - 4)),
      y: at.y + height > window.innerHeight - 4 ? Math.max(4, at.y - height) : at.y,
    });
  }, [at.x, at.y]);

  useEffect(() => {
    const back = document.activeElement as HTMLElement | null;
    box.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus();
    const outside = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) close.current();
    };
    const away = () => close.current();
    document.addEventListener("mousedown", outside);
    window.addEventListener("blur", away);
    window.addEventListener("resize", away);
    return () => {
      document.removeEventListener("mousedown", outside);
      window.removeEventListener("blur", away);
      window.removeEventListener("resize", away);
      if (back && document.activeElement === document.body) back.focus();
    };
  }, []);

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const buttons = [...(box.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])];
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      buttons[(at + step + buttons.length) % buttons.length]?.focus();
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      buttons[e.key === "Home" ? 0 : buttons.length - 1]?.focus();
    } else if (e.key === "Escape" || e.key === "Tab") {
      e.preventDefault();
      e.stopPropagation();
      onClose();
    }
  };

  return (
    <div ref={box} className="menu" role="menu" aria-label={label} style={{ left: pos.x, top: pos.y }} onKeyDown={onKey}>
      {items.map((it) => (
        <button
          key={it.label}
          type="button"
          role="menuitem"
          className={it.danger ? "danger" : undefined}
          disabled={it.disabled}
          onClick={() => {
            onClose();
            it.onSelect();
          }}
        >
          <span>{it.label}</span>
          {it.hint ? <span className="menu-hint">{it.hint}</span> : null}
        </button>
      ))}
    </div>
  );
}
