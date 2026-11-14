// The input row (K1-02): multi-line, Enter sends, Shift+Enter is a newline
// (FR-C-3), Stop while a reply runs (FR-C-2). The `＋` tray and the heart
// animation are K1-05.

import { useState, type KeyboardEvent } from "react";

import { canSend } from "../chat-state";
import { actions, useChat } from "../store";

export function Composer() {
  const [text, setText] = useState("");
  const turn = useChat((s) => s.turn);
  const ready = useChat(canSend);
  const role = useChat((s) => s.role);
  const companion = useChat((s) => s.companion?.name ?? null);

  const submit = () => {
    if (actions.send(text)) setText("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const placeholder =
    role === "observer"
      ? "Another Kōkyū window is talking to the kernel"
      : companion
        ? `Message ${companion}…`
        : "Message…";

  return (
    <div className="composer">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        rows={1}
        aria-label="Message"
        disabled={role === "observer"}
      />
      {turn === "idle" ? (
        <button type="button" className="send" onClick={submit} disabled={!ready || !text.trim()}>
          Send
        </button>
      ) : (
        <button type="button" className="stop" onClick={() => actions.stop()}>
          Stop
        </button>
      )}
    </div>
  );
}
