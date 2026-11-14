// The input row (K1-02, K1-05): multi-line, Enter sends, Shift+Enter is a newline,
// a pasted image or a dropped file is attached (FR-C-3); the `＋` tray (FR-C-4);
// the status heart (FR-C-5); the model chip (K1-10, FR-M-1); Stop while a reply
// runs (FR-C-2).

import { useEffect, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent } from "react";

import { classifyFile, readTextFile, resizeImageToBase64Jpeg } from "../../file-upload";
import { canSend } from "../chat-state";
import { actions, useChat, type Attachment } from "../store";
import { Heart } from "./Heart";
import { ModelChip } from "./ModelChip";

async function readAttachment(file: File): Promise<Attachment | string> {
  const kind = classifyFile(file);
  if (kind.kind === "unsupported") return kind.reason;
  try {
    const content = kind.kind === "image" ? await resizeImageToBase64Jpeg(file) : await readTextFile(file);
    return { filename: file.name || "pasted image", kind: kind.kind, content };
  } catch {
    return "Couldn't read that file. Try a different one?";
  }
}

export function Composer() {
  const [text, setText] = useState("");
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const turn = useChat((s) => s.turn);
  const ready = useChat(canSend);
  const role = useChat((s) => s.role);
  const companion = useChat((s) => s.companion?.name ?? null);
  const box = useRef<HTMLTextAreaElement>(null);

  const attach = async (file: File | undefined) => {
    if (!file) return;
    const read = await readAttachment(file);
    if (typeof read === "string") {
      setProblem(read);
    } else {
      setAttachment(read);
      setProblem(null);
      box.current?.focus();
    }
  };

  const submit = () => {
    const sent = attachment ? actions.sendFile(attachment, text) : actions.send(text);
    if (sent) {
      setText("");
      setAttachment(null);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  // A pasted image becomes the attachment; pasted text stays ordinary typing.
  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const file = Array.from(e.clipboardData.files)[0];
    if (file) {
      e.preventDefault();
      void attach(file);
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (role !== "observer") void attach(e.dataTransfer.files[0]);
  };

  const placeholder =
    role === "observer"
      ? "Another Kōkyū window is talking to the kernel"
      : companion
        ? `Message ${companion}…`
        : "Message…";

  return (
    <div
      className={dragging ? "composer dragging" : "composer"}
      onDragOver={(e) => {
        if (Array.from(e.dataTransfer.types).includes("Files")) {
          e.preventDefault();
          setDragging(true);
        }
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      {attachment ? (
        <div className="attachment">
          <span>
            {attachment.kind === "image" ? "Image" : "File"}: {attachment.filename}
          </span>
          <button type="button" aria-label={`Remove ${attachment.filename}`} onClick={() => setAttachment(null)}>
            ×
          </button>
        </div>
      ) : null}
      {problem ? (
        <p className="composer-problem" role="alert">
          {problem}
        </p>
      ) : null}
      <textarea
        ref={box}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        onPaste={onPaste}
        placeholder={attachment ? "Add a comment (optional)…" : placeholder}
        rows={1}
        aria-label="Message"
        disabled={role === "observer"}
      />
      <div className="composer-bar">
        <Tray onFile={(f) => void attach(f)} disabled={role === "observer"} />
        <Heart />
        <ModelChip />
        {turn === "idle" ? (
          <button
            type="button"
            className="send"
            onClick={submit}
            disabled={!ready || (!text.trim() && !attachment)}
          >
            Send
          </button>
        ) : (
          <button type="button" className="stop" onClick={() => actions.stop()}>
            Stop
          </button>
        )}
      </div>
    </div>
  );
}

// FR-C-4: every item is listed; the ones that arrive with K2 are visibly disabled.
const LATER = [
  { label: "Camera", hint: "Arrives with voice and the stage (K2)" },
  { label: "Voice", hint: "Arrives with voice and the stage (K2)" },
  { label: "Screenshot", hint: "Arrives with voice and the stage (K2)" },
  { label: "Paste image", hint: "Coming in K2. Ctrl+V in the message box works now" },
];

function Tray({ onFile, disabled }: { onFile: (file: File | undefined) => void; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const first = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    first.current?.focus();
    const onDown = (e: MouseEvent) => {
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div
      className="tray"
      ref={wrapper}
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false);
      }}
    >
      <button
        type="button"
        className="tray-toggle"
        aria-label="Add"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
      >
        ＋
      </button>
      {open ? (
        <div className="tray-menu" role="menu" aria-label="Add">
          <button
            ref={first}
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              picker.current?.click();
            }}
          >
            Upload file
          </button>
          {LATER.map((item) => (
            <button key={item.label} type="button" role="menuitem" disabled title={item.hint}>
              {item.label}
              <span className="soon">soon</span>
            </button>
          ))}
        </div>
      ) : null}
      <input
        ref={picker}
        type="file"
        hidden
        onChange={(e) => {
          onFile(e.target.files?.[0]);
          e.target.value = ""; // picking the same file again still fires
        }}
      />
    </div>
  );
}
