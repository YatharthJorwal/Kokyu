// New roleplay… (K1c-08, FR-MODE-6): a dialog over the chat, built like Settings.
// Left, the saved scenario cards (pick one to fill the form, delete one after a
// confirm step); right, the card's fields and the ways to start. A card is the
// user's own and app-level: it never belongs to a companion (D-074).

import { useEffect, useRef, useState, type FormEvent } from "react";

import type { SavedScenario } from "../../net/protocol";
import { canStartThread } from "../chat-state";
import { EMPTY_FORM, SCENARIO_FIELDS, cardFromForm, formFromCard, isBlankCard, sameCard, type ScenarioForm } from "../scenario";
import { actions, useChat } from "../store";

export function RoleplayDialog() {
  const open = useChat((s) => s.roleplayOpen);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") actions.closeRoleplay();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;
  return (
    <div className="settings-backdrop" onMouseDown={(e) => e.target === e.currentTarget && actions.closeRoleplay()}>
      <RoleplayBody />
    </div>
  );
}

/** Mounted while the dialog is open, so each opening starts from an empty form. */
function RoleplayBody() {
  const scenarios = useChat((s) => s.scenarios);
  const canStart = useChat(canStartThread);
  const companion = useChat((s) => s.companion?.name ?? null);
  const [form, setForm] = useState<ScenarioForm>(EMPTY_FORM);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  // A save waits for the kernel's fresh list; a new card is then the newest one.
  const [saving, setSaving] = useState<{ kind: "new" | "update"; before: SavedScenario[] | null } | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const firstField = useRef<HTMLInputElement>(null);

  const loaded = scenarios?.find((c) => c.id === loadedId) ?? null;
  const card = cardFromForm(form);
  const blank = isBlankCard(card);

  useEffect(() => {
    firstField.current?.focus();
  }, []);

  useEffect(() => {
    if (!saving || scenarios === saving.before) return;
    if (saving.kind === "new") setLoadedId(scenarios?.[0]?.id ?? null);
    setSaving(null);
    setStatus("Saved.");
  }, [scenarios, saving]);

  const edit = (key: keyof ScenarioForm, value: string) => {
    setForm({ ...form, [key]: value });
    setStatus(null);
  };

  const pick = (c: SavedScenario) => {
    setForm(formFromCard(c.card));
    setLoadedId(c.id);
    setConfirming(null);
    setStatus(null);
  };

  const save = (kind: "new" | "update") => {
    if (blank) return;
    const sent = kind === "update" && loaded ? actions.saveScenario(card, loaded.id) : actions.saveScenario(card);
    if (sent) {
      setSaving({ kind, before: scenarios });
      setStatus("Saving…");
    }
  };

  const remove = (id: string) => {
    if (actions.deleteScenario(id) && id === loadedId) setLoadedId(null);
    setConfirming(null);
  };

  const start = (e: FormEvent) => {
    e.preventDefault();
    actions.newRoleplay(blank ? null : card);
  };

  return (
    <div className="settings-dialog roleplay-dialog" role="dialog" aria-modal="true" aria-labelledby="roleplay-title">
      <nav className="settings-nav roleplay-cards" aria-label="Saved scenarios">
        <h2>Saved scenarios</h2>
        {scenarios === null ? <p className="muted small">Loading…</p> : null}
        {scenarios?.length === 0 ? <p className="muted small">No saved scenarios yet. Fill in a card and save it.</p> : null}
        <ul>
          {(scenarios ?? []).map((c) =>
            confirming === c.id ? (
              <li key={c.id} className="card-confirm" role="group" aria-label={`Delete ${c.title}?`}>
                <span className="confirm-text">Delete “{c.title}”?</span>
                <span className="card-confirm-actions">
                  <button type="button" className="danger" onClick={() => remove(c.id)}>
                    Delete
                  </button>
                  {/* the safe choice gets the focus */}
                  <button type="button" autoFocus onClick={() => setConfirming(null)}>
                    Cancel
                  </button>
                </span>
              </li>
            ) : (
              <li key={c.id} className="card-row">
                <button
                  type="button"
                  className={c.id === loadedId ? "current" : undefined}
                  aria-current={c.id === loadedId ? "true" : undefined}
                  title={c.card.setting ?? c.title}
                  onClick={() => pick(c)}
                >
                  {c.title}
                </button>
                <button type="button" className="card-delete" aria-label={`Delete ${c.title}`} title="Delete" onClick={() => setConfirming(c.id)}>
                  ✕
                </button>
              </li>
            ),
          )}
        </ul>
      </nav>
      <section className="settings-body">
        <button type="button" className="settings-close ghost" aria-label="Close" onClick={() => actions.closeRoleplay()}>
          ✕
        </button>
        <h3 id="roleplay-title">New roleplay</h3>
        <p className="muted">
          Set the scene for a story with {companion ?? "her"}. Every field is optional. In the story, write *actions* in
          asterisks and (OOC …) to step out of it.
        </p>
        <form className="settings-form" onSubmit={start}>
          {SCENARIO_FIELDS.map((f, i) => (
            <label key={f.key} className="settings-field">
              <span>{f.label}</span>
              {f.multiline ? (
                <textarea
                  value={form[f.key]}
                  maxLength={f.max}
                  rows={3}
                  placeholder={f.hint}
                  onChange={(e) => edit(f.key, e.target.value)}
                />
              ) : (
                <input
                  ref={i === 0 ? firstField : undefined}
                  value={form[f.key]}
                  maxLength={f.max}
                  placeholder={f.hint}
                  onChange={(e) => edit(f.key, e.target.value)}
                />
              )}
            </label>
          ))}
          <div className="settings-actions roleplay-actions">
            <button type="submit" className="primary" disabled={!canStart}>
              Start roleplay
            </button>
            <button type="button" disabled={blank || saving !== null} onClick={() => save("new")}>
              Save card
            </button>
            {loaded ? (
              <button type="button" disabled={blank || saving !== null || sameCard(card, loaded.card)} onClick={() => save("update")}>
                Update
              </button>
            ) : null}
            <button type="button" disabled={!canStart} onClick={() => actions.newRoleplay(null)}>
              Blank roleplay
            </button>
            <button type="button" className="ghost" onClick={() => actions.closeRoleplay()}>
              Cancel
            </button>
            {status ? (
              <span className="settings-status" role="status">
                {status}
              </span>
            ) : null}
          </div>
        </form>
      </section>
    </div>
  );
}
