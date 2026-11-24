// The chat window's store (D-013): Zustand around the pure reducer in
// chat-state.ts, plus the few actions that talk to the kernel. Components read
// state with `useChat(selector)` and call `actions.*`; nothing else touches the
// socket.

import { invoke, isTauri } from "@tauri-apps/api/core";
import { create } from "zustand";

import { KernelSocket } from "../net/kernel";
import type { Effort, Scenario, ServerData, SettingsChange } from "../net/protocol";
import { FILE_MAX, SPEAK_MAX } from "../net/protocol";
import {
  canPickModel,
  canActOnMessages,
  canRegenerate,
  canSend,
  canStartThread,
  initialState,
  reduce,
  type ChatEvent,
  type ChatState,
  type ConfirmAsk,
  type SettingsSection,
} from "./chat-state";
import { UploadProblem, resizeImageToBase64Jpeg } from "./file-upload";
import { PET_PREFS_KEY, parsePetPrefs, type PetPrefs } from "./pet-brain";
import { VoicePlayer } from "./voice";

/** A file ready to send: an image as base64 JPEG, or a text file's content (src/file-upload.ts). */
export interface Attachment {
  filename: string;
  kind: "image" | "text";
  content: string;
}

export const useChat = create<ChatState>(() => initialState);

/** D-103: the pet's show, behaviour and size; this window's own, like Appearance. */
export const usePetPrefs = create<PetPrefs>(() => {
  try {
    return parsePetPrefs(localStorage.getItem(PET_PREFS_KEY));
  } catch {
    return parsePetPrefs(null);
  }
});

export function setPetPrefs(change: Partial<PetPrefs>): void {
  usePetPrefs.setState(change);
  try {
    localStorage.setItem(PET_PREFS_KEY, JSON.stringify(usePetPrefs.getState()));
  } catch {
    // storage blocked: the change holds for this session
  }
}

function dispatch(event: ChatEvent): void {
  useChat.setState((state) => reduce(state, event), true);
}

const voice = new VoicePlayer();

/** The words of the voice clip playing now, or null: the Stage's caption follows it (D-111). */
export function speakingLine(): string | null {
  return voice.line;
}

/** D-099: the engine has sent all of the message being read; it ends once played. */
let readingSent = false;

function readingOver(): void {
  if (useChat.getState().reading !== null) dispatch({ kind: "reading", key: null });
}

voice.onIdle = () => {
  if (readingSent) readingOver();
};

const TYPING_EVERY_MS = 4000;
let lastTypingSent = 0;

/** D-097: the window waiting for a recording's words (one recording at a time). */
type Dictated = ServerData["dictation"];
let dictationWait: ((d: Dictated) => void) | null = null;

function dictationDone(d: Dictated): void {
  const wait = dictationWait;
  dictationWait = null;
  wait?.(d);
}

/** Stop was pressed: `speak` frames sent before the kernel heard it are not played. */
let muted = false;

/** The open in-app confirm's answer (UI1-09); one question at a time. */
let answer: ((yes: boolean) => void) | null = null;

/** Open search results follow a rename or a delete: the kernel answers in order. */
function researchThreads(): void {
  const query = useChat.getState().search?.query;
  if (query) socket.send("thread_search", { query });
}

const socket = new KernelSocket({
  onFrame: (frame) => {
    // After Stop, clips already on their way are dropped until the next thing she is asked to say.
    if (frame.type === "speak" && !muted) voice.enqueue(frame.data as ServerData["speak"]);
    if (frame.type === "spoken" && (frame.data as ServerData["spoken"]).ref === useChat.getState().reading) {
      readingSent = true;
      if (voice.idle) readingOver(); // nothing to hear (code only, or her voice did not start)
    }
    if (frame.type === "dictation") dictationDone(frame.data as Dictated);
    dispatch({ kind: "frame", frame });
  },
  onStatus: (status) => {
    if (status !== "online") {
      voice.stop();
      if (dictationWait) dictationDone({ text: "", error: "The connection to Kōkyū's engine dropped." });
    }
    dispatch({ kind: "status", status });
    // The New roleplay dialog stayed open across a reconnect: its card list may be stale.
    if (status === "online" && useChat.getState().roleplayOpen) socket.send("scenario_list", {});
    // Settings stayed open across it too: its section asks again (models were cleared).
    const section = useChat.getState().settings;
    if (status === "online" && section) actions.openSettings(section);
  },
  onProblem: (reason) => dispatch({ kind: "problem", reason }),
});

export const actions = {
  connect(): void {
    socket.connect();
  },

  /** The banner's Reconnect (D-082): in the desktop app the shell starts the engine
   * again if it has stopped; then the socket tries at once. */
  async reconnect(): Promise<void> {
    if (isTauri()) {
      try {
        await invoke<boolean>("restart_kernel");
      } catch {
        // the retry below still runs; the banner stays until the engine answers
      }
    }
    socket.reconnectNow();
  },

  /** Sends a line. Returns false (and changes nothing) when it can't be sent now. */
  send(text: string): boolean {
    const line = text.trim();
    if (!line || !canSend(useChat.getState())) return false;
    if (!socket.send("send", { text: line })) return false;
    muted = false;
    voice.stop();
    dispatch({ kind: "sent", text: line });
    return true;
  },

  /** A file from the `＋` tray, a paste or a drop (FR-C-3), with the typed text as its
   * caption. The kernel describes an image (or reads a text file) and runs the turn. */
  sendFile(file: Attachment, caption: string): boolean {
    if (!canSend(useChat.getState())) return false;
    if (!socket.send("send_file", { ...file, caption: caption.trim() })) return false;
    muted = false;
    voice.stop();
    dispatch({ kind: "sent", text: null });
    return true;
  },

  /** Stop: halts generation and the voice; the partial reply is kept (FR-C-2). */
  stop(): void {
    muted = true;
    voice.stop();
    socket.send("stop", {});
  },

  /** Regenerate the last reply, or Retry a failed turn (FR-C-9): the kernel replaces
   * the last exchange, so the user line is not stored twice. */
  regenerate(): void {
    const state = useChat.getState();
    if (!canRegenerate(state) || !socket.send("regenerate", {})) return;
    muted = false;
    voice.stop();
    dispatch({ kind: "regenerating" });
  },

  /** Edit and resend the last line (UI1-07, D-092): the kernel replaces the last
   * exchange with the new words and runs it. Returns false when it can't run now. */
  resend(text: string): boolean {
    const line = text.trim();
    if (!line || !canRegenerate(useChat.getState()) || !socket.send("regenerate", { text: line })) return false;
    muted = false;
    voice.stop();
    dispatch({ kind: "regenerating", text: line });
    return true;
  },

  // ── a message's ⋯ card and swipes (D-100) ─────────────────────────────

  copyMessage(text: string): void {
    navigator.clipboard.writeText(text).then(
      () => dispatch({ kind: "toast", text: "Copied" }),
      () => dispatch({ kind: "toast", text: "Couldn't copy" }),
    );
  },

  /** Rewind to here: every later message goes, after the user says yes. */
  async rewind(id: number): Promise<void> {
    const yes = await actions.confirm({
      title: "Rewind to here?",
      body: "Every message after this one is deleted from this PC. This cannot be undone.",
      action: "Rewind",
      danger: true,
    });
    if (yes && canActOnMessages(useChat.getState())) socket.send("message_rewind", { id });
  },

  /** A new conversation of the same kind with the messages up to this one. */
  branchFrom(id: number): void {
    if (canActOnMessages(useChat.getState())) socket.send("message_branch", { id });
  },

  /** Roleplay only: a pinned message stays in her prompt for the whole story. */
  pinMessage(id: number, on: boolean): void {
    if (canActOnMessages(useChat.getState())) socket.send("message_pin", { id, on });
  },

  /** Another of her latest reply's candidates; past the last one, a new one. */
  swipe(id: number, to: number, count: number): void {
    if (to >= count) actions.regenerate();
    else if (to >= 0 && canActOnMessages(useChat.getState())) socket.send("message_swipe", { id, to });
  },

  dismissNotice(): void {
    dispatch({ kind: "dismiss_notice" });
  },

  newThread(): void {
    if (!canStartThread(useChat.getState())) return;
    socket.send("thread_new", {});
  },

  // ── roleplay (K1c-08; FR-MODE-6) ────────────────────────────────────

  /** A roleplay thread from a card, or blank (null). The mode is fixed for the
   * thread's life; the kernel opens it and answers with thread_opened, which closes
   * the dialog. A refusal leaves the dialog open with the card still filled in. */
  newRoleplay(scenario: Scenario | null): boolean {
    const state = useChat.getState();
    if (!canStartThread(state) || state.roleplayStart === "pending") return false;
    if (!socket.send("thread_new", { mode: "roleplay", scenario })) return false;
    dispatch({ kind: "roleplay_starting" });
    return true;
  },

  /** The New roleplay dialog; it asks the kernel for the saved cards each time. */
  openRoleplay(): void {
    if (!canStartThread(useChat.getState())) return;
    dispatch({ kind: "roleplay", open: true });
    socket.send("scenario_list", {});
  },

  closeRoleplay(): void {
    dispatch({ kind: "roleplay", open: false });
  },

  /** Saves a card (with `id`, replaces that saved card); the kernel answers with the fresh list. */
  saveScenario(card: Scenario, id?: string): boolean {
    if (!socket.send("scenario_save", id ? { id, card } : { card })) return false;
    dispatch({ kind: "scenario_saving" });
    return true;
  },

  /** Threads started from the card stay as they are. */
  deleteScenario(id: string): boolean {
    return socket.send("scenario_delete", { id });
  },

  /** Temp Chat for the open thread (FR-MEM-5); the kernel saves it and answers with thread_updated. */
  setTemp(on: boolean): void {
    socket.send("set_temp", { on });
  },

  openThread(id: string): void {
    const state = useChat.getState();
    if (state.turn !== "idle" || state.thread?.id === id) return;
    voice.stop();
    socket.send("thread_open", { id });
  },

  // ── the sidebar (K1-03) ─────────────────────────────────────────────

  /** Full-text search over titles and messages; an empty query shows the history again. */
  searchThreads(query: string): void {
    if (query.trim()) socket.send("thread_search", { query: query.trim() });
  },

  renameThread(id: string, title: string): void {
    if (title.trim()) socket.send("thread_rename", { id, title: title.trim() });
    researchThreads();
  },

  deleteThread(id: string): void {
    if (useChat.getState().turn !== "idle") return;
    if (socket.send("thread_delete", { id })) dispatch({ kind: "toast", text: "Conversation deleted" });
    researchThreads();
  },

  /** UI1-09 (D-094): pinned threads stay at the top of the history list. */
  pinThread(id: string, on: boolean): void {
    if (socket.send("thread_pin", { id, on })) dispatch({ kind: "toast", text: on ? "Pinned" : "Unpinned" });
    researchThreads();
  },

  // ── the Ctrl+K palette (UI1-10) ─────────────────────────────────────

  openPalette(): void {
    dispatch({ kind: "palette", open: true });
  },

  closePalette(): void {
    dispatch({ kind: "palette", open: false });
  },

  // ── toasts and confirms (UI1-09) ────────────────────────────────────

  toast(text: string): void {
    dispatch({ kind: "toast", text });
  },

  dismissToast(id: number): void {
    dispatch({ kind: "toast_gone", id });
  },

  /** Asks in the window (never the browser's confirm box); resolves true to go ahead.
   * A new question answers an open one with "no". */
  confirm(ask: ConfirmAsk): Promise<boolean> {
    answer?.(false);
    dispatch({ kind: "confirm", ask });
    return new Promise((resolve) => {
      answer = resolve;
    });
  },

  answerConfirm(yes: boolean): void {
    const resolve = answer;
    answer = null;
    dispatch({ kind: "confirm", ask: null });
    resolve?.(yes);
  },

  // ── her profile (D-091, FR-W-9) ─────────────────────────────────────

  openProfile(id: string): void {
    dispatch({ kind: "profile", id });
  },

  closeProfile(): void {
    dispatch({ kind: "profile", id: null });
  },

  // ── a roleplay's tray (D-101) ───────────────────────────────────────

  openStory(panel: "history" | "memory"): void {
    dispatch({ kind: "story", panel });
  },

  closeStory(): void {
    dispatch({ kind: "story", panel: null });
  },

  /** The roleplay's Memory box, kept by the engine with the thread. */
  saveStoryNote(text: string): void {
    if (canActOnMessages(useChat.getState())) socket.send("thread_note", { text });
  },

  /** A new roleplay from the open one's card, with her: her greeting starts it again. */
  newStory(): void {
    const scenario = useChat.getState().thread?.scenario ?? null;
    actions.newRoleplay(scenario && Object.keys(scenario).length > 0 ? scenario : null);
  },

  /** The profile's Chat button: a new chat that starts with her. The open chat gets
   * no divider, since nobody switched in it. */
  chatWith(id: string): void {
    if (!canStartThread(useChat.getState())) return;
    if (socket.send("thread_new", { waifu_id: id })) dispatch({ kind: "profile", id: null });
  },

  /** A picture the user picked for her; the engine cuts it square. A file the engine
   * cannot read comes back as a notice. */
  async choosePortrait(id: string, file: File): Promise<void> {
    let image: string;
    try {
      image = await resizeImageToBase64Jpeg(file, "image/png");
    } catch (e) {
      dispatch({ kind: "problem", reason: e instanceof UploadProblem ? e.message : "That file is not a picture Kōkyū can read. Try a PNG or JPEG." });
      return;
    }
    socket.send("set_portrait", { waifu_id: id, image_b64: image });
  },

  /** Create pet (D-103): the sheet goes to the engine, which cuts it and answers with
   * `pet_draft`. PNG keeps its transparency. */
  async sendPetSheet(id: string, file: File): Promise<void> {
    let image: string;
    try {
      image = await resizeImageToBase64Jpeg(file, "image/png", 2048);   // a sheet's 12 cells need more pixels than a photo
    } catch (e) {
      dispatch({ kind: "problem", reason: e instanceof UploadProblem ? e.message : "That file is not a picture Kōkyū can read. Use a PNG of the pose sheet." });
      return;
    }
    if (image.length > FILE_MAX) {
      dispatch({ kind: "problem", reason: "That sheet is too detailed to send. Save it as a PNG with a plain background and try again." });
      return;
    }
    socket.send("pet_sheet", { waifu_id: id, image_b64: image });
  },

  savePet(id: string, labels: (string | null)[]): void {
    socket.send("pet_save", { waifu_id: id, labels });
    dispatch({ kind: "pet_draft_done" });
  },

  /** D-104: Chat or Stage for this window. */
  setView(view: "chat" | "stage"): void {
    dispatch({ kind: "view", view });
  },

  dropPetDraft(): void {
    dispatch({ kind: "pet_draft_done" });
  },

  removePet(id: string): void {
    socket.send("pet_remove", { waifu_id: id });
  },

  /** Back to the face from her model. */
  resetPortrait(id: string): void {
    socket.send("set_portrait", { waifu_id: id, image_b64: null });
  },

  /** Persona and voice only; model, memory and tools stay (FR-W-3). Mid-reply it waits for the reply. */
  switchWaifu(id: string): void {
    const state = useChat.getState();
    // Mid-reply a click back to her undoes a switch still waiting for the reply.
    if (state.companion?.id === id && state.turn === "idle") return;
    socket.send("switch_waifu", { id });
  },

  /** FR-SC-5: tells the kernel the user is typing (OCR watch keeps quiet); at most every few seconds. */
  typing(): void {
    const now = Date.now();
    if (now - lastTypingSent < TYPING_EVERY_MS) return;
    lastTypingSent = now;
    socket.send("typing", {});
  },

  /** Task Guide (with the task in the user's words) or OCR watch, on or off (FR-SC-1, 4). */
  setScreenCompanion(mode: "task_guide" | "ocr_watch", on: boolean, task = ""): void {
    socket.send("screen_companion", task ? { mode, on, task } : { mode, on });
  },

  /** D-099: read one of her messages aloud now, in her voice, Read aloud on or off.
   * The same message again stops it. */
  /** Stops a message being read on request, if one is (D-099). */
  stopReading(): void {
    const reading = useChat.getState().reading;
    if (reading !== null) actions.readMessage(reading, "", null);
  },

  readMessage(key: string, text: string, speakerId: string | null): void {
    const reading = useChat.getState().reading;
    voice.stop();
    if (reading === key) {
      socket.send("speak_stop", {});
      readingSent = false;
      readingOver();
      return;
    }
    if (!socket.send("speak_message", { ref: key, text: text.slice(0, SPEAK_MAX), speaker_id: speakerId })) return;
    muted = false;
    readingSent = false;
    dispatch({ kind: "reading", key });
  },

  /** Dictation began recording (D-097): the engine loads speech-to-text meanwhile. */
  dictateStart(): void {
    socket.send("dictate_start", {});
  },

  /** A recording to write down (D-097). Resolves with the words for the input box, or
   * why there are none; never sends anything to her. */
  dictate(audio_b64: string, mime: string): Promise<Dictated> {
    if (!socket.send("dictate", { audio_b64, mime })) {
      return Promise.resolve({ text: "", error: "Kōkyū's engine is not connected." });
    }
    if (dictationWait) dictationDone({ text: "", error: null }); // a stale wait gives way
    return new Promise((resolve) => {
      dictationWait = resolve;
    });
  },

  /** Read aloud on or off (D-097): kept by the engine; her voice starts while it is on.
   * Off silences her at once. */
  setReadAloud(on: boolean): void {
    if (!on) voice.stop();
    socket.send("read_aloud", { on });
  },

  // ── the model chip (K1-10) ──────────────────────────────────────────

  /** Opens the picker and asks the kernel what can be picked (fresh every time:
   * a model pulled in Ollama a minute ago shows up). */
  openPicker(): void {
    if (!canPickModel(useChat.getState())) return;
    dispatch({ kind: "picker", open: true });
    socket.send("model_list", {});
  },

  closePicker(): void {
    dispatch({ kind: "picker", open: false });
  },

  /** K1-13: Settings opens on a section; each asks the kernel for fresh data. */
  openSettings(section: SettingsSection = "models"): void {
    dispatch({ kind: "settings", section });
    if (section === "doctor") socket.send("doctor", {});
    if (section === "memory") socket.send("memory_list", {});
    if (section === "models") socket.send("model_list", {});
    if (section === "models" || section === "screen") socket.send("settings_get", {});
  },

  /** K1-13b (FR-SET-2): saved to settings.json and applied at once; every window gets the result. */
  saveSettings(change: SettingsChange): boolean {
    return socket.send("settings_set", change);
  },

  closeSettings(): void {
    dispatch({ kind: "settings", section: null });
  },

  runDoctor(): boolean {
    return socket.send("doctor", {});
  },

  /** FR-MEM-4: the kernel supersedes the fact with the new wording (nothing is deleted). */
  correctFact(id: number, text: string): boolean {
    return socket.send("memory_edit", { id, text });
  },

  forgetFact(id: number): boolean {
    return socket.send("memory_forget", { id });
  },

  restoreFact(id: number): boolean {
    return socket.send("memory_restore", { id });
  },

  /** Re-fetches the API catalog (FR-M-4). */
  refreshModels(): void {
    socket.send("model_list", { refresh: true });
  },

  /** Picking a row is the whole action (FR-M-2): the thread switches and the kernel loads it. */
  setModel(ref: string): boolean {
    const state = useChat.getState();
    if (!canPickModel(state)) return false;
    dispatch({ kind: "picker", open: false });
    if (ref === (state.thread?.model_ref ?? null)) return true;
    return socket.send("set_model", { model_ref: ref });
  },

  /** The open thread's effort, from the next turn on (FR-M-8; per model, FR-M-11). */
  setEffort(effort: Effort): boolean {
    if (!useChat.getState().thread) return false;
    return socket.send("set_effort", { effort });
  },

  /** D-098: a model's Chat memory, for every thread. The model in memory reloads with it. */
  setContext(ref: string, tokens: number | null): boolean {
    return socket.send("set_context", { ref, tokens });
  },

  /** Try again after a failed load. */
  /** K1-09b: *Unload X* on the graphics-memory card; the kernel then tries the load again. */
  unloadModel(ref: string): void {
    socket.send("model_unload", { ref });
  },

  retryLoad(): void {
    socket.send("model_load", {});
  },
};
