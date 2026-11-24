// Errors the user must see (RULES: no silent fallback) that are not about a turn:
// a refused send, a lost connection. A failed turn shows inline on the turn
// instead (TurnFailure, FR-R-5, K1-12).

import { barNotice, canPickModel, canRegenerate, fallbackLabel } from "../chat-state";
import { actions, useChat } from "../store";

export function NoticeBar() {
  const notice = useChat(barNotice);
  const canPick = useChat(canPickModel);
  const canRetry = useChat(canRegenerate);
  const fallback = useChat((s) => fallbackLabel(s, barNotice(s)));
  if (!notice) return null;
  // D-083, D-125: the unpriced-model note and "the fallback is answering" inform; they are not errors
  const info = notice.code === "price_unknown" || notice.code === "model_fallback";
  return (
    <div className={info ? "notice info" : "notice"} role={info ? "status" : "alert"}>
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
        {fallback && notice.fallback && canRetry ? (
          <button type="button" onClick={() => actions.regenerate(notice.fallback ?? undefined)}>
            Answer with {fallback}
          </button>
        ) : null}
        <button type="button" className="ghost" aria-label="Dismiss" onClick={() => actions.dismissNotice()}>
          ✕
        </button>
      </span>
    </div>
  );
}
