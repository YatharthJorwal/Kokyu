// Copy to the clipboard with a short "Copied" confirmation (FR-C-8, FR-C-9). With
// `icon`, the message bar's icon button (UI1-07): a tick says it worked.

import { useEffect, useState } from "react";

import { Icon } from "./Icon";

export function CopyButton({
  text,
  label = "Copy",
  icon = false,
  showLabel = false,
}: {
  text: string;
  label?: string;
  icon?: boolean;
  /** With `icon`: the word "Copy" beside it (a code block's header, UI1-08). */
  showLabel?: boolean;
}) {
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
      className={icon ? (showLabel ? "msg-action icon-action labelled" : "msg-action icon-action") : "msg-action"}
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
      {icon && showLabel ? <span>{said ?? "Copy"}</span> : null}
    </button>
  );
}
