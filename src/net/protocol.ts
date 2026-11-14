// Typed WebSocket protocol, version 1 -- the TypeScript mirror of
// KASANE/protocol/__init__.py (K1-00b; ARCHITECTURE §5.3). A kernel test reads
// the three lists below and fails if they drift from the Python ones.
//
// Every message added from K1 on travels in one envelope:
//   { v: 1, type, id, thread, data }
// Yuri's older flat messages (speak, turn_end, ...) still arrive without `v`
// until the K1 shell replaces the widget (D-049); `parseFrame` returns null
// for those so existing handlers keep working.

export const PROTOCOL_VERSION = 1;

export const CLIENT_TYPES = [
  "hello",
  "thread_list",
  "thread_search",
  "thread_new",
  "thread_open",
  "thread_delete",
  "thread_rename",
  "set_model",
  "set_effort",
  "model_list",
  "model_load",
  "regenerate",
  "screen_companion",
  "typing",
] as const;

export const SERVER_TYPES = [
  "hello",
  "thread_opened",
  "thread_list",
  "thread_message",
  "thread_updated",
  "turn_start",
  "token",
  "turn_done",
  "error",
  "model_list",
  "model_status",
  "screen_companions",
] as const;

export const ERROR_CODES = [
  "bad_message",
  "protocol_version",
  "unknown_thread",
  "unknown_waifu",
  "turn_running",
  "threads_unavailable",
  "model_blocked",
  "model_failed",
  "vision_unavailable",
] as const;

/** K1-05b (FR-SC-2): what is watching the screen right now. */
export interface ScreenCompanions {
  task_guide: { on: boolean; task: string | null };
  ocr_watch: { on: boolean };
}

export type ClientType = (typeof CLIENT_TYPES)[number];
export type ServerType = (typeof SERVER_TYPES)[number];
export type ErrorCode = (typeof ERROR_CODES)[number];

export interface ThreadInfo {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  active_waifu_id: string | null;
  model_ref: string | null;
  effort: string | null;
  temp: boolean;
  archived: boolean;
}

export interface ThreadMessage {
  id: number;
  thread_id: string;
  ts: number;
  role: "user" | "assistant" | "divider";
  content: string;
  speaker_waifu_id: string | null;
  speaker_name: string | null;
  model_ref: string | null;
  effort: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  meta: Record<string, unknown>;
}

/** One row of the model picker (K1-10; FR-M-3, 4). */
export interface ModelRow {
  ref: string;
  label: string;
  kind: "local" | "api";
  backend: string;
  detail: string | null;
  size_bytes: number | null;
  /** False: listed but not usable now (no key, missing file); `note` says why. */
  available: boolean;
  note: string | null;
  /** Fits in VRAM? Null until the VRAM manager (K1-09). */
  fits: boolean | null;
  price_in?: number | null;
  price_out?: number | null;
  tags?: string[];
  /** API rows: the vendor the model is listed under (FR-M-4). */
  group?: string | null;
}

export interface Spend {
  /** Off: the caps are not enforced, so the footer does not show them. */
  enabled: boolean;
  hour_usd?: number;
  hourly_cap_usd?: number | null;
  day_usd: number;
  month_usd: number;
  daily_cap_usd: number | null;
  monthly_cap_usd: number | null;
}

export interface ModelListData {
  /** The model a thread without a choice uses. */
  default_ref: string;
  local: ModelRow[];
  api: ModelRow[];
  local_error: string | null;
  api_error: string | null;
  api_stale: boolean;
  api_key: boolean;
  spend: Spend | null;
}

export type ModelLoadState = "idle" | "loading" | "ready" | "failed";

/** The kernel's chat-model load (K1-10, FR-M-6). */
export interface ModelStatus {
  model_ref: string | null;
  label: string | null;
  state: ModelLoadState;
  message: string | null;
  /** Seconds spent loading when the frame was sent. */
  elapsed_s: number | null;
}

export interface ServerData {
  /** The kernel's defaults for a thread with no choice of its own (K1-10). */
  hello: { protocol: number; kernel: string; default_model_ref?: string; default_effort?: string | null };
  thread_opened: { thread: ThreadInfo; messages: ThreadMessage[] };
  thread_list: { query: string; threads: ThreadInfo[] };
  thread_message: { message: ThreadMessage };
  thread_updated: { thread: ThreadInfo };
  turn_start: { user_text: string };
  token: { text: string };
  turn_done: { text: string; stopped: boolean };
  error: {
    code: ErrorCode;
    message: string;
    reply_to: string | null;
    reason?: string;
    model_ref?: string | null;
    actions?: ("retry" | "switch_model")[];
  };
  model_list: ModelListData;
  model_status: ModelStatus;
  screen_companions: ScreenCompanions;
}

export interface ClientData {
  hello: { client: "main" | "pet" | "dev"; protocol: number };
  thread_list: Record<string, never>;
  thread_search: { query: string };
  thread_new: Record<string, never>;
  thread_open: { id: string };
  thread_delete: { id: string };
  thread_rename: { id: string; title: string };
  set_model: { model_ref: string | null };
  set_effort: { effort: Effort | null };
  model_list: { refresh?: boolean };
  model_load: Record<string, never>;
  regenerate: Record<string, never>;
  screen_companion: { mode: "task_guide" | "ocr_watch"; on: boolean; task?: string };
  typing: Record<string, never>;
}

export type Effort = "off" | "low" | "medium" | "high";

export interface Frame<T extends ServerType = ServerType> {
  v: number;
  type: T;
  id: string;
  thread: string | null;
  data: ServerData[T];
}

let counter = 0;

/** A client -> kernel envelope. */
export function clientFrame<T extends ClientType>(
  type: T,
  data: ClientData[T],
  thread: string | null = null,
): { v: number; type: T; id: string; thread: string | null; data: ClientData[T] } {
  counter += 1;
  return { v: PROTOCOL_VERSION, type, id: `c${Date.now().toString(36)}${counter}`, thread, data };
}

export type ParseResult =
  | { kind: "legacy" }
  | { kind: "frame"; frame: Frame }
  | { kind: "error"; reason: string };

/** Classifies an incoming message: a legacy flat message, a valid v1 frame, or a problem. */
export function parseFrame(raw: unknown): ParseResult {
  if (typeof raw !== "object" || raw === null || !("v" in raw)) return { kind: "legacy" };
  const f = raw as Record<string, unknown>;
  if (f.v !== PROTOCOL_VERSION) {
    return { kind: "error", reason: `kernel speaks protocol ${String(f.v)}, this window speaks ${PROTOCOL_VERSION}` };
  }
  if (typeof f.type !== "string" || !(SERVER_TYPES as readonly string[]).includes(f.type)) {
    return { kind: "error", reason: `unknown message type ${String(f.type)}` };
  }
  if (typeof f.data !== "object" || f.data === null) {
    return { kind: "error", reason: `${f.type}: data must be an object` };
  }
  return { kind: "frame", frame: raw as Frame };
}

/** What the user sees of a streamed reply: a trailing emotion tag (`[happy]`),
 * or one still being written (`[hap`), is hidden. Mirrors protocol.strip_trailing_tag. */
export function stripTrailingTag(text: string): string {
  const s = text.trimEnd();
  const open = s.lastIndexOf("[");
  if (open === -1) return text;
  const tail = s.slice(open);
  if (tail.slice(0, -1).includes("]") || tail.replace(/^\[|\]$/g, "").includes(" ")) return text;
  if (tail.endsWith("]") || !tail.includes("]")) return s.slice(0, open).trimEnd();
  return text;
}

/** Accumulates `token` frames for one thread into the text to display. */
export class ReplyAccumulator {
  private raw = "";
  constructor(public readonly thread: string | null) {}
  push(text: string): string {
    this.raw += text;
    return this.visible;
  }
  get visible(): string {
    return stripTrailingTag(this.raw);
  }
}
