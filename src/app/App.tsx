// The Kōkyū window (K1-02, laid out to the reference in K1-15, D-068): sidebar,
// then the chat column with its top bar, the open thread and the input box. The
// Stage view with the avatar arrives in K2 (its engine waits in src/engine/).

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

export function App() {
  return (
    <div className="app">
      <Sidebar />
      <main className="chat">
        <TopBar />
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
