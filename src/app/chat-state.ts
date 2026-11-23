// The chat window's state as a pure reducer (K1-02, D-013): every kernel frame
// and local event goes through `reduce`, so the behaviour is
// testable in Node without a DOM. The Zustand store (store.ts) only wraps it.
// Clients hold no business logic (RULES): this decides what to *show*, never
// what the kernel does.

import {
  NOT_CONNECTED,
  stripTrailingTag,
  type CompanionInfo,
  type DoctorCheck,
  type ErrorCode,
  type Frame,
  type MemoryFact,
  type ModelListData,
  type ModelRow,
  type ModelStatus,
  type SavedScenario,
  type ScreenCompanions,
  type ServerData,
  type SettingsData,
  type ReadAloudStatus,
  type ThreadInfo,
  type ThreadMessage,
  type ThreadMode,
} from "../net/protocol";
import { shortRef } from "./models";

export type ConnectionStatus = "connecting" | "online" | "offline";
/** K1-13: the Settings dialog's sections (FR-SET-1; the rest arrive with their phases). */
export type SettingsSection = "models" | "appearance" | "pet" | "voice" | "screen" | "memory" | "doctor" | "about";
export type TurnPhase = "idle" | "thinking" | "replying";
export type SurfaceRole = "driver" | "observer";

export interface ChatMessage {
  key: string;
  role: "user" | "assistant" | "divider";
  text: string;
  speaker: string | null;
  /** Who spoke it, for her portrait (D-091); null for the user and old rows. */
  speakerId?: string | null;
  /** Stop cut the reply short (FR-C-2). */
  stopped?: boolean;
  /** Sent by this window, not yet acknowledged by `turn_start`. */
  pending?: boolean;
  /** The model call for this user line failed (shown with Retry). */
  failed?: boolean;
  /** An attachment on this line went to this API model (FR-R-7 badge). */
  sentTo?: string;
  /** When it was said, Unix seconds (UI1-07: shown on hover). */
  ts?: number;
  /** The model that wrote a reply (UI1-07: shown on hover). */
  model?: string | null;
  /** The line came from a file: the engine words it, so it cannot be edited. */
  file?: boolean;
  /** A screen remark or a roleplay's opening: no exchange's part, as the kernel's _aside. */
  aside?: boolean;
  /** Its id in the thread store (D-100): what Rewind, Pin, Swipe and New chat from here name. */
  id?: number;
  /** D-100: pinned in a roleplay, so she always keeps it in mind. */
  pinned?: boolean;
  /** D-100: her reply's candidates (Regenerate adds one) and which is shown. */
  swipes?: number;
  swipe?: number;
}

export interface Notice {
  code: ErrorCode | "client";
  text: string;
  actions: ("retry" | "switch_model")[];
  detail?: string | null;
}

/** A short confirmation that fades by itself (UI1-09): "Pinned", "Conversation deleted". */
export interface Toast {
  id: number;
  text: string;
}

/** An in-app question before something that cannot be undone (UI1-09), in place of
 * the browser's own confirm box. The answer goes back through the store. */
export interface ConfirmAsk {
  title: string;
  body?: string;
  /** The button that goes ahead: "Delete", "Remove". */
  action: string;
  danger?: boolean;
}

/** At most this many toasts at once; an older one gives way. */
export const MAX_TOASTS = 3;

export interface Companion {
  id: string;
  name: string;
  /** Her portrait's version stamp, or null for her initial (D-091). */
  portrait?: string | null;
  /** For her profile (D-091, FR-W-9). */
  traits?: string[];
  about?: string | null;
  portraitChosen?: boolean;
  /** D-103: her pet's version stamp and poses; null when she has none. */
  pet?: string | null;
  petPoses?: string[];
  petOwn?: boolean;
}

function toCompanion(w: CompanionInfo): Companion {
  return {
    id: w.id,
    name: w.name,
    portrait: w.portrait ?? null,
    traits: w.traits ?? [],
    about: w.about ?? null,
    portraitChosen: w.portrait_chosen ?? false,
    pet: w.pet ?? null,
    petPoses: w.pet_poses ?? [],
    petOwn: w.pet_own ?? false,
  };
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
  /** The kernel has started the turn (turn_start): it always ends it with turn_done, so
   * an error about something else (a refused rename, say) does not end it here. */
  started: boolean;
  /** D-100: the turn's stored line and reply (`exchange_saved`), until turn_done uses them. */
  saved: ServerData["exchange_saved"] | null;
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
  /** Read aloud (D-097); null until the kernel says. */
  readAloud: ReadAloudStatus | null;
  /** K1-13: the open Settings section; null when Settings is closed. */
  settings: SettingsSection | null;
  /** The Doctor's last report (FR-SET-3); null until asked. */
  doctor: DoctorCheck[] | null;
  /** The remembered facts (FR-MEM-4); null until asked. */
  memory: MemoryFact[] | null;
  /** K1-13b: the editable settings (FR-SET-2); null until asked. */
  prefs: SettingsData | null;
  /** FR-MODE-6: the saved scenario cards, newest first; null until asked. */
  scenarios: SavedScenario[] | null;
  /** FR-MODE-6: the New roleplay dialog is open. */
  roleplayOpen: boolean;
  /** D-091 (FR-W-9): whose profile is open, or null. */
  profile: string | null;
  /** D-101: a roleplay's History or Memory page, or null. */
  story: "history" | "memory" | null;
  /** UI1-09: the toasts on screen, oldest first. */
  toasts: Toast[];
  /** UI1-09: the in-app confirm being asked, or null. */
  confirm: ConfirmAsk | null;
  /** UI1-10: the Ctrl+K palette is open. */
  palette: boolean;
  /** D-104: the last finished reply's emotion tag, a new object per reply (the Stage's mood). */
  mood: { emotion: string | null } | null;
  /** D-104: the conversation as text, or her on the Stage. This window's own. */
  view: "chat" | "stage";
  /** D-103: Create pet's cut sheet, being checked; null otherwise. */
  petDraft: ServerData["pet_draft"] | null;
  /** D-099: the message being read aloud on request (its key), from the click until
   * the last of it has played; null otherwise. */
  reading: string | null;
  /** FR-MODE-6: the dialog's card save. "pending" until its own answer: the
   * `scenarios` frame naming the saved card, or a store error. null: none asked. */
  scenarioSave: ScenarioSave;
  /** FR-MODE-6: the dialog's Start roleplay. "pending" until the kernel answers: the
   * new thread's thread_opened closes the dialog, a refusal keeps it open (and the
   * filled-in card with it) with the reason. null: none asked. */
  roleplayStart: RoleplayStart;
}

/** "lost": the connection dropped before the answer, so the card may or may not be saved. */
export type ScenarioSave = null | "pending" | "failed" | "lost" | { saved: string };

export type RoleplayStart = null | "pending" | { failed: string };

export type ChatEvent =
  | { kind: "frame"; frame: Frame }
  | { kind: "status"; status: ConnectionStatus }
  | { kind: "problem"; reason: string }
  /** `text` null: a file went out; its line arrives with turn_start (the kernel words it). */
  | { kind: "sent"; text: string | null }
  /** `text`: the last line was edited first (UI1-07, D-092). */
  | { kind: "regenerating"; text?: string }
  | { kind: "dismiss_notice" }
  | { kind: "picker"; open: boolean }
  | { kind: "settings"; section: SettingsSection | null }
  | { kind: "roleplay"; open: boolean }
  | { kind: "profile"; id: string | null }
  | { kind: "story"; panel: "history" | "memory" | null }
  | { kind: "toast"; text: string }
  | { kind: "toast_gone"; id: number }
  | { kind: "confirm"; ask: ConfirmAsk | null }
  | { kind: "palette"; open: boolean }
  | { kind: "pet_draft_done" }
  | { kind: "view"; view: "chat" | "stage" }
  | { kind: "reading"; key: string | null }
  /** A card save went out (FR-MODE-6). */
  | { kind: "scenario_saving" }
  /** The dialog's thread_new went out (FR-MODE-6). */
  | { kind: "roleplay_starting" };

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
  started: false,
  saved: null,
  roster: [],
  search: null,
  defaults: null,
  models: null,
  modelStatus: null,
  pickerOpen: false,
  screen: null,
  readAloud: null,
  settings: null,
  doctor: null,
  memory: null,
  prefs: null,
  scenarios: null,
  roleplayOpen: false,
  profile: null,
  story: null,
  toasts: [],
  confirm: null,
  palette: false,
  mood: null,
  view: "chat",
  petDraft: null,
  reading: null,
  scenarioSave: null,
  roleplayStart: null,
};

let localCounter = 0;
let toastCounter = 0;
function localKey(): string {
  localCounter += 1;
  return `l${localCounter}`;
}

export function fromStored(m: ThreadMessage): ChatMessage {
  const swipes = Array.isArray(m.meta?.swipes) ? m.meta.swipes.length : 0;
  return {
    key: `m${m.id}`,
    id: m.id,
    pinned: m.meta?.pinned === true ? true : undefined,
    swipes: swipes > 1 ? swipes : undefined,
    swipe: swipes > 1 && typeof m.meta?.swipe === "number" ? m.meta.swipe : undefined,
    role: m.role,
    text: m.content,
    speaker: m.speaker_name,
    speakerId: m.speaker_waifu_id,
    stopped: m.meta?.stopped === true ? true : undefined,
    sentTo: typeof m.meta?.sent_to === "string" ? m.meta.sent_to : undefined,
    ts: m.ts,
    model: m.role === "assistant" ? m.model_ref : null,
    file: m.meta?.attachment ? true : undefined,
    aside: m.meta?.ambient || m.meta?.opening ? true : undefined,
  };
}

const nowS = () => Date.now() / 1000;

/** UI1-07: a message continues the one before it when the same voice said it, so
 * her face and name show once per run of messages. */
export function startsGroup(messages: ChatMessage[], i: number): boolean {
  const m = messages[i];
  const before = messages[i - 1];
  if (!before || m.role === "divider" || before.role !== m.role) return true;
  return m.role === "assistant" && (before.speakerId ?? before.speaker) !== (m.speakerId ?? m.speaker);
}

/** The key of the user line Edit may change (UI1-07, D-092): the last exchange's,
 * when Regenerate could run and the line is the user's own words. */
export function editableKey(state: ChatState): string | null {
  if (!canRegenerate(state)) return null;
  const exchange = lastExchange(state.messages);
  const line = exchange ? state.messages[exchange[0]] : undefined;
  return line && line.role === "user" && !line.file ? line.key : null;
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

/** D-100: Rewind, Pin, Swipe and New chat from here act on stored messages, between turns. */
export function canActOnMessages(state: ChatState): boolean {
  return canSend(state) && state.thread !== null;
}

/** A new thread (chat or roleplay) waits for the reply and needs the kernel. */
export function canStartThread(state: ChatState): boolean {
  return state.connection === "online" && state.turn === "idle";
}

/** The open thread's mode, from the thread alone (FR-MODE-1); before one opens, chat. */
export function currentMode(state: ChatState): ThreadMode {
  return state.thread?.mode ?? "chat";
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

/** The picker's row for a model, once the list has arrived. */
export function modelRow(state: ChatState, ref: string | null): ModelRow | undefined {
  return ref && state.models ? [...state.models.local, ...state.models.api].find((r) => r.ref === ref) : undefined;
}

/** The chip's name for a model: the picker's label, else the load status's, else the id. */
export function modelLabel(state: ChatState, ref: string | null): string {
  if (!ref) return "Default model";
  const row = modelRow(state, ref);
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

/** The last exchange as the kernel's last_exchange finds it, dividers and asides
 * skipped: the indices of a user line and its reply, or of a failed turn's lone line. */
export function lastExchange(messages: ChatMessage[]): number[] | null {
  const said = messages.flatMap((m, i) => (m.role === "divider" || m.aside ? [] : [i]));
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
        saved: null,
        // A Memory page belongs to the story it was opened in.
        story: state.story === "memory" && state.thread?.id !== data.thread.id ? null : state.story,
        streamRaw: "",
        notice: null,
        // The dialog's roleplay opened: only now does the dialog close (FR-MODE-6).
        ...(state.roleplayStart !== null ? { roleplayOpen: false, roleplayStart: null } : {}),
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
      const { user_text, sent_to, file } = frame.data as ServerData["turn_start"];
      const sentTo = sent_to ?? undefined;
      const last = state.messages[state.messages.length - 1];
      const line = { sentTo, file: file || undefined };
      const messages =
        last && last.role === "user" && last.pending && last.text === user_text
          ? [...state.messages.slice(0, -1), { ...last, pending: false, ...line }]
          : [...state.messages, { key: localKey(), role: "user" as const, text: user_text, speaker: null, ts: nowS(), ...line }];
      return { ...state, messages, turn: "thinking", streamRaw: "", started: true };
    }
    case "token": {
      if (!forCurrentThread(state, frame)) return state;
      const { text } = frame.data as { text: string };
      return { ...state, turn: "replying", streamRaw: state.streamRaw + text };
    }
    case "exchange_saved": {
      if (!forCurrentThread(state, frame)) return state;
      return { ...state, saved: frame.data as ServerData["exchange_saved"] };
    }
    case "message_updated": {
      if (!forCurrentThread(state, frame)) return state;
      const fresh = fromStored((frame.data as ServerData["message_updated"]).message);
      return { ...state, messages: state.messages.map((m) => (m.key === fresh.key ? fresh : m)) };
    }
    case "turn_done": {
      if (!forCurrentThread(state, frame)) return state;
      const { text, stopped, emotion } = frame.data as ServerData["turn_done"];
      const reply = text || visibleStream(state);
      // A Regenerate that brought nothing back: the kernel kept the old exchange, so does the view.
      if (!reply && state.beforeRegenerate) {
        return { ...state, messages: state.beforeRegenerate, beforeRegenerate: null, saved: null, turn: "idle", streamRaw: "" };
      }
      // D-100: the stored line and reply, so every message on screen has its id.
      const saved = state.saved;
      const lineAt = saved ? state.messages.map((m) => m.role).lastIndexOf("user") : -1;
      const withLine =
        saved && lineAt >= 0
          ? state.messages.map((m, i) =>
              i === lineAt ? { ...m, key: `m${saved.user.id}`, id: saved.user.id, pinned: saved.user.meta?.pinned === true || undefined } : m,
            )
          : state.messages;
      const messages = reply
        ? [
            ...withLine,
            saved?.reply ? { ...fromStored(saved.reply), text: reply } : {
              key: localKey(),
              role: "assistant" as const,
              text: reply,
              speaker: state.companion?.name ?? null,
              speakerId: state.companion?.id ?? null,
              stopped: stopped || undefined,
              ts: nowS(),
              // What the kernel stores with it: the thread's model, else the default.
              model: currentModelRef(state),
            },
          ]
        : withLine;
      return { ...state, messages, beforeRegenerate: null, saved: null, started: false, turn: "idle", streamRaw: "", mood: { emotion: emotion ?? null } };
    }
    case "model_list":
      return { ...state, models: frame.data as ModelListData };
    case "model_status":
      return { ...state, modelStatus: frame.data as ModelStatus };
    case "screen_companions":
      return { ...state, screen: frame.data as ScreenCompanions };
    case "read_aloud_status":
      return { ...state, readAloud: frame.data as ReadAloudStatus };
    case "waifu_state": {
      const data = frame.data as ServerData["waifu_state"];
      const roster = (data.waifus ?? []).map(toCompanion);
      const found = roster.find((w) => w.id === data.active);
      const pending = data.pending !== data.active ? roster.find((w) => w.id === data.pending) : undefined;
      return { ...state, roster, companion: found ?? null, pendingCompanion: pending ?? null };
    }
    case "pet_draft":
      return { ...state, petDraft: frame.data as ServerData["pet_draft"] };
    case "waifu_roster": {
      // A new picture (D-091): the same companions, fresh details; who is active stays.
      const roster = ((frame.data as ServerData["waifu_roster"]).waifus ?? []).map(toCompanion);
      const fresh = (c: Companion | null) => (c ? (roster.find((w) => w.id === c.id) ?? c) : null);
      return { ...state, roster, companion: fresh(state.companion), pendingCompanion: fresh(state.pendingCompanion) };
    }
    case "surface_status": {
      const { role } = frame.data as ServerData["surface_status"];
      return { ...state, role: role === "observer" ? "observer" : "driver" };
    }
    case "doctor_report":
      return { ...state, doctor: (frame.data as ServerData["doctor_report"]).checks };
    case "memory_facts":
      return { ...state, memory: (frame.data as ServerData["memory_facts"]).facts };
    case "settings":
      return { ...state, prefs: frame.data as SettingsData };
    case "scenarios": {
      const data = frame.data as ServerData["scenarios"];
      // Only the save's own answer names a card; a list or delete answer is not it.
      const scenarioSave =
        state.scenarioSave === "pending" && typeof data.saved_id === "string" ? { saved: data.saved_id } : state.scenarioSave;
      return { ...state, scenarios: data.cards, scenarioSave };
    }
    case "error": {
      const data = frame.data as ServerData["error"];
      const notice: Notice = { code: data.code, text: data.message, actions: data.actions ?? [], detail: data.detail ?? null };
      const failedTurn = data.code === "model_blocked" || data.code === "model_failed";
      // A failed turn still ends with turn_done; turn_running, a screen-companion refusal
      // and the unpriced-model notice (D-083) do not stop the turn. Anything else refused the send.
      const keepsTurn =
        failedTurn ||
        state.started ||
        data.code === "turn_running" ||
        data.code === "vision_unavailable" ||
        data.code === "price_unknown" ||
        data.code === "picture_unreadable" ||
        data.code === "pin_limit" ||
        data.code === "unknown_message";
      // A store failure answers a pending card save (the kernel sends no list then).
      const scenarioSave = state.scenarioSave === "pending" && data.code === "threads_unavailable" ? "failed" : state.scenarioSave;
      // A refused Start roleplay (turn_running, threads_unavailable): the dialog stays open.
      const roleplayStart = state.roleplayStart === "pending" ? { failed: data.message } : state.roleplayStart;
      if (!keepsTurn && state.beforeRegenerate) {
        return { ...state, notice, scenarioSave, roleplayStart, messages: state.beforeRegenerate, beforeRegenerate: null, turn: "idle" };
      }
      return {
        ...state,
        notice,
        scenarioSave,
        roleplayStart,
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
      if (event.status === "online") return state.notice?.text === NOT_CONNECTED ? { ...next, notice: null } : next;
      // A dropped connection ends whatever was streaming; the kernel restarts clean
      // and re-sends its model status on reconnect. A save or start still waiting will
      // get no answer: the dialog stops waiting (FR-MODE-6).
      const scenarioSave = state.scenarioSave === "pending" ? "lost" : state.scenarioSave;
      const roleplayStart = state.roleplayStart === "pending" ? { failed: "The connection to Kōkyū's engine dropped." } : state.roleplayStart;
      return { ...next, turn: "idle", started: false, streamRaw: "", modelStatus: null, pickerOpen: false, models: null, defaults: null, screen: null, readAloud: null, reading: null, pendingCompanion: null, beforeRegenerate: null, saved: null, scenarioSave, roleplayStart };
    }
    case "problem":
      return { ...state, notice: { code: "client", text: event.reason, actions: [] } };
    case "sent":
      return {
        ...state,
        messages:
          event.text === null
            ? state.messages
            : [...state.messages, { key: localKey(), role: "user", text: event.text, speaker: null, pending: true, ts: nowS() }],
        turn: "thinking",
        started: false,
        notice: null,
        pickerOpen: false,
      };
    case "regenerating": {
      // The kernel runs the last exchange again (Regenerate, or Retry after a failure),
      // skipping dividers. The exchange leaves; its line goes last, where the store will
      // have it, and waits for turn_start. The old view is kept in case nothing comes back.
      const drop = lastExchange(state.messages);
      if (!drop) return state;
      const old = state.messages[drop[0]];
      const line = { ...old, key: localKey(), pending: true, failed: false, text: event.text ?? old.text, ts: event.text ? nowS() : old.ts };
      const messages = [...state.messages.filter((_, i) => !drop.includes(i)), line];
      return { ...state, messages, beforeRegenerate: state.messages, notice: null, turn: "thinking", started: false, streamRaw: "" };
    }
    case "dismiss_notice":
      return { ...state, notice: null };
    case "picker":
      return { ...state, pickerOpen: event.open && canPickModel(state) };
    case "settings":
      return { ...state, settings: event.section, pickerOpen: false };
    case "roleplay":
      // Opens only when a new thread could start; closing always works.
      return { ...state, roleplayOpen: event.open && canStartThread(state), pickerOpen: false, scenarioSave: null, roleplayStart: null };
    case "profile":
      return { ...state, profile: event.id, pickerOpen: false };
    case "story":
      // Roleplay pages only: a chat thread has no History or Memory (D-101).
      return { ...state, story: event.panel && currentMode(state) === "roleplay" ? event.panel : null, pickerOpen: false };
    case "toast": {
      toastCounter += 1;
      return { ...state, toasts: [...state.toasts, { id: toastCounter, text: event.text }].slice(-MAX_TOASTS) };
    }
    case "toast_gone":
      return { ...state, toasts: state.toasts.filter((t) => t.id !== event.id) };
    case "confirm":
      return { ...state, confirm: event.ask };
    case "palette":
      return { ...state, palette: event.open, pickerOpen: event.open ? false : state.pickerOpen };
    case "reading":
      return { ...state, reading: event.key };
    case "pet_draft_done":
      return { ...state, petDraft: null };
    case "view":
      return { ...state, view: event.view };
    case "scenario_saving":
      return { ...state, scenarioSave: "pending" };
    case "roleplay_starting":
      return { ...state, roleplayStart: "pending" };
  }
}
