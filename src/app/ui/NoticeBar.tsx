// Errors the user must see (RULES: no silent fallback) that are not about a turn:
// a refused send, a lost connection. A failed turn shows inline on the turn
// instead (TurnFailure, FR-R-5, K1-12).

import { barNotice, canPickModel, canRegenerate } from "../chat-state";
import { actions, useChat } from "../store";

export function NoticeBar() {
  const notice = useChat(barNotice);
  const canPick = useChat(canPickModel);
  const canRetry = useChat(canRegenerate);
  if (!notice) return null;
  return (
    // D-083: the unpriced-model notice informs; it is not an error
    <div className={notice.code === "price_unknown" ? "notice info" : "notice"} role={notice.code === "price_unknown" ? "status" : "alert"}>
      <span className="notice-text">{notice.text}</span>
      <span className="notice-actions">
        {notice.actions.includes("retry") && canRetry ? (
          <button type="button" onClick={() => actions.regenerate()}>
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
