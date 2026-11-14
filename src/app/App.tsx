// The Kōkyū window (K1-02): sidebar and the open thread. The Stage view with
// the avatar arrives in K2; until then Yuri's widget stays at /widget.html.

import { Composer } from "./ui/Composer";
import { NoticeBar } from "./ui/NoticeBar";
import { Sidebar } from "./ui/Sidebar";
import { ThreadView } from "./ui/ThreadView";
import { useChat } from "./store";

function Header() {
  const title = useChat((s) => s.thread?.title || "New chat");
  const temp = useChat((s) => s.thread?.temp ?? false);
  // The model chip lives in the input row (K1-10, FR-M-1), not up here.
  return (
    <header className="chat-header">
      <h1>{title}</h1>
      <span className="chips">
        {temp ? <span className="chip" title="Nothing from this chat goes into memory">Temp Chat</span> : null}
      </span>
    </header>
  );
}

export function App() {
  return (
    <div className="app">
      <Sidebar />
      <main className="chat">
        <Header />
        <ThreadView />
        <NoticeBar />
        <Composer />
      </main>
    </div>
  );
}
