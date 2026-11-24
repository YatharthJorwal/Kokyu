// The Kōkyū window (K1-02, laid out to the reference in K1-15, D-068): sidebar,
// then the chat column with its top bar, the open thread (or her on the Stage,
// D-104) and the input box.

import { Suspense, lazy, useState } from "react";

import { Composer } from "./ui/Composer";
import { CommandPalette } from "./ui/CommandPalette";
import { ConfirmDialog } from "./ui/ConfirmDialog";
import { ConnectionBanner } from "./ui/ConnectionBanner";
import { NoticeBar } from "./ui/NoticeBar";
import { Pet } from "./ui/Pet";
import { actions, useChat } from "./store";
import { usePasteLimitNote } from "./paste";
import { ProfileDialog } from "./ui/ProfileDialog";
import { RoleplayDialog } from "./ui/RoleplayDialog";
import { SettingsDialog } from "./ui/SettingsDialog";
import { StoryDialog } from "./ui/StoryDialog";
import { Sidebar } from "./ui/Sidebar";
import { Toasts } from "./ui/Toasts";
import { ThreadView } from "./ui/ThreadView";
import { TopBar } from "./ui/TopBar";
import { WakingCard } from "./ui/WakingCard";

// three.js loads only when the Stage is first opened.
const Stage = lazy(() => import("./ui/Stage").then((m) => ({ default: m.Stage })));

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
  usePasteLimitNote(actions.toast);
  const [hidden, setHidden] = useState(sidebarHidden);
  const view = useChat((s) => s.view);
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
        {view === "stage" ? (
          <Suspense fallback={<div className="stage" />}>
            <Stage />
          </Suspense>
        ) : (
          <>
            <ThreadView />
            <Pet />
          </>
        )}
        <ConnectionBanner />
        <NoticeBar />
        <WakingCard />
        <Composer />
      </main>
      <SettingsDialog />
      <RoleplayDialog />
      <ProfileDialog />
      <StoryDialog />
      <ConfirmDialog />
      <CommandPalette />
      <Toasts />
    </div>
  );
}
