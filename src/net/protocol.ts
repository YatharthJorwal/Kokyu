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
] as const;

export const SERVER_TYPES = [
  "hello",
  "thread_opened",
  "thread_list",
  "thread_message",
  "turn_start",
  "token",
  "turn_done",
  "error",
] as const;

export const ERROR_CODES = [
  "bad_message",
  "protocol_version",
  "unknown_thread",
  "unknown_waifu",
  "turn_running",
  "threads_unavailable",
] as const;

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

export interface ServerData {
  hello: { protocol: number; kernel: string };
  thread_opened: { thread: ThreadInfo; messages: ThreadMessage[] };
  thread_list: { query: string; threads: ThreadInfo[] };
  thread_message: { message: ThreadMessage };
  turn_start: { user_text: string };
  token: { text: string };
  turn_done: { text: string; stopped: boolean };
  error: { code: ErrorCode; message: string; reply_to: string | null };
}

export interface ClientData {
  hello: { client: "main" | "pet" | "dev"; protocol: number };
  thread_list: Record<string, never>;
  thread_search: { query: string };
  thread_new: Record<string, never>;
  thread_open: { id: string };
  thread_delete: { id: string };
  thread_rename: { id: string; title: string };
}

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
