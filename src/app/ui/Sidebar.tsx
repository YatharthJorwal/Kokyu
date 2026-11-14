// Sidebar, first version (K1-02): companion, New chat, the thread list, Settings.
// Grouping by day, search, rename and delete are K1-03 (FR-C-6).

import { actions, useChat } from "../store";

export function Sidebar() {
  const threads = useChat((s) => s.threads);
  const current = useChat((s) => s.thread?.id ?? null);
  const companion = useChat((s) => s.companion);
  const busy = useChat((s) => s.turn !== "idle");
  const connection = useChat((s) => s.connection);

  return (
    <aside className="sidebar" aria-label="Conversations">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          ♡
        </span>
        <span className="brand-name">Kōkyū</span>
      </div>

      <div className="companion" title="Active companion">
        <span className="avatar-dot" aria-hidden="true">
          {(companion?.name ?? "?").slice(0, 1)}
        </span>
        <span>{companion?.name ?? "No companion installed"}</span>
      </div>

      <button
        type="button"
        className="new-chat"
        onClick={() => actions.newThread()}
        disabled={busy || connection !== "online"}
      >
        + New chat
      </button>

      <nav className="history" aria-label="History">
        {threads.length === 0 ? (
          <p className="muted small">No conversations yet.</p>
        ) : (
          <ul>
            {threads.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className={t.id === current ? "thread-item active" : "thread-item"}
                  aria-current={t.id === current ? "page" : undefined}
                  onClick={() => actions.openThread(t.id)}
                  disabled={busy && t.id !== current}
                  title={t.title}
                >
                  {t.title || "New chat"}
                  {t.temp ? <span className="badge">Temp</span> : null}
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>

      <div className="sidebar-footer">
        <button type="button" className="settings" disabled title="Settings arrive in a later step">
          Settings
        </button>
        <span className={`conn conn-${connection}`} role="status">
          {connection === "online" ? "Connected" : connection === "connecting" ? "Connecting…" : "Kernel offline"}
        </span>
      </div>
    </aside>
  );
}
