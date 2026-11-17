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
}: {
  id?: string | null;
  name: string | null | undefined;
  portrait?: string | null;
  className: string;
  title?: string;
}) {
  const src = id && portrait ? portraitUrl(id, portrait) : null;
  const [failed, setFailed] = useState<string | null>(null);
  const shown = src !== null && failed !== src;
  return (
    <span className={shown ? `${className} has-face` : className} title={title} aria-hidden="true">
      {shown ? (
        <img src={src} alt="" draggable={false} onError={() => setFailed(src)} />
      ) : (
        (name ?? "?").slice(0, 1).toUpperCase()
      )}
    </span>
  );
}
