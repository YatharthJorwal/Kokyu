// Pure helpers for the active waifu on the page (no DOM, no WebSocket), so they are
// unit-testable. A waifu is a voice and a persona; the page only shows which one is active
// and loads her avatar (RULES R-01, R-08: no business logic in the client).

export type WaifuInfo = { id: string; name: string; premade: boolean; traits: string[] };

export type WaifuStateMessage = {
  type: "waifu_state";
  /** The waifu the kernel is using now, or null when no pack is installed (legacy persona). */
  active: string | null;
  waifus: WaifuInfo[];
  /** Plain-language reasons packs were skipped (shown in the doctor/settings later). */
  problems: string[];
  /** A switch asked for while a turn was running; the kernel applies it between turns. */
  pending?: string;
};

export const WAIFU_STORAGE_KEY = "kokyu.waifu";

/** `ws://127.0.0.1:8780/ws` -> `http://127.0.0.1:8780`. */
export function kernelHttpBase(wsUrl: string): string {
  return wsUrl.replace(/^ws(s?):\/\//, "http$1://").replace(/\/ws(\?.*)?$/, "");
}

export function vrmUrl(httpBase: string, waifuId: string): string {
  return `${httpBase}/waifus/${encodeURIComponent(waifuId)}/vrm`;
}

/** Which avatar file to load at startup: the stored waifu's, else the legacy default. */
export function resolveModelPath(storedId: string | null, defaultPath: string, httpBase: string): string {
  return storedId ? vrmUrl(httpBase, storedId) : defaultPath;
}

/** The kernel is authoritative. Reload only when it names a waifu other than the one whose
 * avatar is on screen, so a reload can never loop. */
export function needsAvatarReload(loadedId: string | null, active: string | null): boolean {
  return active !== null && active !== loadedId;
}

/** With no audio (voice backend down) the caption still shows, for about as long as it
 * takes to read. */
export function captionOnlyDurationMs(text: string): number {
  const ms = 1200 + 55 * text.length;
  return Math.max(1200, Math.min(6000, ms));
}

/** Option labels for the companion list; premade companions first (the kernel already sorts). */
export function waifuOptions(msg: WaifuStateMessage): { value: string; label: string; selected: boolean }[] {
  return msg.waifus.map((w) => ({ value: w.id, label: w.name, selected: w.id === (msg.pending ?? msg.active) }));
}
