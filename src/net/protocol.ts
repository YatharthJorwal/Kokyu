// Typed WebSocket protocol, version 1 -- the TypeScript mirror of
// KASANE/protocol/__init__.py (K1-00b; ARCHITECTURE §5.3). A kernel test reads
// the three lists below and fails if they drift from the Python ones.
//
// Every message, both ways, travels in one envelope (D-062):
//   { v: 1, type, id, thread, data }
// Anything else is a problem the window reports, never a message it acts on.

export const PROTOCOL_VERSION = 1;

export const CLIENT_TYPES = [
  "hello",
  "send",
  "send_file",
  "stop",
  "switch_waifu",
  "set_portrait",
  "set_temp",
  "camera_frame",
  "thread_list",
  "thread_search",
  "thread_new",
  "thread_open",
  "thread_delete",
  "thread_rename",
  "thread_pin",
  "set_model",
  "set_effort",
  "model_list",
  "model_load",
  "model_unload",
  "regenerate",
  "screen_companion",
  "typing",
  "voice_mode",
  "doctor",
  "memory_list",
  "memory_edit",
  "memory_forget",
  "memory_restore",
  "settings_get",
  "settings_set",
  "scenario_list",
  "scenario_save",
  "scenario_delete",
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
  "voice_status",
  "waifu_state",
  "waifu_roster",
  "surface_status",
  "speak",
  "camera_request",
  "doctor_report",
  "memory_facts",
  "settings",
  "scenarios",
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
  "observer",
  "price_unknown",
  "picture_unreadable",
] as const;

/** D-061: voice mode (replies spoken; the mic in K2). It starts only when turned on. */
export interface VoiceStatus {
  on: boolean;
  state: "idle" | "loading" | "ready" | "failed";
  message: string | null;
  elapsed_s: number | null;
}

/** K1-05b (FR-SC-2): what is watching the screen right now. */
export interface ScreenCompanions {
  task_guide: { on: boolean; task: string | null };
  ocr_watch: { on: boolean };
}

/** FR-S-1: an installed companion as the kernel lists her. */
export interface CompanionInfo {
  id: string;
  name: string;
  premade?: boolean;
  traits?: string[];
  /** Her profile's brief (D-091, FR-W-9). */
  about?: string | null;
  /** A version stamp for `/waifus/<id>/portrait`, or null (D-091, FR-W-8). */
  portrait?: string | null;
  /** The picture is one the user chose, not the model's face. */
  portrait_chosen?: boolean;
}

export type ClientType = (typeof CLIENT_TYPES)[number];
export type ServerType = (typeof SERVER_TYPES)[number];
export type ErrorCode = (typeof ERROR_CODES)[number];

/** What kind of conversation a thread is, fixed when it is created (FR-MODE-1). */
export type ThreadMode = "chat" | "roleplay";

/** A roleplay's scenario card (FR-MODE-6). Every field may be left out or empty. */
export interface Scenario {
  title?: string;
  setting?: string;
  user_role?: string;
  her_role?: string;
  rules?: string;
  opening?: string;
}

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
  mode: ThreadMode;
  /** The filled-in fields of the card; empty for chat threads and blank roleplays. */
  scenario: Scenario;
  /** Kept at the top of the history list (UI1-09, D-094); absent from an older engine. */
  pinned?: boolean;
}

/** A saved scenario card (FR-MODE-6): `title` is the card's own, else derived from its setting. */
export interface SavedScenario {
  id: string;
  title: string;
  card: Scenario;
  updated_at: number | null;
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
  /** The short name the kernel computed (FR-M-12, D-084). */
  label: string;
  /** The backend's exact id (or a llama.cpp preset's file), shown muted on hover. */
  full?: string;
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
  /** No catalog price while a cap is on: it runs, not counted against the cap (D-083). */
  unpriced?: boolean;
  tags?: string[];
  /** API rows: the vendor the model is listed under (FR-M-4). */
  group?: string | null;
  /** The effort slider's detents, lowest first; empty = no slider (FR-M-8, FR-M-10). */
  efforts?: Effort[];
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
  /** The one active API endpoint and where its key came from (D-059). Never the key. */
  api_provider?: { id: string; label: string; key: "app" | "developer" | null } | null;
  /** Endpoints a key can be saved for (D-059). */
  api_presets?: { id: string; label: string }[];
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
  /** K1-09b (SPEC §5): on a load refused for graphics memory, the models the card may unload. */
  unload?: { ref: string; label: string }[];
}

export interface ServerData {
  /** The kernel's defaults for a thread with no choice of its own (K1-10). */
  hello: { protocol: number; kernel: string; default_model_ref?: string; default_effort?: string | null };
  thread_opened: { thread: ThreadInfo; messages: ThreadMessage[] };
  thread_list: { query: string; threads: ThreadInfo[] };
  thread_message: { message: ThreadMessage };
  thread_updated: { thread: ThreadInfo };
  /** `file`: the line came from a file (it cannot be edited, D-092). */
  turn_start: { user_text: string; sent_to?: string | null; file?: boolean };
  token: { text: string };
  turn_done: { text: string; stopped: boolean; emotion?: string | null };
  error: {
    code: ErrorCode;
    message: string;
    reply_to: string | null;
    reason?: string;
    /** What the provider itself said (FR-R-5), for a "Details" disclosure. */
    detail?: string | null;
    model_ref?: string | null;
    actions?: ("retry" | "switch_model")[];
  };
  model_list: ModelListData;
  model_status: ModelStatus;
  screen_companions: ScreenCompanions;
  voice_status: VoiceStatus;
  waifu_state: { active: string | null; waifus: CompanionInfo[]; problems: string[]; pending: string | null };
  /** D-091: only the roster changed (a new picture); active and pending stay. */
  waifu_roster: { waifus: CompanionInfo[] };
  surface_status: { role: "driver" | "observer" };
  /** One spoken clause (FR-V-2); `audio_b64` is empty when the voice backend is down. */
  speak: { text: string; audio_b64: string; mime: string };
  camera_request: Record<string, never>;
  doctor_report: { checks: DoctorCheck[] };
  memory_facts: { facts: MemoryFact[] };
  settings: SettingsData;
  /** FR-MODE-6: every saved card, the most recently saved first. The answer to a
   * scenario_save also names the card it saved. */
  scenarios: { cards: SavedScenario[]; saved_id?: string };
}

/** K1-13b (FR-SET-2, D-070): the editable settings in effect. `saved` names the ones
 * set in settings.json (the rest come from config.yaml); `problem` says why the
 * last change was refused. */
export interface SettingsData {
  ollama_url: string;
  budget: BudgetCaps;
  custom_api: { id: string; label: string; base_url: string } | null;
  screen: { task_guide: boolean; ocr_watch: boolean };
  saved: ("ollama_url" | "budget" | "custom_api" | "screen")[];
  file: string;
  problem: string | null;
}

/** A null cap is no cap (FR-M-7). */
export interface BudgetCaps {
  enabled: boolean;
  hourly_usd: number | null;
  daily_usd: number | null;
  monthly_usd: number | null;
}

/** Only the keys sent change; `ollama_url` "" and `custom_api` null go back to config.yaml. */
export interface SettingsChange {
  ollama_url?: string;
  budget?: BudgetCaps;
  custom_api?: { label: string; base_url: string } | null;
  screen?: Partial<SettingsData["screen"]>;
}

/** K1-13 (FR-SET-3): one component's state and how to fix it. */
export interface DoctorCheck {
  id: string;
  label: string;
  state: "ok" | "warn" | "fail" | "off";
  detail: string;
  hint: string | null;
}

/** K1-13 (FR-MEM-4): a remembered fact; forgotten ones can be restored. */
export interface MemoryFact {
  id: number;
  content: string;
  source: string;
  pinned: boolean;
  created_ts: number;
  forgotten: boolean;
}

export interface ClientData {
  hello: { client: "main" | "pet" | "dev"; protocol: number };
  send: { text: string };
  send_file: { filename: string; kind: "image" | "text"; content: string; caption: string };
  stop: Record<string, never>;
  switch_waifu: { id: string };
  /** D-091: bare base64 (already scaled down), or null for the model's face. */
  set_portrait: { waifu_id: string; image_b64: string | null };
  set_temp: { on: boolean };
  camera_frame: { image_b64: string | null };
  thread_list: Record<string, never>;
  thread_search: { query: string };
  /** `waifu_id`: her profile's Chat button; the new thread starts with her (D-091). */
  thread_new: { mode?: ThreadMode; scenario?: Scenario | null; waifu_id?: string };
  thread_open: { id: string };
  thread_delete: { id: string };
  thread_rename: { id: string; title: string };
  /** UI1-09 (D-094): pinned threads stay at the top of the history list. */
  thread_pin: { id: string; on: boolean };
  set_model: { model_ref: string | null };
  set_effort: { effort: Effort | null };
  model_list: { refresh?: boolean };
  model_load: Record<string, never>;
  model_unload: { ref: string };
  /** With `text`, the last user line is edited first (UI1-07, D-092). */
  regenerate: { text?: string };
  screen_companion: { mode: "task_guide" | "ocr_watch"; on: boolean; task?: string };
  typing: Record<string, never>;
  voice_mode: { on: boolean };
  doctor: Record<string, never>;
  memory_list: Record<string, never>;
  memory_edit: { id: number; text: string };
  memory_forget: { id: number };
  memory_restore: { id: number };
  settings_get: Record<string, never>;
  settings_set: SettingsChange;
  scenario_list: Record<string, never>;
  /** With `id`, replaces that saved card; without, saves a new one. */
  scenario_save: { id?: string; card: Scenario };
  scenario_delete: { id: string };
}

export type Effort = "off" | "low" | "medium" | "high" | "max";

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

export type ParseResult = { kind: "frame"; frame: Frame } | { kind: "error"; reason: string };

/** A valid v1 frame, or the problem with the message. */
export function parseFrame(raw: unknown): ParseResult {
  if (typeof raw !== "object" || raw === null || !("v" in raw)) {
    return { kind: "error", reason: "the kernel sent a message without a protocol version" };
  }
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
