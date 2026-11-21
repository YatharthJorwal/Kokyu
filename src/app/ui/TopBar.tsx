// The top of the chat column (K1-15, D-068; one slim row since UI1-09): the
// companion chip with her face (FR-S-1), the open conversation's title, the Temp
// Chat switch (FR-MEM-5) and, in the desktop app, the window's own minimize,
// maximize and close buttons (the window has no frame; close hides to the tray, as
// the frame's did). The row is where the window is dragged.

import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";

import { actions, setPetPrefs, useChat, usePetPrefs } from "../store";
import { CompanionChip } from "./CompanionChip";
import { Icon } from "./Icon";

/** `onShowSidebar`: the sidebar is hidden (D-100); this button brings it back. */
export function TopBar({ onShowSidebar }: { onShowSidebar?: () => void }) {
  const desktop = isTauri();
  const title = useChat((s) => (s.thread ? s.thread.title || (s.thread.mode === "roleplay" ? "New story" : "New chat") : ""));
  return (
    <header className={desktop ? "top-bar framed" : "top-bar"} data-tauri-drag-region>
      {onShowSidebar ? (
        <button type="button" className="sidebar-toggle" aria-label="Show the sidebar" title="Show the sidebar" onClick={onShowSidebar}>
          <Icon name="sidebar" size={18} />
        </button>
      ) : null}
      <CompanionChip />
      <PetButton />
      <span className="top-bar-title" data-tauri-drag-region title={title || undefined}>
        {title}
      </span>
      <ViewSwitch />
      <TempSwitch />
      {desktop ? <WindowControls /> : null}
    </header>
  );
}

/** D-103 (FR-P-1): shows or hides her pet; with no pet yet it opens Settings → Pet. */
function PetButton() {
  const name = useChat((s) => s.companion?.name ?? null);
  const has = useChat((s) => Boolean(s.companion?.pet));
  const show = usePetPrefs((p) => p.show);
  if (name === null) return null;
  const on = has && show;
  const label = has ? (show ? `Hide ${name}'s pet` : `Show ${name}'s pet`) : `Create ${name}'s pet`;
  return (
    <button
      type="button"
      className={on ? "pet-toggle on" : "pet-toggle"}
      aria-label={label}
      aria-pressed={has ? on : undefined}
      title={label}
      onClick={() => (has ? setPetPrefs({ show: !show }) : actions.openSettings("pet"))}
    >
      <Icon name="cat" size={17} />
    </button>
  );
}

/** D-104 (D-009): the same thread as text, or her on the Stage. */
function ViewSwitch() {
  const view = useChat((s) => s.view);
  const has = useChat((s) => s.companion !== null);
  if (!has) return null;
  return (
    <div className="view-switch" role="group" aria-label="View">
      <button type="button" aria-pressed={view === "chat"} onClick={() => actions.setView("chat")}>
        Chat
      </button>
      <button type="button" aria-pressed={view === "stage"} onClick={() => actions.setView("stage")}>
        Stage
      </button>
    </div>
  );
}

function TempSwitch() {
  const on = useChat((s) => s.thread?.temp ?? false);
  const enabled = useChat((s) => s.role === "driver" && s.connection === "online" && s.thread !== null);
  return (
    <label className="switch" title="While on, this chat neither reads nor adds to memory">
      <input type="checkbox" role="switch" checked={on} disabled={!enabled} onChange={(e) => actions.setTemp(e.target.checked)} />
      <span className="switch-track" aria-hidden="true" />
      Temp Chat
    </label>
  );
}

function WindowControls() {
  const win = getCurrentWindow();
  return (
    <div className="window-controls">
      <button type="button" aria-label="Minimize" title="Minimize" onClick={() => void win.minimize()}>
        <svg viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2 6h8" />
        </svg>
      </button>
      <button type="button" aria-label="Maximize" title="Maximize" onClick={() => void win.toggleMaximize()}>
        <svg viewBox="0 0 12 12" aria-hidden="true">
          <rect x="2" y="2" width="8" height="8" rx="1" />
        </svg>
      </button>
      <button type="button" className="close" aria-label="Close" title="Close (Kōkyū stays in the tray)" onClick={() => void win.close()}>
        <svg viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2.5 2.5l7 7M9.5 2.5l-7 7" />
        </svg>
      </button>
    </div>
  );
}
