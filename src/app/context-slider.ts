// Chat memory (D-098): how much of the conversation she keeps in mind, the model's
// context length, set per model in the picker under Effort. Pure logic for its
// slider, tested in Node: the detents, their labels, and where the thumb sits.

/** The smallest setting offered: below this a chat forgets too fast to be useful. */
export const MIN_CONTEXT = 8192;

/** 8K, 16K, 32K … doubling up to the model's maximum, plus the maximum itself when it
 * is not a power of two. A model that cannot hold 8K gets its maximum alone. */
export function contextDetents(max: number | null | undefined, min: number = MIN_CONTEXT): number[] {
  if (!max || !Number.isFinite(max) || max <= 0) return [];
  const top = Math.floor(max);
  if (top <= min) return [top];
  const stops: number[] = [];
  for (let n = min; n <= top; n *= 2) stops.push(n);
  if (stops[stops.length - 1] !== top) stops.push(top);
  return stops;
}

/** "8K", "128K", "1M", "200K", "1.5M"; tokens below 1K as they are. */
export function contextLabel(tokens: number): string {
  if (tokens >= 1024 * 1024 && tokens % (1024 * 1024) === 0) return `${tokens / (1024 * 1024)}M`;
  if (tokens >= 1_000_000) {
    const m = tokens / 1_048_576;
    return `${Number.isInteger(m) ? m : m.toFixed(1)}M`;
  }
  if (tokens >= 1024 && tokens % 1024 === 0) return `${tokens / 1024}K`;
  if (tokens >= 1000) return `${Math.round(tokens / 1000)}K`;
  return String(tokens);
}

/** The detent nearest to `tokens` (a value set elsewhere may fall between two). */
export function nearestDetent(stops: readonly number[], tokens: number | null | undefined): number {
  if (stops.length === 0 || !tokens) return -1;
  let best = 0;
  for (let i = 1; i < stops.length; i += 1) {
    if (Math.abs(Math.log2(stops[i] / tokens)) < Math.abs(Math.log2(stops[best] / tokens))) best = i;
  }
  return best;
}

/** Where a token count sits on the track, 0..1, spaced like the detents (doubling). */
export function trackPosition(stops: readonly number[], tokens: number): number {
  if (stops.length < 2) return 0;
  const lo = stops[0];
  const hi = stops[stops.length - 1];
  if (tokens <= lo) return 0;
  if (tokens >= hi) return 1;
  // Equal spacing per detent; between two detents, by doubling.
  for (let i = 0; i < stops.length - 1; i += 1) {
    const a = stops[i];
    const b = stops[i + 1];
    if (tokens <= b) return (i + Math.log2(tokens / a) / Math.log2(b / a)) / (stops.length - 1);
  }
  return 1;
}

/** What the picker's line under the slider says about `tokens` for this model; null
 * when nothing needs saying. Local models past their fit point get a warning (it
 * never blocks); API models a note on what longer costs. */
export function contextNote(
  ctx: { fit: number | null; spills: boolean },
  tokens: number,
  local: boolean,
): { text: string; warn: boolean } | null {
  if (!local) return { text: "Longer sends more of the chat with each message, so each one costs more.", warn: false };
  if (ctx.fit === null || tokens <= ctx.fit) return null;
  const tail = ctx.spills ? "replies will slow down." : "llama.cpp can't load it then.";
  if (ctx.fit < MIN_CONTEXT) return { text: `This model barely fits in your graphics memory; ${tail}`, warn: true };
  const at = ctx.fit >= 1024 * 1024 ? contextLabel(ctx.fit) : `${Math.floor(ctx.fit / 1024)}K`;
  return { text: `Past ${at} this won't fit in your graphics memory; ${tail}`, warn: true };
}
