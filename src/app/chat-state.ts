// The chat window's state as a pure reducer (K1-02, D-013): every kernel frame
// and local event goes through `reduce`, so the behaviour is
// testable in Node without a DOM. The Zustand store (store.ts) only wraps it.
// Clients hold no business logic (RULES): this decides what to *show*, never
// what the kernel does.

import {
  stripTrailingTag,
  type ErrorCode,
  type Frame,
  type ModelListData,
  type ModelStatus,
  type ScreenCompanions,
  type ServerData,
  type VoiceStatus,
  type ThreadInfo,
  type ThreadMessage,
} from "../net/protocol";
import { shortRef } from "./models";

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
  /** An attachment on this line went to this API model (FR-R-7 badge). */
  sentTo?: string;
}

export interface Notice {
  code: ErrorCode | "client";
  text: string;
  actions: ("retry" | "switch_model")[];
  detail?: string | null;
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
  /** The thread as it was before a Regenerate; it comes back if no new reply does
   * (the kernel keeps the old exchange then). */
  beforeRegenerate: ChatMessage[] | null;
  /** A switch asked for mid-reply; she takes over from the next turn (FR-S-2). */
  pendingCompanion: Companion | null;
  /** Every installed companion, for the sidebar (K1-03, FR-C-6). */
  roster: Companion[];
  /** The sidebar's search results (K1-03); null when not searching. */
  search: { query: string; threads: ThreadInfo[] } | null;
  /** What a thread with no model or effort of its own uses (from the kernel's hello). */
  defaults: { model_ref: string | null; effort: string | null } | null;
  /** What the model picker lists (K1-10); null until first asked. */
  models: ModelListData | null;
  /** The kernel's chat-model load: the "waking up" card and the chip (FR-M-6). */
  modelStatus: ModelStatus | null;
  pickerOpen: boolean;
  /** Task Guide / OCR watch (K1-05b); null until the kernel says. */
  screen: ScreenCompanions | null;
  /** Voice mode (D-061); null until the kernel says. */
  voice: VoiceStatus | null;
}

export type ChatEvent =
  | { kind: "frame"; frame: Frame }
  | { kind: "status"; status: ConnectionStatus }
  | { kind: "problem"; reason: string }
  /** `text` null: a file went out; its line arrives with turn_start (the kernel words it). */
  | { kind: "sent"; text: string | null }
  | { kind: "regenerating" }
  | { kind: "dismiss_notice" }
  | { kind: "picker"; open: boolean };

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
  pendingCompanion: null,
  beforeRegenerate: null,
  roster: [],
  search: null,
  defaults: null,
  models: null,
  modelStatus: null,
  pickerOpen: false,
  screen: null,
  voice: null,
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
    sentTo: typeof m.meta?.sent_to === "string" ? m.meta.sent_to : undefined,
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

/** A turn that failed: shown inline on the turn, not in the bar (FR-R-5). */
export function turnFailure(state: ChatState): Notice | null {
  const n = state.notice;
  return n && (n.code === "model_failed" || n.code === "model_blocked") ? n : null;
}

/** Everything else the user must see (a refused send, a lost connection): the bar. */
export function barNotice(state: ChatState): Notice | null {
  return turnFailure(state) ? null : state.notice;
}

/** Regenerate and Retry need a saved thread with a line in it (the kernel replaces its last exchange). */
export function canRegenerate(state: ChatState): boolean {
  return canSend(state) && state.thread !== null && state.messages.some((m) => m.role === "user");
}

/** Switching models waits for the reply (the kernel refuses it mid-turn). */
export function canPickModel(state: ChatState): boolean {
  return canSend(state);
}

/** The model the open thread uses: its own pick, else the kernel's default. Never
 * guessed from the load status: the loader may be busy with another thread's model. */
export function currentModelRef(state: ChatState): string | null {
  return state.thread?.model_ref ?? state.defaults?.model_ref ?? state.models?.default_ref ?? null;
}

/** The kernel's model status when it concerns the open thread's model; a load of
 * another thread's model (the kernel is shared) is not this chat's news. */
export function modelStatusHere(state: ChatState): ModelStatus | null {
  const status = state.modelStatus;
  const current = currentModelRef(state);
  if (!status || (current !== null && status.model_ref !== null && status.model_ref !== current)) return null;
  return status;
}

/** The waking-up card is talking: the thinking line waits for it (D-063). */
export function modelLoadingHere(state: ChatState): boolean {
  return modelStatusHere(state)?.state === "loading";
}

/** The effort a turn in the open thread runs with (FR-M-1: shown on the chip). */
export function currentEffort(state: ChatState): string | null {
  return state.thread?.effort ?? state.defaults?.effort ?? null;
}

const NO_EFFORTS: readonly string[] = [];

/** The open thread's model's effort levels (FR-M-8, FR-M-10); empty: no slider. The
 * same array each time for the same list, so a store selector can return it. */
export function currentEfforts(state: ChatState): readonly string[] {
  const ref = currentModelRef(state);
  const row = [...(state.models?.local ?? []), ...(state.models?.api ?? [])].find((r) => r.ref === ref);
  return row?.efforts ?? NO_EFFORTS;
}

/** The level the chip names: none for one the model does not offer, since the turn
 * runs on its default (FR-M-8). Before the model list arrives (it loads with the
 * picker), only a level the thread picked itself. */
export function shownEffort(state: ChatState): string | null {
  if (!state.models) return state.thread?.effort ?? null;
  const effort = currentEffort(state);
  return effort && currentEfforts(state).includes(effort) ? effort : null;
}

/** The chip's name for a model: the picker's label, else the load status's, else the id. */
export function modelLabel(state: ChatState, ref: string | null): string {
  if (!ref) return "Default model";
  const row = state.models ? [...state.models.local, ...state.models.api].find((r) => r.ref === ref) : undefined;
  if (row) return row.label;
  if (state.modelStatus?.model_ref === ref && state.modelStatus.label) return state.modelStatus.label;
  return shortRef(ref);
}

function upsertThread(threads: ThreadInfo[], thread: ThreadInfo): ThreadInfo[] {
  const found = threads.some((t) => t.id === thread.id);
  const next = found ? threads.map((t) => (t.id === thread.id ? thread : t)) : [thread, ...threads];
  return next.filter((t) => !t.archived).sort((a, b) => b.updated_at - a.updated_at);
}

function forCurrentThread(state: ChatState, frame: Frame): boolean {
  return frame.thread === null || state.thread === null || frame.thread === state.thread.id;
}

/** The last exchange as the kernel's last_exchange finds it, dividers skipped: the
 * indices of a user line and its reply, or of a failed turn's lone line. */
export function lastExchange(messages: ChatMessage[]): number[] | null {
  const said = messages.flatMap((m, i) => (m.role === "divider" ? [] : [i]));
  const last = said[said.length - 1];
  if (last === undefined) return null;
  if (messages[last].role === "user") return [last];
  const before = said[said.length - 2];
  return before !== undefined && messages[before].role === "user" ? [before, last] : null;
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
    case "hello": {
      const data = frame.data as { default_model_ref?: string; default_effort?: string | null };
      if (data.default_model_ref === undefined) return state;
      return { ...state, defaults: { model_ref: data.default_model_ref, effort: data.default_effort ?? null } };
    }
    case "thread_opened": {
      const data = frame.data as { thread: ThreadInfo; messages: ThreadMessage[] };
      return {
        ...state,
        thread: data.thread,
        threads: upsertThread(state.threads, data.thread),
        messages: data.messages.map(fromStored),
        beforeRegenerate: null,
        streamRaw: "",
        notice: null,
      };
    }
    case "thread_list": {
      const data = frame.data as { query: string; threads: ThreadInfo[] };
      const threads = data.threads.filter((t) => !t.archived);
      if (data.query.trim()) return { ...state, search: { query: data.query, threads } };
      // The list also carries the open thread's newest title (set from the first message).
      const fresh = state.thread ? data.threads.find((t) => t.id === state.thread?.id) : undefined;
      // Open search results follow renames and deletes too. The list holds only the
      // newest threads, so a missing hit older than all of them may still exist.
      const byId = new Map(threads.map((t) => [t.id, t]));
      const oldest = Math.min(...threads.map((t) => t.updated_at));
      const search = state.search && {
        ...state.search,
        threads: state.search.threads.flatMap((t) => byId.get(t.id) ?? (t.updated_at < oldest ? [t] : [])),
      };
      return { ...state, thread: fresh ?? state.thread, threads, search };
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
      const { user_text, sent_to } = frame.data as { user_text: string; sent_to?: string | null };
      const sentTo = sent_to ?? undefined;
      const last = state.messages[state.messages.length - 1];
      const messages =
        last && last.role === "user" && last.pending && last.text === user_text
          ? [...state.messages.slice(0, -1), { ...last, pending: false, sentTo }]
          : [...state.messages, { key: localKey(), role: "user" as const, text: user_text, speaker: null, sentTo }];
      return { ...state, messages, turn: "thinking", streamRaw: "" };
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
      // A Regenerate that brought nothing back: the kernel kept the old exchange, so does the view.
      if (!reply && state.beforeRegenerate) {
        return { ...state, messages: state.beforeRegenerate, beforeRegenerate: null, turn: "idle", streamRaw: "" };
      }
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
      return { ...state, messages, beforeRegenerate: null, turn: "idle", streamRaw: "" };
    }
    case "model_list":
      return { ...state, models: frame.data as ModelListData };
    case "model_status":
      return { ...state, modelStatus: frame.data as ModelStatus };
    case "screen_companions":
      return { ...state, screen: frame.data as ScreenCompanions };
    case "voice_status":
      return { ...state, voice: frame.data as VoiceStatus };
    case "waifu_state": {
      const data = frame.data as ServerData["waifu_state"];
      const roster = (data.waifus ?? []).map((w) => ({ id: w.id, name: w.name }));
      const found = roster.find((w) => w.id === data.active);
      const pending = data.pending !== data.active ? roster.find((w) => w.id === data.pending) : undefined;
      return { ...state, roster, companion: found ?? null, pendingCompanion: pending ?? null };
    }
    case "surface_status": {
      const { role } = frame.data as ServerData["surface_status"];
      return { ...state, role: role === "observer" ? "observer" : "driver" };
    }
    case "error": {
      const data = frame.data as ServerData["error"];
      const notice: Notice = { code: data.code, text: data.message, actions: data.actions ?? [], detail: data.detail ?? null };
      const failedTurn = data.code === "model_blocked" || data.code === "model_failed";
      // A failed turn still ends with turn_done; turn_running and a screen-companion
      // refusal are not about the turn at all. Anything else refused the send itself.
      const keepsTurn = failedTurn || data.code === "turn_running" || data.code === "vision_unavailable";
      if (!keepsTurn && state.beforeRegenerate) {
        return { ...state, notice, messages: state.beforeRegenerate, beforeRegenerate: null, turn: "idle" };
      }
      return {
        ...state,
        notice,
        messages: failedTurn ? markLastUser(state.messages, { failed: true, pending: false }) : state.messages,
        turn: keepsTurn ? state.turn : "idle",
      };
    }
    default:
      return state;
  }
}

export function reduce(state: ChatState, event: ChatEvent): ChatState {
  switch (event.kind) {
    case "frame":
      return reduceFrame(state, event.frame);
    case "status": {
      const next = { ...state, connection: event.status };
      // A dropped connection ends whatever was streaming; the kernel restarts clean
      // and re-sends its model status on reconnect.
      return event.status === "online"
        ? next
        : { ...next, turn: "idle", streamRaw: "", modelStatus: null, pickerOpen: false, models: null, defaults: null, screen: null, voice: null, pendingCompanion: null, beforeRegenerate: null };
    }
    case "problem":
      return { ...state, notice: { code: "client", text: event.reason, actions: [] } };
    case "sent":
      return {
        ...state,
        messages:
          event.text === null
            ? state.messages
            : [...state.messages, { key: localKey(), role: "user", text: event.text, speaker: null, pending: true }],
        turn: "thinking",
        notice: null,
        pickerOpen: false,
      };
    case "regenerating": {
      // The kernel runs the last exchange again (Regenerate, or Retry after a failure),
      // skipping dividers. The exchange leaves; its line goes last, where the store will
      // have it, and waits for turn_start. The old view is kept in case nothing comes back.
      const drop = lastExchange(state.messages);
      if (!drop) return state;
      const line = { ...state.messages[drop[0]], key: localKey(), pending: true, failed: false };
      const messages = [...state.messages.filter((_, i) => !drop.includes(i)), line];
      return { ...state, messages, beforeRegenerate: state.messages, notice: null, turn: "thinking", streamRaw: "" };
    }
    case "dismiss_notice":
      return { ...state, notice: null };
    case "picker":
      return { ...state, pickerOpen: event.open && canPickModel(state) };
  }
}
