// A paste that does not fit a field's limit is cut by the browser without a word (the
// audit, D-123): one listener for every capped input and text area says what was left out.

import { useEffect } from "react";

/** How many pasted characters a field with `max` (maxLength) cannot take: the text it
 * keeps (`length` minus the selection the paste replaces) plus the paste, past the limit. */
export function pasteOverflow(length: number, selected: number, pasted: number, max: number): number {
  if (max <= 0) return 0; // no maxLength
  return Math.max(0, length - selected + pasted - max);
}

export function pasteNote(pasted: number, lost: number, max: number): string {
  const n = (v: number) => v.toLocaleString("en-US");
  return `Only ${n(pasted - lost)} of the ${n(pasted)} pasted characters fit. The limit here is ${n(max)}.`;
}

/** Mounted once, in App: tells the user through `say` when a paste was cut. */
export function usePasteLimitNote(say: (text: string) => void): void {
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const el = e.target;
      if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement)) return;
      const pasted = e.clipboardData?.getData("text") ?? "";
      const selected = Math.abs((el.selectionEnd ?? 0) - (el.selectionStart ?? 0));
      const lost = pasteOverflow(el.value.length, selected, pasted.length, el.maxLength);
      if (lost > 0) say(pasteNote(pasted.length, lost, el.maxLength));
    };
    document.addEventListener("paste", onPaste, true);
    return () => document.removeEventListener("paste", onPaste, true);
  }, [say]);
}
