// The Stage's caption, from Yuri's (D-111): her words pop in one at a time with the
// voice clip that is playing. The voice engine gives no word timings, so each word
// gets a share of the clip's length in proportion to its letters. Pure logic here;
// Stage.tsx draws it.

/** How many spoken words stay, dimmed, behind the glowing one before folding away. */
export const TRAIL_WORDS = 4;

export type WordState = "hidden" | "active" | "spoken" | "fading";

export function splitWords(text: string): string[] {
  return text.trim().split(/\s+/).filter(Boolean);
}

/** Where in the clip (0..1) each word starts. */
export function wordStarts(words: readonly string[]): number[] {
  const total = words.reduce((sum, w) => sum + w.length, 0) || 1;
  let seen = 0;
  return words.map((w) => {
    const start = seen / total;
    seen += w.length;
    return start;
  });
}

/** The word being said at `fraction` of the clip. */
export function activeWord(starts: readonly number[], fraction: number): number {
  let index = 0;
  for (let i = 0; i < starts.length; i += 1) {
    if (starts[i] <= fraction) index = i;
    else break;
  }
  return index;
}

export function wordState(index: number, active: number): WordState {
  if (index === active) return "active";
  if (index > active) return "hidden";
  return active - index > TRAIL_WORDS ? "fading" : "spoken";
}
