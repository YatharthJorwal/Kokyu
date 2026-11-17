// Read aloud (D-097): she speaks each reply once it has finished. The engine keeps
// the switch (settings.json) and starts her voice only while it is on; this is the
// composer chip's wording for its state. Pure, so it is tested in Node.

import type { ReadAloudStatus } from "../net/protocol";

/** How long GPT-SoVITS takes to answer after a cold start on the reference PC (STATE.md). */
export const VOICE_START_S = 47;

/** The chip's line; null when Read aloud is off (no chip). `elapsedS`: seconds the
 * voice has been starting, counted by the window from the engine's figure. */
export function readAloudLine(status: ReadAloudStatus | null, name: string, elapsedS: number): string | null {
  if (!status?.on) return null;
  if (status.state === "failed") return `${name}'s voice couldn't start. ${status.message ?? ""}`.trim();
  if (status.state === "ready") return `Read aloud: ${name} reads her replies`;
  const secs = Math.max(0, Math.floor(elapsedS));
  if (status.state === "idle" || secs === 0) return `Starting ${name}'s voice, about ${VOICE_START_S} s…`;
  return secs < VOICE_START_S
    ? `Starting ${name}'s voice… ${secs} s of about ${VOICE_START_S}`
    : `Starting ${name}'s voice… ${secs} s`;
}

/** The voice is on its way up: the chip pulses and counts. */
export function voiceStarting(status: ReadAloudStatus | null): boolean {
  return !!status?.on && (status.state === "loading" || status.state === "idle");
}
