// The chat window's store (D-013): Zustand around the pure reducer in
// chat-state.ts, plus the few actions that talk to the kernel. Components read
// state with `useChat(selector)` and call `actions.*`; nothing else touches the
// socket.

import { create } from "zustand";

import { KernelSocket } from "../net/kernel";
import { canPickModel, canSend, initialState, reduce, type ChatEvent, type ChatState } from "./chat-state";
import { VoicePlayer, type SpeakClip } from "./voice";

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

const TYPING_EVERY_MS = 4000;
let lastTypingSent = 0;

const socket = new KernelSocket({
  onFrame: (frame) => dispatch({ kind: "frame", frame }),
  onLegacy: (msg) => {
    if (msg.type === "speak") voice.enqueue(msg as unknown as SpeakClip);
    else if (msg.type === "barge_in") voice.stop();
    dispatch({ kind: "legacy", msg });
  },
  onStatus: (status) => {
    if (status !== "online") voice.stop();
    dispatch({ kind: "status", status });
  },
  onProblem: (reason) => dispatch({ kind: "problem", reason }),
});

export const actions = {
  connect(): void {
    socket.connect();
  },

  /** Sends a line. Returns false (and changes nothing) when it can't be sent now. */
  send(text: string): boolean {
    const line = text.trim();
    if (!line || !canSend(useChat.getState())) return false;
    if (!socket.sendLegacy({ type: "user_text", text: line })) return false;
    voice.stop();
    dispatch({ kind: "sent", text: line });
    return true;
  },

  /** A file from the `＋` tray, a paste or a drop (FR-C-3), with the typed text as its
   * caption. The kernel describes an image (or reads a text file) and runs the turn. */
  sendFile(file: Attachment, caption: string): boolean {
    if (!canSend(useChat.getState())) return false;
    if (!socket.sendLegacy({ type: "user_file", ...file, caption: caption.trim() })) return false;
    voice.stop();
    dispatch({ kind: "sent", text: null });
    return true;
  },

  /** Stop: halts generation and the voice; the partial reply is kept (FR-C-2). */
  stop(): void {
    voice.stop();
    socket.sendLegacy({ type: "stop" });
  },

  /** Regenerate the last reply, or Retry a failed turn (FR-C-9): the kernel replaces
   * the last exchange, so the user line is not stored twice. */
  regenerate(): void {
    const state = useChat.getState();
    if (!canSend(state) || !state.messages.some((m) => m.role === "user")) return;
    if (!socket.send("regenerate", {})) return;
    voice.stop();
    dispatch({ kind: "regenerating" });
  },

  dismissNotice(): void {
    dispatch({ kind: "dismiss_notice" });
  },

  newThread(): void {
    if (useChat.getState().turn !== "idle") return;
    socket.send("thread_new", {});
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
  },

  deleteThread(id: string): void {
    if (useChat.getState().turn !== "idle") return;
    socket.send("thread_delete", { id });
  },

  /** Persona and voice only; model, memory and tools stay (FR-W-3). Mid-reply it waits for the reply. */
  switchWaifu(id: string): void {
    if (useChat.getState().companion?.id === id) return;
    socket.sendLegacy({ type: "switch_waifu", id });
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

  /** Try again after a failed load. */
  retryLoad(): void {
    socket.send("model_load", {});
  },
};
