// Short confirmations that fade by themselves (UI1-09): "Pinned", "Conversation
// deleted". Errors never come this way: they stay in the notice bar or on the turn
// until dismissed (RULES: no silent fallback).

import { useEffect } from "react";

import type { Toast } from "../chat-state";
import { actions, useChat } from "../store";

const SHOWN_MS = 3000;

export function Toasts() {
  const toasts = useChat((s) => s.toasts);
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}

function ToastItem({ toast }: { toast: Toast }) {
  useEffect(() => {
    const t = window.setTimeout(() => actions.dismissToast(toast.id), SHOWN_MS);
    return () => window.clearTimeout(t);
  }, [toast.id]);
  return <div className="toast">{toast.text}</div>;
}
