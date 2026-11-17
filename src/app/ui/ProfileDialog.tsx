// Her profile (D-091, FR-W-9): her face, name, traits and About, a Chat button that
// starts a new chat with her, and her picture: change it, or go back to the face
// from her model. Not a platform page: no creator, likes, counts or sharing.

import { useEffect, useRef } from "react";

import { canStartThread, type Companion } from "../chat-state";
import { actions, useChat } from "../store";
import { Portrait } from "./Portrait";

export function ProfileDialog() {
  const id = useChat((s) => s.profile);
  const companion = useChat((s) => s.roster.find((w) => w.id === s.profile) ?? null);
  if (id === null || companion === null) return null;
  return (
    <div className="settings-backdrop" onMouseDown={(e) => e.target === e.currentTarget && actions.closeProfile()}>
      <ProfileBody key={companion.id} companion={companion} />
    </div>
  );
}

function ProfileBody({ companion }: { companion: Companion }) {
  const canChat = useChat(canStartThread);
  const online = useChat((s) => s.connection === "online");
  const file = useRef<HTMLInputElement>(null);
  const chat = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") actions.closeProfile();
    };
    document.addEventListener("keydown", onKey);
    chat.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const traits = companion.traits ?? [];
  return (
    <div className="profile-dialog" role="dialog" aria-modal="true" aria-labelledby="profile-name">
      <button type="button" className="settings-close ghost" aria-label="Close" onClick={() => actions.closeProfile()}>
        ✕
      </button>
      <Portrait id={companion.id} name={companion.name} portrait={companion.portrait} className="profile-face" />
      <h2 id="profile-name">{companion.name}</h2>
      <button
        ref={chat}
        type="button"
        className="primary profile-chat"
        disabled={!canChat}
        title={`Start a new chat with ${companion.name}`}
        onClick={() => actions.chatWith(companion.id)}
      >
        Chat
      </button>
      {companion.about ? (
        <section className="profile-section">
          <h3>About</h3>
          <p>{companion.about}</p>
        </section>
      ) : null}
      {traits.length > 0 ? (
        <section className="profile-section">
          <h3>Traits</h3>
          <ul className="profile-traits">
            {traits.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <div className="profile-picture">
        <input
          ref={file}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          hidden
          onChange={(e) => {
            const picked = e.target.files?.[0];
            e.target.value = "";
            if (picked) void actions.choosePortrait(companion.id, picked);
          }}
        />
        <button type="button" disabled={!online} onClick={() => file.current?.click()}>
          Change picture
        </button>
        {companion.portraitChosen ? (
          <button type="button" className="ghost" disabled={!online} onClick={() => actions.resetPortrait(companion.id)}>
            Use the model's face
          </button>
        ) : null}
      </div>
    </div>
  );
}
