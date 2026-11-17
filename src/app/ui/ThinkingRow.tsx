// The status heart, just above the input box (K1-05, FR-C-5, D-063): calm while
// idle, spinning while she thinks, one beat when the first word of the reply
// arrives. The changing "thinking" line moved to where her reply appears (UI1-07,
// ThreadView's ThinkingReply).

import { Heart } from "./Heart";

export function ThinkingRow() {
  return (
    <div className="thinking-row">
      <Heart />
    </div>
  );
}
