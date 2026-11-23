// Her picture for Create pet (D-104, D-103): her VRM in Yuri's shell, which the user
// turns and zooms, then takes a picture of (see-through PNG) to copy or save.

import { useEffect, useRef, useState } from "react";

import { createStage, type Framing, type Stage } from "../../engine/stage";
import { KERNEL_HTTP_URL } from "../../net/kernel";
import { actions } from "../store";
import { Icon } from "./Icon";

/** The File System Access API's Save As (Chromium, so WebView2), not yet in TypeScript's DOM types. */
type SaveAsWindow = Window & {
  showSaveFilePicker?: (options: {
    suggestedName: string;
    types: { description: string; accept: Record<string, string[]> }[];
  }) => Promise<{ name: string; createWritable: () => Promise<{ write: (data: Blob) => Promise<void>; close: () => Promise<void> }> }>;
};

export function PictureViewer({ id, name, onClose }: { id: string; name: string; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const stage = useRef<Stage | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [framing, setFraming] = useState<Framing>("full");
  const [shot, setShot] = useState<{ blob: Blob; url: string } | null>(null);
  // A short note on the picture itself: copied, or where it was saved.
  const [note, setNote] = useState<string | null>(null);
  const timer = useRef(0);
  const tell = (text: string) => {
    setNote(text);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setNote(null), 2500);
  };
  useEffect(() => () => window.clearTimeout(timer.current), []);

  useEffect(() => {
    let gone = false;
    const canvas = document.createElement("canvas");   // fresh per mount, as on the Stage
    canvas.className = "stage-canvas";
    box.current?.appendChild(canvas);
    createStage(canvas, `${KERNEL_HTTP_URL}/waifus/${encodeURIComponent(id)}/vrm`, { busy: () => false, orbit: true })
      .then((s) => {
        if (gone) return s.dispose();
        stage.current = s;
        s.frame("full");
        setState("ready");
      })
      .catch(() => !gone && setState("failed"));
    // First, and no further: Esc closes the viewer, not the Settings dialog under it.
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      onClose();
    };
    document.addEventListener("keydown", esc, true);
    return () => {
      gone = true;
      document.removeEventListener("keydown", esc, true);
      stage.current?.dispose();
      stage.current = null;
      canvas.remove();
    };
  }, [id, onClose]);

  useEffect(() => () => {
    if (shot) URL.revokeObjectURL(shot.url);
  }, [shot]);

  const take = async () => {
    const blob = await stage.current?.capture();
    if (blob) setShot({ blob, url: URL.createObjectURL(blob) });
  };
  const copy = async () => {
    if (!shot) return;
    try {
      await navigator.clipboard.write([new ClipboardItem({ "image/png": shot.blob })]);
      tell("Copied. Paste it into the image model.");
    } catch {
      actions.toast("The picture could not be copied. Use Save instead.");
    }
  };
  // Asks where to save (the window's Save As); a webview without it saves to Downloads.
  const save = async () => {
    if (!shot) return;
    const ask = (window as SaveAsWindow).showSaveFilePicker;
    if (!ask) {
      const a = document.createElement("a");
      a.href = shot.url;
      a.download = `${name}.png`;
      a.click();
      tell(`Saved to Downloads as ${name}.png`);
      return;
    }
    try {
      const file = await ask({ suggestedName: `${name}.png`, types: [{ description: "PNG picture", accept: { "image/png": [".png"] } }] });
      const out = await file.createWritable();
      await out.write(shot.blob);
      await out.close();
      tell(`Saved as ${file.name}`);
    } catch (e) {
      if ((e as Error).name !== "AbortError") actions.toast("The picture could not be saved there. Try another folder.");
    }
  };

  return (
    <div className="settings-backdrop confirm-layer" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="picture-dialog" role="dialog" aria-modal="true" aria-label={`${name}'s picture`}>
        <header>
          <h2>{name}'s picture</h2>
          <button type="button" className="settings-close" aria-label="Close" onClick={onClose}>
            <Icon name="close" size={16} />
          </button>
        </header>
        <div className="picture-view">
          <div ref={box} className={shot ? "stage-box hidden" : "stage-box"} />
          {shot ? <img src={shot.url} alt={`${name}, as taken`} /> : null}
          {note ? (
            <p className="picture-note" role="status">
              {note}
            </p>
          ) : null}
          {state === "loading" ? <p className="stage-note">Bringing {name} in…</p> : null}
          {state === "failed" ? <p className="stage-note">{name}'s model could not be loaded.</p> : null}
        </div>
        {shot ? (
          <div className="picture-actions">
            <button type="button" className="ghost" onClick={() => setShot(null)}>
              Take another
            </button>
            <button type="button" onClick={() => void save()}>
              Save as…
            </button>
            <button type="button" className="primary" onClick={() => void copy()}>
              Copy
            </button>
          </div>
        ) : (
          <div className="picture-actions">
            <span className="muted">Drag to turn her, scroll to zoom.</span>
            <div className="view-switch" role="group" aria-label="Framing">
              {(["full", "bust"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={framing === f}
                  onClick={() => {
                    setFraming(f);
                    stage.current?.frame(f);
                  }}
                >
                  {f === "full" ? "Full body" : "Bust"}
                </button>
              ))}
            </div>
            <button type="button" className="primary" disabled={state !== "ready"} onClick={() => void take()}>
              Take picture
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
