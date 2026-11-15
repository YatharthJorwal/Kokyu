// The Kōkyū window (K1-02, laid out to the reference in K1-15, D-068): sidebar,
// then the chat column with its top bar, the open thread and the input box. The
// Stage view with the avatar arrives in K2 (its engine waits in src/engine/).

import { Composer } from "./ui/Composer";
import { NoticeBar } from "./ui/NoticeBar";
import { SettingsDialog } from "./ui/SettingsDialog";
import { Sidebar } from "./ui/Sidebar";
import { ThinkingRow } from "./ui/ThinkingRow";
import { ThreadView } from "./ui/ThreadView";
import { TopBar } from "./ui/TopBar";

export function App() {
  return (
    <div className="app">
      <Sidebar />
      <main className="chat">
        <TopBar />
        <ThreadView />
        <NoticeBar />
        <ThinkingRow />
        <Composer />
      </main>
      <SettingsDialog />
    </div>
  );
}
