// The chat window's store (D-013): Zustand around the pure reducer in
// chat-state.ts, plus the few actions that talk to the kernel. Components read
// state with `useChat(selector)` and call `actions.*`; nothing else touches the
// socket.

import { invoke, isTauri } from "@tauri-apps/api/core";
import { create } from "zustand";

import { KernelSocket } from "../net/kernel";
import type { Effort, Scenario, ServerData, SettingsChange } from "../net/protocol";
import {
  canPickModel,
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
import { resizeImageToBase64Jpeg } from "./file-upload";
import { VoicePlayer } from "./voice";

/** A file ready to send: an image as base64 JPEG, or a text file's content (src/file-upload.ts). */
export interface Attachment {
  filename: string;
  kind: "image" | "text";
  content: string;
}

export const useChat = create<ChatState>(() => initialState);

function dispatch(event: ChatEvent): void {
  useChat.setState((state) => reduce(state, event), true);
}

const voice = new VoicePlayer();

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

/** The open in-app confirm's answer (UI1-09); one question at a time. */
let answer: ((yes: boolean) => void) | null = null;

/** Open search results follow a rename or a delete: the kernel answers in order. */
function researchThreads(): void {
  const query = useChat.getState().search?.query;
  if (query) socket.send("thread_search", { query });
}

const socket = new KernelSocket({
  onFrame: (frame) => {
    if (frame.type === "speak") voice.enqueue(frame.data as ServerData["speak"]);
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
    voice.stop();
    dispatch({ kind: "sent", text: line });
    return true;
  },

  /** A file from the `＋` tray, a paste or a drop (FR-C-3), with the typed text as its
   * caption. The kernel describes an image (or reads a text file) and runs the turn. */
  sendFile(file: Attachment, caption: string): boolean {
    if (!canSend(useChat.getState())) return false;
    if (!socket.send("send_file", { ...file, caption: caption.trim() })) return false;
    voice.stop();
    dispatch({ kind: "sent", text: null });
    return true;
  },

  /** Stop: halts generation and the voice; the partial reply is kept (FR-C-2). */
  stop(): void {
    voice.stop();
    socket.send("stop", {});
  },

  /** Regenerate the last reply, or Retry a failed turn (FR-C-9): the kernel replaces
   * the last exchange, so the user line is not stored twice. */
  regenerate(): void {
    const state = useChat.getState();
    if (!canRegenerate(state) || !socket.send("regenerate", {})) return;
    voice.stop();
    dispatch({ kind: "regenerating" });
  },

  /** Edit and resend the last line (UI1-07, D-092): the kernel replaces the last
   * exchange with the new words and runs it. Returns false when it can't run now. */
  resend(text: string): boolean {
    const line = text.trim();
    if (!line || !canRegenerate(useChat.getState()) || !socket.send("regenerate", { text: line })) return false;
    voice.stop();
    dispatch({ kind: "regenerating", text: line });
    return true;
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
    } catch {
      dispatch({ kind: "problem", reason: "That file is not a picture Kōkyū can read. Try a PNG or JPEG." });
      return;
    }
    socket.send("set_portrait", { waifu_id: id, image_b64: image });
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
  readMessage(key: string, text: string, speakerId: string | null): void {
    const reading = useChat.getState().reading;
    voice.stop();
    if (reading === key) {
      socket.send("speak_stop", {});
      readingSent = false;
      readingOver();
      return;
    }
    if (!socket.send("speak_message", { ref: key, text, speaker_id: speakerId })) return;
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
