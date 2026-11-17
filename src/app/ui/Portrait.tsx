// Her face (D-091, FR-W-8): the picture the engine serves from her VRM, or the one
// the user chose in her profile. Her initial while it loads, when she has none,
// or when the engine cannot be reached. `portrait` is the engine's version stamp,
// so a new picture is a new URL.

import { useState } from "react";

import { KERNEL_HTTP_URL } from "../../net/kernel";

export function portraitUrl(id: string, portrait: string): string {
  return `${KERNEL_HTTP_URL}/waifus/${encodeURIComponent(id)}/portrait?v=${encodeURIComponent(portrait)}`;
}

export function Portrait({
  id,
  name,
  portrait,
  className,
  title,
  onClick,
}: {
  id?: string | null;
  name: string | null | undefined;
  portrait?: string | null;
  className: string;
  title?: string;
  /** Makes it a button (her profile, D-091); `title` is then its label. */
  onClick?: () => void;
}) {
  const src = id && portrait ? portraitUrl(id, portrait) : null;
  const [failed, setFailed] = useState<string | null>(null);
  const shown = src !== null && failed !== src;
  const classes = shown ? `${className} has-face` : className;
  const face = shown ? (
    <img src={src} alt="" draggable={false} onError={() => setFailed(src)} />
  ) : (
    (name ?? "?").slice(0, 1).toUpperCase()
  );
  if (onClick) {
    return (
      <button type="button" className={`${classes} face-button`} title={title} aria-label={title} onClick={onClick}>
        {face}
      </button>
    );
  }
  return (
    <span className={classes} title={title} aria-hidden="true">
      {face}
    </span>
  );
}
