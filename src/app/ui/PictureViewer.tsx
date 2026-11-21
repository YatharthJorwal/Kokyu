// Her picture for Create pet (D-104, D-103): her VRM in Yuri's shell, which the user
// turns and zooms, then takes a picture of (see-through PNG) to copy or save.

import { useEffect, useRef, useState } from "react";

import { createStage, type Framing, type Stage } from "../../engine/stage";
import { KERNEL_HTTP_URL } from "../../net/kernel";
import { actions } from "../store";
import { Icon } from "./Icon";

export function PictureViewer({ id, name, onClose }: { id: string; name: string; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const stage = useRef<Stage | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [framing, setFraming] = useState<Framing>("full");
  const [shot, setShot] = useState<{ blob: Blob; url: string } | null>(null);
  const [copied, setCopied] = useState(false);

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
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => {
      gone = true;
      window.removeEventListener("keydown", esc);
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
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      actions.toast("The picture could not be copied. Use Save instead.");
    }
  };
  const save = () => {
    if (!shot) return;
    const a = document.createElement("a");
    a.href = shot.url;
    a.download = `${name}.png`;
    a.click();
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
          {state === "loading" ? <p className="stage-note">Bringing {name} in…</p> : null}
          {state === "failed" ? <p className="stage-note">{name}'s model could not be loaded.</p> : null}
        </div>
        {shot ? (
          <div className="picture-actions">
            <button type="button" className="ghost" onClick={() => setShot(null)}>
              Take another
            </button>
            <button type="button" onClick={save}>
              Save
            </button>
            <button type="button" className="primary" onClick={() => void copy()}>
              {copied ? "Copied" : "Copy"}
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
