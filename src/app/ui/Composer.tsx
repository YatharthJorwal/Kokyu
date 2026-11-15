// The input row (K1-02, K1-05; laid out to the reference in K1-15, D-068): one
// rounded box with the paperclip tray (FR-C-4) and the screen companions in it
// (K1-05b, FR-SC-1..4), the message (multi-line, Enter sends, Shift+Enter is a
// newline, a pasted image or a dropped file is attached, FR-C-3), the mic (voice
// input arrives in K2) and a round Send, or Stop while a reply runs (FR-C-2).
// Status chips (FR-SC-2) sit above the message; the model chip (K1-10, FR-M-1)
// sits under the box. The companion chip moved to the top bar.

import { useEffect, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent } from "react";

import { classifyFile, readTextFile, resizeImageToBase64Jpeg } from "../file-upload";
import { canSend } from "../chat-state";
import { actions, useChat, type Attachment } from "../store";
import { ModelChip } from "./ModelChip";

async function readAttachment(file: File): Promise<Attachment | string> {
  const kind = classifyFile(file);
  if (kind.kind === "unsupported") return kind.reason;
  try {
    const content = kind.kind === "image" ? await resizeImageToBase64Jpeg(file) : await readTextFile(file);
    if (!content.trim()) return "That file is empty.";
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
      setProblem(null);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  // A pasted image becomes the attachment; pasted text stays ordinary typing, even
  // when Excel or OneNote put a picture of it on the clipboard too.
  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const file = Array.from(e.clipboardData.files)[0];
    if (file && !e.clipboardData.getData("text/plain")) {
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
    <div className="composer-area">
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
        <VoiceChip />
        <ScreenChips />
        {attachment ? (
          <div className="attachment">
            <span>
              {attachment.kind === "image" ? "Image" : "File"}: {attachment.filename}
            </span>
            <button type="button" aria-label={`Remove ${attachment.filename}`} onClick={() => {
                setAttachment(null);
                setProblem(null);
              }}>
              ×
            </button>
          </div>
        ) : null}
        {problem ? (
          <p className="composer-problem" role="alert">
            {problem}
          </p>
        ) : null}
        <div className="composer-row">
          <Tray onFile={(f) => void attach(f)} disabled={role === "observer"} />
          <textarea
            ref={box}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              actions.typing();
            }}
            onKeyDown={onKeyDown}
            onPaste={onPaste}
            placeholder={attachment ? "Add a comment (optional)…" : placeholder}
            rows={1}
            aria-label="Message"
            disabled={role === "observer"}
          />
          <button type="button" className="mic" aria-label="Talk" disabled title="Talking to her by voice arrives with the stage (K2)">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="9" y="3" width="6" height="11" rx="3" />
              <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" />
            </svg>
          </button>
          {turn === "idle" ? (
            <button
              type="button"
              className="send"
              aria-label="Send"
              title="Send"
              onClick={submit}
              disabled={!ready || (!text.trim() && !attachment)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20.5 3.5L3.5 10.5l7 3 3 7z" />
                <path d="M20.5 3.5l-10 10" />
              </svg>
            </button>
          ) : (
            <button type="button" className="stop" aria-label="Stop" title="Stop" onClick={() => actions.stop()}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="7" y="7" width="10" height="10" rx="1.5" />
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="composer-under">
        <ModelChip />
      </div>
    </div>
  );
}

// FR-C-4: every item is listed; the ones that arrive with K2 are visibly disabled.
const LATER = [
  { label: "Camera", hint: "Arrives with voice and the stage (K2)" },
  { label: "Screenshot", hint: "Arrives with voice and the stage (K2)" },
  { label: "Paste image", hint: "Coming in K2. Ctrl+V in the message box works now" },
];

/** D-061: voice waking up, on, or failed with Try again; × turns it off. */
function VoiceChip() {
  const voice = useChat((s) => s.voice);
  const name = useChat((s) => s.companion?.name ?? "Her");
  const canAct = useChat((s) => s.role === "driver" && s.connection === "online");
  if (!voice?.on) return null;
  const waking = voice.state === "loading" || voice.state === "idle";
  const line =
    voice.state === "failed"
      ? `${name}'s voice couldn't start. ${voice.message ?? ""}`
      : waking
        ? `${name}'s voice is waking up…`
        : `Voice on: ${name} speaks her replies`;
  return (
    <div className="screen-chips" role="status" aria-label="Voice">
      <span className={waking ? "screen-chip voice-chip waking" : "screen-chip voice-chip"}>
        <span aria-hidden="true">🔊</span> {line}
        {voice.state === "failed" ? (
          <button type="button" className="chip-retry" disabled={!canAct} onClick={() => actions.setVoice(true)}>
            Try again
          </button>
        ) : null}
        <button
          type="button"
          aria-label="Turn voice off"
          title="Turn voice off"
          disabled={!canAct}
          onClick={() => actions.setVoice(false)}
        >
          ×
        </button>
      </span>
    </div>
  );
}

/** FR-SC-2: what is watching the screen, each stopped with one click. */
function ScreenChips() {
  const screen = useChat((s) => s.screen);
  const canAct = useChat((s) => s.role === "driver" && s.connection === "online");
  if (!screen || (!screen.task_guide.on && !screen.ocr_watch.on)) return null;
  return (
    <div className="screen-chips" role="status" aria-label="Watching your screen">
      {screen.task_guide.on ? (
        <span className="screen-chip">
          <span aria-hidden="true">👁</span> Task Guide: {screen.task_guide.task ?? "tell her what you are working on"}
          <button
            type="button"
            aria-label="Stop Task Guide"
            title="Stop Task Guide"
            disabled={!canAct}
            onClick={() => actions.setScreenCompanion("task_guide", false)}
          >
            ×
          </button>
        </span>
      ) : null}
      {screen.ocr_watch.on ? (
        <span className="screen-chip">
          <span aria-hidden="true">👁</span> OCR watch
          <button
            type="button"
            aria-label="Stop OCR watch"
            title="Stop OCR watch"
            disabled={!canAct}
            onClick={() => actions.setScreenCompanion("ocr_watch", false)}
          >
            ×
          </button>
        </span>
      ) : null}
    </div>
  );
}

function Tray({ onFile, disabled }: { onFile: (file: File | undefined) => void; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const [asking, setAsking] = useState(false);
  const [task, setTask] = useState("");
  const screen = useChat((s) => s.screen);
  const voiceOn = useChat((s) => s.voice?.on ?? false);
  const wrapper = useRef<HTMLDivElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const first = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      setAsking(false);
      return;
    }
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
        aria-label="Attach"
        title="Attach a file; voice; screen companions"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M20 11.5l-7.8 7.8a5 5 0 0 1-7.1-7.1l8.2-8.2a3.3 3.3 0 0 1 4.7 4.7l-8.2 8.2a1.7 1.7 0 0 1-2.4-2.4l7.6-7.6" />
        </svg>
      </button>
      {open ? (
        <div className="tray-menu" role="menu" aria-label="Attach">
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
          <button
            type="button"
            role="menuitemcheckbox"
            aria-checked={voiceOn}
            title="She speaks her replies. The first time, her voice takes about a minute to wake up"
            onClick={() => {
              actions.setVoice(!voiceOn);
              setOpen(false);
            }}
          >
            Voice
            <span className="soon">{voiceOn ? "on" : "off"}</span>
          </button>
          {LATER.map((item) => (
            <button key={item.label} type="button" role="menuitem" disabled title={item.hint}>
              {item.label}
              <span className="soon">soon</span>
            </button>
          ))}
          <div className="tray-section" role="presentation">
            Screen companions
          </div>
          {asking ? (
            <form
              className="task-form"
              onSubmit={(e) => {
                e.preventDefault();
                if (!task.trim()) return;
                actions.setScreenCompanion("task_guide", true, task);
                setTask("");
                setOpen(false);
              }}
            >
              {/* the task in the user's own words (FR-SC-4) */}
              <input
                autoFocus
                aria-label="What are you working on?"
                placeholder="What are you working on?"
                maxLength={200}
                value={task}
                onChange={(e) => setTask(e.target.value)}
              />
              <button type="submit" disabled={!task.trim()}>
                Start
              </button>
            </form>
          ) : (
            <button
              type="button"
              role="menuitem"
              title="She checks your screen now and then and nudges you when you drift"
              onClick={() => setAsking(true)}
            >
              {screen?.task_guide.on ? "Task Guide: change task…" : "Task Guide…"}
            </button>
          )}
          <button
            type="button"
            role="menuitemcheckbox"
            aria-checked={screen?.ocr_watch.on ?? false}
            title="Rare remarks about what is on your screen"
            onClick={() => {
              actions.setScreenCompanion("ocr_watch", !(screen?.ocr_watch.on ?? false));
              setOpen(false);
            }}
          >
            OCR watch
            <span className="soon">{screen?.ocr_watch.on ? "on" : "off"}</span>
          </button>
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
