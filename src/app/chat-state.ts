// The chat window's state as a pure reducer (K1-02, D-013): every kernel frame,
// legacy message and local event goes through `reduce`, so the behaviour is
// testable in Node without a DOM. The Zustand store (store.ts) only wraps it.
// Clients hold no business logic (RULES): this decides what to *show*, never
// what the kernel does.

import { stripTrailingTag, type ErrorCode, type Frame, type ThreadInfo, type ThreadMessage } from "../net/protocol";

export type ConnectionStatus = "connecting" | "online" | "offline";
export type TurnPhase = "idle" | "thinking" | "replying";
export type SurfaceRole = "driver" | "observer";

export interface ChatMessage {
  key: string;
  role: "user" | "assistant" | "divider";
  text: string;
  speaker: string | null;
  /** Stop cut the reply short (FR-C-2). */
  stopped?: boolean;
  /** Sent by this window, not yet acknowledged by `turn_start`. */
  pending?: boolean;
  /** The model call for this user line failed (shown with Retry). */
  failed?: boolean;
}

export interface Notice {
  code: ErrorCode | "client";
  text: string;
  actions: ("retry" | "switch_model")[];
}

export interface Companion {
  id: string;
  name: string;
}

export interface ChatState {
  connection: ConnectionStatus;
  role: SurfaceRole;
  thread: ThreadInfo | null;
  threads: ThreadInfo[];
  messages: ChatMessage[];
  turn: TurnPhase;
  /** Raw tokens of the reply being streamed (may end in a half-written emotion tag). */
  streamRaw: string;
  notice: Notice | null;
  companion: Companion | null;
  /** The last line the user sent, for Retry. */
  lastUserText: string | null;
}

export type LegacyMessage = { type: string; [key: string]: unknown };

export type ChatEvent =
  | { kind: "frame"; frame: Frame }
  | { kind: "legacy"; msg: LegacyMessage }
  | { kind: "status"; status: ConnectionStatus }
  | { kind: "problem"; reason: string }
  | { kind: "sent"; text: string }
  | { kind: "retrying" }
  | { kind: "dismiss_notice" };

export const initialState: ChatState = {
  connection: "connecting",
  role: "driver",
  thread: null,
  threads: [],
  messages: [],
  turn: "idle",
  streamRaw: "",
  notice: null,
  companion: null,
  lastUserText: null,
};

let localCounter = 0;
function localKey(): string {
  localCounter += 1;
  return `l${localCounter}`;
}

export function fromStored(m: ThreadMessage): ChatMessage {
  return {
    key: `m${m.id}`,
    role: m.role,
    text: m.content,
    speaker: m.speaker_name,
    stopped: m.meta?.stopped === true ? true : undefined,
  };
}

/** What the streaming bubble shows: the reply so far without a trailing emotion tag. */
export function visibleStream(state: ChatState): string {
  return stripTrailingTag(state.streamRaw);
}

/** Composer rules: one turn at a time, only the window that drives the kernel may talk. */
export function canSend(state: ChatState): boolean {
  return state.connection === "online" && state.role === "driver" && state.turn === "idle";
}

function upsertThread(threads: ThreadInfo[], thread: ThreadInfo): ThreadInfo[] {
  const found = threads.some((t) => t.id === thread.id);
  const next = found ? threads.map((t) => (t.id === thread.id ? thread : t)) : [thread, ...threads];
  return next.filter((t) => !t.archived).sort((a, b) => b.updated_at - a.updated_at);
}

function forCurrentThread(state: ChatState, frame: Frame): boolean {
  return frame.thread === null || state.thread === null || frame.thread === state.thread.id;
}

function markLastUser(messages: ChatMessage[], patch: Partial<ChatMessage>): ChatMessage[] {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "user") {
      const copy = messages.slice();
      copy[i] = { ...copy[i], ...patch };
      return copy;
    }
  }
  return messages;
}

function reduceFrame(state: ChatState, frame: Frame): ChatState {
  switch (frame.type) {
    case "hello":
      return state;
    case "thread_opened": {
      const data = frame.data as { thread: ThreadInfo; messages: ThreadMessage[] };
      return {
        ...state,
        thread: data.thread,
        threads: upsertThread(state.threads, data.thread),
        messages: data.messages.map(fromStored),
        streamRaw: "",
        notice: null,
      };
    }
    case "thread_list": {
      const data = frame.data as { query: string; threads: ThreadInfo[] };
      if (data.query.trim()) return state; // search results belong to the sidebar's search (K1-03)
      // The list also carries the open thread's newest title (set from the first message).
      const fresh = state.thread ? data.threads.find((t) => t.id === state.thread?.id) : undefined;
      return { ...state, thread: fresh ?? state.thread, threads: data.threads.filter((t) => !t.archived) };
    }
    case "thread_updated": {
      const { thread } = frame.data as { thread: ThreadInfo };
      return {
        ...state,
        thread: state.thread?.id === thread.id ? thread : state.thread,
        threads: upsertThread(state.threads, thread),
      };
    }
    case "thread_message": {
      if (!forCurrentThread(state, frame)) return state;
      const { message } = frame.data as { message: ThreadMessage };
      return { ...state, messages: [...state.messages, fromStored(message)] };
    }
    case "turn_start": {
      if (!forCurrentThread(state, frame)) return state;
      const { user_text } = frame.data as { user_text: string };
      const last = state.messages[state.messages.length - 1];
      const messages =
        last && last.role === "user" && last.pending && last.text === user_text
          ? [...state.messages.slice(0, -1), { ...last, pending: false }]
          : [...state.messages, { key: localKey(), role: "user" as const, text: user_text, speaker: null }];
      return { ...state, messages, turn: "thinking", streamRaw: "", lastUserText: user_text };
    }
    case "token": {
      if (!forCurrentThread(state, frame)) return state;
      const { text } = frame.data as { text: string };
      return { ...state, turn: "replying", streamRaw: state.streamRaw + text };
    }
    case "turn_done": {
      if (!forCurrentThread(state, frame)) return state;
      const { text, stopped } = frame.data as { text: string; stopped: boolean };
      const reply = text || visibleStream(state);
      const messages = reply
        ? [
            ...state.messages,
            {
              key: localKey(),
              role: "assistant" as const,
              text: reply,
              speaker: state.companion?.name ?? null,
              stopped: stopped || undefined,
            },
          ]
        : state.messages;
      return { ...state, messages, turn: "idle", streamRaw: "" };
    }
    case "error": {
      const data = frame.data as { code: ErrorCode; message: string; actions?: ("retry" | "switch_model")[] };
      const notice: Notice = { code: data.code, text: data.message, actions: data.actions ?? [] };
      const failedTurn = data.code === "model_blocked" || data.code === "model_failed";
      return {
        ...state,
        notice,
        messages: failedTurn ? markLastUser(state.messages, { failed: true, pending: false }) : state.messages,
        // A refused send never started a turn; a failed turn still ends with turn_done.
        turn: data.code === "turn_running" ? state.turn : failedTurn ? state.turn : "idle",
      };
    }
    default:
      return state;
  }
}

function reduceLegacy(state: ChatState, msg: LegacyMessage): ChatState {
  switch (msg.type) {
    case "waifu_state": {
      const active = msg.active as string | null;
      const roster = (msg.waifus as { id: string; name: string }[] | undefined) ?? [];
      const found = roster.find((w) => w.id === active);
      return { ...state, companion: found ? { id: found.id, name: found.name } : null };
    }
    case "surface_status":
      return { ...state, role: msg.role === "observer" ? "observer" : "driver" };
    case "turn_end":
      // Yuri's end-of-turn message. turn_done normally arrived first; this only
      // closes a turn the kernel ended without one (an old kernel, or a Stop race).
      if (state.turn === "idle") return state;
      return reduceFrame(state, {
        v: 1,
        type: "turn_done",
        id: "legacy",
        thread: null,
        data: { text: "", stopped: true },
      });
    default:
      return state;
  }
}

export function reduce(state: ChatState, event: ChatEvent): ChatState {
  switch (event.kind) {
    case "frame":
      return reduceFrame(state, event.frame);
    case "legacy":
      return reduceLegacy(state, event.msg);
    case "status": {
      const next = { ...state, connection: event.status };
      // A dropped connection ends whatever was streaming; the kernel restarts clean.
      return event.status === "online" ? next : { ...next, turn: "idle", streamRaw: "" };
    }
    case "problem":
      return { ...state, notice: { code: "client", text: event.reason, actions: [] } };
    case "sent":
      return {
        ...state,
        messages: [...state.messages, { key: localKey(), role: "user", text: event.text, speaker: null, pending: true }],
        turn: "thinking",
        notice: null,
        lastUserText: event.text,
      };
    case "retrying": {
      // Drop the failed line; the resend adds it again.
      const idx = state.messages.map((m) => m.failed === true).lastIndexOf(true);
      const messages = idx >= 0 ? state.messages.filter((_, i) => i !== idx) : state.messages;
      return { ...state, messages, notice: null };
    }
    case "dismiss_notice":
      return { ...state, notice: null };
  }
}
