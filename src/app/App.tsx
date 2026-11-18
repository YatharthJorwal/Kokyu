// The Kōkyū window (K1-02, laid out to the reference in K1-15, D-068): sidebar,
// then the chat column with its top bar, the open thread and the input box. The
// Stage view with the avatar arrives in K2 (its engine waits in src/engine/).

import { useState } from "react";

import { Composer } from "./ui/Composer";
import { CommandPalette } from "./ui/CommandPalette";
import { ConfirmDialog } from "./ui/ConfirmDialog";
import { ConnectionBanner } from "./ui/ConnectionBanner";
import { NoticeBar } from "./ui/NoticeBar";
import { ProfileDialog } from "./ui/ProfileDialog";
import { RoleplayDialog } from "./ui/RoleplayDialog";
import { SettingsDialog } from "./ui/SettingsDialog";
import { Sidebar } from "./ui/Sidebar";
import { Toasts } from "./ui/Toasts";
import { ThreadView } from "./ui/ThreadView";
import { TopBar } from "./ui/TopBar";
import { WakingCard } from "./ui/WakingCard";

// D-100: the sidebar hidden or shown, kept by this page like the theme.
const SIDEBAR_KEY = "kokyu.sidebarHidden";

function sidebarHidden(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "1";
  } catch {
    return false; // storage blocked: shown
  }
}

export function App() {
  const [hidden, setHidden] = useState(sidebarHidden);
  const hide = (on: boolean) => {
    setHidden(on);
    try {
      localStorage.setItem(SIDEBAR_KEY, on ? "1" : "0");
    } catch {
      // storage blocked: it still applies for this session
    }
  };
  return (
    <div className={hidden ? "app sidebar-hidden" : "app"}>
      {hidden ? null : <Sidebar onHide={() => hide(true)} />}
      <main className="chat">
        <TopBar onShowSidebar={hidden ? () => hide(false) : undefined} />
        <ThreadView />
        <ConnectionBanner />
        <NoticeBar />
        <WakingCard />
        <Composer />
      </main>
      <SettingsDialog />
      <RoleplayDialog />
      <ProfileDialog />
      <ConfirmDialog />
      <CommandPalette />
      <Toasts />
    </div>
  );
}
