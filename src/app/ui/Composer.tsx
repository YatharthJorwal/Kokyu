// The input row (K1-02, K1-05; laid out to the reference in K1-15, D-068): one
// rounded box with the paperclip tray (FR-C-4) and the screen companions in it
// (K1-05b, FR-SC-1..4), the message (multi-line, Enter sends, Shift+Enter is a
// newline, a pasted image or a dropped file is attached, FR-C-3) and a round Send, or Stop while a reply runs (FR-C-2).
// Under the box: a status line at the left (Read aloud and screen companion chips,
// FR-SC-2; Temp Chat; else a keyboard hint) and the model chip (K1-10, FR-M-1)
// at the right. The companion chip moved to the top bar. Beside Send, the mic
// (D-097): it or its key (F9 unless changed) dictates into the box, never sends.
// D-101: in a roleplay the paperclip becomes the story tray (a book): History, New
// chat and Memory first, then Upload file and Read aloud; no screen companions.

import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent,
  type DragEvent,
  type KeyboardEvent,
} from "react";

import { UploadProblem, classifyFile, readTextFile, resizeImageToBase64Jpeg } from "../file-upload";
import { canSend, canStartThread, currentMode } from "../chat-state";
import { MAX_DICTATION_S, insertDictation, isDictationKey, micProblem, recordingTime } from "../dictation";
import { useDictationKey } from "../dictation-key";
import { anyModal } from "../keys";
import { readAloudLine, voiceStarting } from "../read-aloud";
import { MicRecorder, blobToBase64 } from "../recorder";
import { TEXT_MAX } from "../../net/protocol";
import { actions, useChat, type Attachment } from "../store";
import { Icon } from "./Icon";
import { ModelChip } from "./ModelChip";

async function readAttachment(file: File): Promise<Attachment | string> {
  const kind = classifyFile(file);
  if (kind.kind === "unsupported") return kind.reason;
  try {
    const content = kind.kind === "image" ? await resizeImageToBase64Jpeg(file) : await readTextFile(file);
    if (!content.trim()) return "That file is empty.";
    return { filename: file.name || "pasted image", kind: kind.kind, content };
  } catch (e) {
    return e instanceof UploadProblem ? e.message : "Couldn't read that file. Try a different one?";
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
  const roleplay = useChat((s) => currentMode(s) === "roleplay");
  const box = useRef<HTMLTextAreaElement>(null);
  const dictation = useDictation(box, setText, setProblem);

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
      ? "Another Kōkyū window is running this chat"
      : roleplay
        ? `Write to ${companion ?? "her"}… *actions* in asterisks`
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
            maxLength={TEXT_MAX}
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
          <MicButton dictation={dictation} />
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
            <button type="button" className="stop" aria-label="Stop" title="Stop (Esc)" onClick={() => actions.stop()}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="7" y="7" width="10" height="10" rx="1.5" />
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="composer-under">
        <div className="composer-status">
          <ReadAloudChip />
          <ScreenChips />
          <StatusHint />
        </div>
        <ModelChip />
      </div>
      <p className="ai-note">
        {companion ?? "This companion"} is an AI, not a real person.{" "}
        {roleplay ? "Treat everything in this roleplay as fiction." : "What she says can be wrong: don't rely on it for facts or advice."}
      </p>
    </div>
  );
}

type DictationPhase = "idle" | "opening" | "recording" | "writing";

interface Dictation {
  phase: DictationPhase;
  startedAt: number;
  toggle: () => void;
}

/** D-097: the mic. Recording → the engine writes it down → the words go into the box
 * at the caret (never sent). Its key toggles it while the window has focus and no
 * dialog is open; it stops by itself after MAX_DICTATION_S. */
function useDictation(
  box: React.RefObject<HTMLTextAreaElement | null>,
  setText: React.Dispatch<React.SetStateAction<string>>,
  setProblem: (p: string | null) => void,
): Dictation {
  const [phase, setPhase] = useState<DictationPhase>("idle");
  const [startedAt, setStartedAt] = useState(0);
  const mic = useRef<MicRecorder | null>(null);
  const caret = useRef<number | null>(null);
  const key = useDictationKey((s) => s.key);
  const usable = useChat((s) => s.role === "driver" && s.connection === "online");

  const start = async () => {
    setPhase("opening");
    setProblem(null);
    const rec = new MicRecorder();
    try {
      await rec.start();
    } catch (err) {
      setProblem(micProblem(err));
      setPhase("idle");
      return;
    }
    mic.current = rec;
    setStartedAt(Date.now());
    setPhase("recording");
    actions.dictateStart();
  };

  const stop = async () => {
    const rec = mic.current;
    mic.current = null;
    if (!rec) return;
    setPhase("writing");
    const blob = await rec.stop();
    if (!blob) {
      setPhase("idle");
      setProblem("Nothing was recorded.");
      return;
    }
    const heard = await actions.dictate(await blobToBase64(blob), blob.type || "audio/webm");
    setPhase("idle");
    if (heard.error) return setProblem(heard.error);
    if (!heard.text.trim()) return setProblem("Didn't catch anything. Try again, a little closer to the mic.");
    const el = box.current;
    setText((cur) => {
      const put = insertDictation(cur, heard.text, el?.selectionStart ?? cur.length, el?.selectionEnd ?? cur.length);
      caret.current = put.caret;
      return put.value;
    });
  };

  // After the words go in: the caret after them, the box focused for editing.
  useLayoutEffect(() => {
    if (caret.current === null || !box.current) return;
    box.current.focus();
    box.current.setSelectionRange(caret.current, caret.current);
    caret.current = null;
  });

  const toggle = () => {
    if (phase === "recording") void stop();
    else if (phase === "idle" && usable) void start();
  };
  const latest = useRef(toggle);
  latest.current = toggle;

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (!isDictationKey(e, key) || anyModal(useChat.getState())) return;
      e.preventDefault();
      latest.current();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [key]);

  useEffect(() => {
    if (phase !== "recording") return;
    const t = window.setTimeout(() => latest.current(), MAX_DICTATION_S * 1000);
    return () => window.clearTimeout(t);
  }, [phase]);

  useEffect(() => () => mic.current?.cancel(), []); // the window went: the mic light goes off

  return { phase, startedAt, toggle };
}

function MicButton({ dictation }: { dictation: Dictation }) {
  const key = useDictationKey((s) => s.key);
  const usable = useChat((s) => s.role === "driver" && s.connection === "online");
  const { phase, startedAt, toggle } = dictation;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (phase !== "recording") return;
    setNow(Date.now());
    const t = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(t);
  }, [phase]);
  const recording = phase === "recording";
  const label = recording ? `Stop dictating (${key})` : phase === "writing" ? "Writing it down…" : `Dictate (${key})`;
  return (
    <>
      {recording ? (
        <span className="mic-time" aria-hidden="true">
          {recordingTime((now - startedAt) / 1000)}
        </span>
      ) : null}
      <button
        type="button"
        className={`mic ${phase}`}
        aria-label={label}
        aria-pressed={recording}
        title={label}
        disabled={(!usable && !recording) || phase === "opening" || phase === "writing"}   // a recording can always be stopped
        onClick={toggle}
      >
        {phase === "writing" ? <span className="spinner" aria-hidden="true" /> : <Icon name="mic" size={18} />}
      </button>
    </>
  );
}

/** The status line's quiet state: Temp Chat, else how to send. Silent while a chip speaks. */
function StatusHint() {
  const busy = useChat((s) => (s.readAloud?.on ?? false) || s.reading !== null || (s.screen?.task_guide.on ?? false) || (s.screen?.ocr_watch.on ?? false));
  const temp = useChat((s) => s.thread?.temp ?? false);
  const observer = useChat((s) => s.role === "observer");
  if (busy || observer) return null;
  return (
    <span className="status-hint">
      {temp ? "Temp Chat: this chat is not remembered" : "Enter to send · Shift+Enter for a new line"}
    </span>
  );
}

/** D-097: Read aloud on: her voice starting (counting to about 47 s), reading, or
 * failed with Try again and Set up; × turns it off. D-112: also while her voice starts
 * for one message read on request, and if that fails. */
function ReadAloudChip() {
  const status = useChat((s) => s.readAloud);
  const name = useChat((s) => s.companion?.name ?? "Her");
  const canAct = useChat((s) => s.role === "driver" && s.connection === "online");
  const reading = useChat((s) => s.reading);
  // A message's speaker asked for her voice: kept after the reading ends, so a failure stays said.
  const [asked, setAsked] = useState(false);
  useEffect(() => {
    if (reading !== null) setAsked(true);
  }, [reading]);
  useEffect(() => {
    if (status?.state === "ready" && reading === null) setAsked(false);
  }, [status, reading]);
  const wanted = asked && !status?.on;
  const starting = voiceStarting(status, wanted);
  // When the start began, from the engine's count at this frame; the chip counts on.
  const since = useMemo(() => Date.now() - (status?.elapsed_s ?? 0) * 1000, [status]);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!starting) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [starting]);
  const line = readAloudLine(status, name, starting ? (now - since) / 1000 : 0, wanted);
  if (line === null) return null;
  return (
    <div className="screen-chips" role="status" aria-label="Read aloud">
      <span className={starting ? "screen-chip voice-chip starting" : "screen-chip voice-chip"}>
        <Icon name="speaker" size={14} /> {line}
        {status?.state === "failed" && status.on ? (
          <button type="button" className="chip-retry" disabled={!canAct} onClick={() => actions.setReadAloud(true)}>
            Try again
          </button>
        ) : null}
        {status?.state === "failed" ? (
          <button type="button" className="chip-retry" onClick={() => actions.openSettings("voice")}>
            Set up
          </button>
        ) : null}
        <button
          type="button"
          aria-label={wanted ? "Dismiss" : "Turn off Read aloud"}
          title={wanted ? "Dismiss" : "Turn off Read aloud"}
          disabled={!canAct && !wanted}
          onClick={() => {
            if (!wanted) return actions.setReadAloud(false);
            actions.stopReading();
            setAsked(false);
          }}
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
  const readAloudOn = useChat((s) => s.readAloud?.on ?? false);
  const roleplay = useChat((s) => currentMode(s) === "roleplay");
  const canStart = useChat(canStartThread);
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
        if (e.key === "Escape") {
          e.preventDefault(); // closing the tray, not stopping a reply (UI1-10)
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        className="tray-toggle"
        aria-label={roleplay ? "Story" : "Attach"}
        title={roleplay ? "History, a new chat, Memory; a file; Read aloud" : "Attach a file; Read aloud; screen companions"}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          {roleplay ? (
            <path d="M12 6.5C10 5 7.5 4.5 4 4.5v13c3.5 0 6 .5 8 2 2-1.5 4.5-2 8-2v-13c-3.5 0-6 .5-8 2zM12 6.5v13" />
          ) : (
            <path d="M20 11.5l-7.8 7.8a5 5 0 0 1-7.1-7.1l8.2-8.2a3.3 3.3 0 0 1 4.7 4.7l-8.2 8.2a1.7 1.7 0 0 1-2.4-2.4l7.6-7.6" />
          )}
        </svg>
      </button>
      {open ? (
        <div className="tray-menu" role="menu" aria-label={roleplay ? "Story" : "Attach"}>
          {roleplay ? (
            <>
              <button
                ref={first}
                type="button"
                role="menuitem"
                title="Every roleplay with her"
                onClick={() => {
                  setOpen(false);
                  actions.openStory("history");
                }}
              >
                History
              </button>
              {canStart ? (
                <button
                  type="button"
                  role="menuitem"
                  title="This story again from the start, with her"
                  onClick={() => {
                    setOpen(false);
                    actions.newStory();
                  }}
                >
                  New chat
                </button>
              ) : null}
              <button
                type="button"
                role="menuitem"
                title="What she keeps in mind for this story, and its pinned messages"
                onClick={() => {
                  setOpen(false);
                  actions.openStory("memory");
                }}
              >
                Memory
              </button>
              <div className="tray-section" role="presentation" />
            </>
          ) : null}
          <button
            ref={roleplay ? undefined : first}
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
            className="menu-with-icon"
            aria-checked={readAloudOn}
            title="She reads each reply aloud once it is written. Her voice takes about 47 seconds to start"
            onClick={() => {
              actions.setReadAloud(!readAloudOn);
              setOpen(false);
            }}
          >
            <Icon name="speaker" size={15} />
            Read aloud
            <span className="menu-state">{readAloudOn ? "on" : "off"}</span>
          </button>
          {roleplay ? null : (
            <>
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
            <span className="menu-state">{screen?.ocr_watch.on ? "on" : "off"}</span>
          </button>
            </>
          )}
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
