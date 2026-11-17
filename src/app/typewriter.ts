// How fast a reply is shown (D-096): letter by letter, as if being written, never
// in the lumps the network delivers. It keeps up with any model: the further the
// shown text is behind, the faster it types.

/** Letters per second when the text is only a little ahead. */
export const MIN_CPS = 50;
/** Any backlog is mostly caught up within about this long. */
export const CATCH_UP_S = 0.7;

/** How many UTF-16 units of `text` to show after `dtMs` more milliseconds. */
export function revealTo(shown: number, text: string, dtMs: number): number {
  const total = text.length;
  if (shown >= total) return total;
  const rate = Math.max(MIN_CPS, (total - shown) / CATCH_UP_S);
  let next = Math.min(total, shown + Math.max(1, Math.round((rate * Math.max(0, dtMs)) / 1000)));
  // Never split a surrogate pair: half an emoji draws as a box.
  const code = text.charCodeAt(next - 1);
  if (code >= 0xd800 && code <= 0xdbff && next < total) next += 1;
  return next;
}
