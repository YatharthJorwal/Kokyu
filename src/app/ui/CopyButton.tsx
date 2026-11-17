// Copy to the clipboard with a short "Copied" confirmation (FR-C-8, FR-C-9). With
// `icon`, the message bar's icon button (UI1-07): a tick says it worked.

import { useEffect, useState } from "react";

import { Icon } from "./Icon";

export function CopyButton({ text, label = "Copy", icon = false }: { text: string; label?: string; icon?: boolean }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (state === "idle") return;
    const t = window.setTimeout(() => setState("idle"), 1500);
    return () => window.clearTimeout(t);
  }, [state]);

  const said = state === "copied" ? "Copied" : state === "failed" ? "Couldn't copy" : null;
  return (
    <button
      type="button"
      className={icon ? "msg-action icon-action" : "msg-action"}
      aria-label={said ?? label}
      title={said ?? label}
      onClick={() => {
        navigator.clipboard.writeText(text).then(
          () => setState("copied"),
          () => setState("failed"),
        );
      }}
    >
      {icon ? <Icon name={state === "copied" ? "check" : "copy"} /> : (said ?? "Copy")}
    </button>
  );
}
