// The in-app confirm (UI1-09), in place of the browser's own box: a title, a line
// of detail, Cancel (focused: the safe choice) and the action. Escape or a click
// outside cancels.

import { useEffect, useRef } from "react";

import { actions, useChat } from "../store";

export function ConfirmDialog() {
  const ask = useChat((s) => s.confirm);
  const cancel = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!ask) return;
    const back = document.activeElement as HTMLElement | null;
    cancel.current?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        actions.answerConfirm(false);
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      back?.focus?.();
    };
  }, [ask]);

  if (!ask) return null;
  return (
    <div className="settings-backdrop confirm-layer" onMouseDown={(e) => e.target === e.currentTarget && actions.answerConfirm(false)}>
      <div className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby={ask.body ? "confirm-body" : undefined}>
        <h2 id="confirm-title">{ask.title}</h2>
        {ask.body ? <p id="confirm-body">{ask.body}</p> : null}
        <div className="confirm-actions">
          <button ref={cancel} type="button" onClick={() => actions.answerConfirm(false)}>
            Cancel
          </button>
          <button type="button" className={ask.danger ? "danger" : "primary"} onClick={() => actions.answerConfirm(true)}>
            {ask.action}
          </button>
        </div>
      </div>
    </div>
  );
}
