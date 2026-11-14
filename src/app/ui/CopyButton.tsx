// Copy to the clipboard with a short "Copied" confirmation (FR-C-8, FR-C-9).

import { useEffect, useState } from "react";

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (state === "idle") return;
    const t = window.setTimeout(() => setState("idle"), 1500);
    return () => window.clearTimeout(t);
  }, [state]);

  return (
    <button
      type="button"
      className="msg-action"
      aria-label={label}
      title={label}
      onClick={() => {
        navigator.clipboard.writeText(text).then(
          () => setState("copied"),
          () => setState("failed"),
        );
      }}
    >
      {state === "copied" ? "Copied" : state === "failed" ? "Couldn't copy" : "Copy"}
    </button>
  );
}
