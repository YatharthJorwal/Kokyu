// Errors the user must see (RULES: no silent fallback). A failed or refused
// model shows its message with Retry and Switch model (D-025, D-050); Switch
// model opens the model chip's picker (K1-10).

import { canPickModel } from "../chat-state";
import { actions, useChat } from "../store";

export function NoticeBar() {
  const notice = useChat((s) => s.notice);
  const canPick = useChat(canPickModel);
  if (!notice) return null;
  return (
    <div className="notice" role="alert">
      <span className="notice-text">{notice.text}</span>
      <span className="notice-actions">
        {notice.actions.includes("retry") ? (
          <button type="button" onClick={() => actions.retry()}>
            Retry
          </button>
        ) : null}
        {notice.actions.includes("switch_model") && canPick ? (
          <button type="button" onClick={() => actions.openPicker()}>
            Switch model
          </button>
        ) : null}
        <button type="button" className="ghost" aria-label="Dismiss" onClick={() => actions.dismissNotice()}>
          ✕
        </button>
      </span>
    </div>
  );
}
