// The top of the chat column (K1-15, D-068): the companion chip (FR-S-1) and the
// Temp Chat switch (FR-MEM-5). In the desktop app the window has no frame, so
// this row is also where the window is dragged and where its own minimize,
// maximize and close buttons sit; close hides to the tray, as the frame's did.

import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";

import { actions, useChat } from "../store";
import { CompanionChip } from "./CompanionChip";

export function TopBar() {
  const desktop = isTauri();
  return (
    <header className={desktop ? "top-bar framed" : "top-bar"} data-tauri-drag-region>
      {desktop ? <WindowControls /> : null}
      <div className="top-bar-row" data-tauri-drag-region>
        <CompanionChip />
        <span className="top-bar-gap" data-tauri-drag-region />
        <TempSwitch />
      </div>
    </header>
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
