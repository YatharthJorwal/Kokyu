// The chat window's store (D-013): Zustand around the pure reducer in
// chat-state.ts, plus the few actions that talk to the kernel. Components read
// state with `useChat(selector)` and call `actions.*`; nothing else touches the
// socket.

import { create } from "zustand";

import { KernelSocket } from "../net/kernel";
import { canSend, initialState, reduce, type ChatEvent, type ChatState } from "./chat-state";
import { VoicePlayer, type SpeakClip } from "./voice";

export const useChat = create<ChatState>(() => initialState);

function dispatch(event: ChatEvent): void {
  useChat.setState((state) => reduce(state, event), true);
}

const voice = new VoicePlayer();

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

  /** Stop: halts generation and the voice; the partial reply is kept (FR-C-2). */
  stop(): void {
    voice.stop();
    socket.sendLegacy({ type: "stop" });
  },

  retry(): void {
    const { lastUserText } = useChat.getState();
    if (!lastUserText) return;
    dispatch({ kind: "retrying" });
    actions.send(lastUserText);
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
};
