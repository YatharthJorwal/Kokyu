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
  const saveState = useChat((s) => s.scenarioSave);
  const startState = useChat((s) => s.roleplayStart);
  const starting = startState === "pending";
  const canStart = useChat(canStartThread) && !starting;
  const companion = useChat((s) => s.companion?.name ?? null);
  const [form, setForm] = useState<ScenarioForm>(EMPTY_FORM);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  // A save waits for its own answer (the store's scenarioSave): the list naming the
  // saved card, or a store error. No other list counts, so Update can only ever
  // point at the card this form was saved as.
  const saving = saveState === "pending";
  const [status, setStatus] = useState<string | null>(null);
  const firstField = useRef<HTMLInputElement>(null);
  // Escape backs out of a delete confirm first; only with none open does it close
  // the dialog (and the form with it).
  const confirmingNow = useRef(confirming);
  confirmingNow.current = confirming;

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (confirmingNow.current !== null) setConfirming(null);
      else actions.closeRoleplay();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const loaded = scenarios?.find((c) => c.id === loadedId) ?? null;
  const card = cardFromForm(form);
  const blank = isBlankCard(card);

  useEffect(() => {
    firstField.current?.focus();
  }, []);

  useEffect(() => {
    if (saveState === "failed") {
      setStatus("Could not save the card.");
    } else if (saveState === "lost") {
      setStatus("The connection dropped before Kōkyū answered, so the card may not be saved. Check the list once it is back.");
    } else if (saveState !== null && saveState !== "pending") {
      setLoadedId(saveState.saved);
      setStatus("Saved.");
    }
  }, [saveState]);

  useEffect(() => {
    if (startState === "pending") setStatus("Starting…");
    else if (startState !== null) setStatus(`Could not start the roleplay. ${startState.failed}`);
  }, [startState]);

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
    if (sent) setStatus("Saving…");
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
                  <button type="button" className="danger" disabled={saving} onClick={() => remove(c.id)}>
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
                <button
                  type="button"
                  className="card-delete"
                  aria-label={`Delete ${c.title}`}
                  title="Delete"
                  disabled={saving}
                  onClick={() => setConfirming(c.id)}
                >
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
            <button type="button" disabled={blank || saving} onClick={() => save("new")}>
              Save card
            </button>
            {loaded ? (
              <button type="button" disabled={blank || saving || sameCard(card, loaded.card)} onClick={() => save("update")}>
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
