// Settings (K1-13; FR-SET-1, FR-SET-3, FR-MEM-4). A dialog over the chat with
// four sections for now: Models (what the kernel runs, read-only), Memory (read,
// correct, forget, restore the remembered facts), Doctor (each component's state
// with a fix hint) and About. Voice, Waifus, Scenes, Pets and Advanced arrive
// with their phases; editing settings in the app comes with settings.json.

import { useEffect, useState, type KeyboardEvent } from "react";

import type { DoctorCheck, MemoryFact, ModelRow } from "../../net/protocol";
import { modelLabel, type SettingsSection } from "../chat-state";
import { formatSize, formatUsd } from "../models";
import { actions, useChat } from "../store";

const SECTIONS: { id: SettingsSection; label: string }[] = [
  { id: "models", label: "Models" },
  { id: "memory", label: "Memory" },
  { id: "doctor", label: "Doctor" },
  { id: "about", label: "About" },
];

export function SettingsDialog() {
  const section = useChat((s) => s.settings);

  useEffect(() => {
    if (!section) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") actions.closeSettings();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [section]);

  if (!section) return null;
  return (
    <div className="settings-backdrop" onMouseDown={(e) => e.target === e.currentTarget && actions.closeSettings()}>
      <div className="settings-dialog" role="dialog" aria-modal="true" aria-label="Settings">
        <nav className="settings-nav" aria-label="Settings sections">
          <h2>Settings</h2>
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={s.id === section ? "current" : undefined}
              aria-current={s.id === section ? "page" : undefined}
              onClick={() => actions.openSettings(s.id)}
            >
              {s.label}
            </button>
          ))}
        </nav>
        <section className="settings-body">
          <button type="button" className="settings-close ghost" aria-label="Close settings" onClick={() => actions.closeSettings()}>
            ✕
          </button>
          {section === "models" ? <ModelsSection /> : null}
          {section === "memory" ? <MemorySection /> : null}
          {section === "doctor" ? <DoctorSection /> : null}
          {section === "about" ? <AboutSection /> : null}
        </section>
      </div>
    </div>
  );
}

/** "$0.25 of $1.50", or "$0.25 (no cap)" for an unlimited cap. */
function spent(value: number | null | undefined, cap: number | null | undefined): string {
  const used = formatUsd(value ?? 0);
  return cap == null ? `${used} (no cap)` : `${used} of ${formatUsd(cap)}`;
}

function ModelsSection() {
  const models = useChat((s) => s.models);
  const defaultLabel = useChat((s) => modelLabel(s, s.defaults?.model_ref ?? s.models?.default_ref ?? null));
  if (!models) return <p className="muted">Asking the kernel…</p>;
  const spend = models.spend;
  const row = (r: ModelRow) => (
    <li key={r.ref}>
      <span>{r.label}</span>
      <span className="muted">{[r.detail, formatSize(r.size_bytes)].filter(Boolean).join(" · ")}</span>
    </li>
  );
  return (
    <>
      <h3>Models</h3>
      <p className="muted">
        New chats use <strong>{defaultLabel}</strong>. Pick a model for a chat with the chip
        under the message box. Change these defaults in <code>config/config.yaml</code> for now.
      </p>
      <h4>On this PC</h4>
      {models.local_error ? <p className="muted">{models.local_error}</p> : null}
      <ul className="settings-list">{models.local.map(row)}</ul>
      <h4>API {models.api_provider ? `· ${models.api_provider.label}` : ""}</h4>
      <p className="muted">
        {models.api_key ? `Key saved; ${models.api.length} models listed.` : "No API key. Add one with Key in the model picker."}
      </p>
      {spend ? (
        <>
          <h4>Budget</h4>
          <p className="muted">
            {spend.enabled
              ? `This hour ${spent(spend.hour_usd, spend.hourly_cap_usd)}; today ${spent(spend.day_usd, spend.daily_cap_usd)}; this month ${spent(spend.month_usd, spend.monthly_cap_usd)}.`
              : "The budget is off: API spending is not capped."}
          </p>
        </>
      ) : null}
    </>
  );
}

function MemorySection() {
  const facts = useChat((s) => s.memory);
  if (!facts) return <p className="muted">Reading memory…</p>;
  const live = facts.filter((f) => !f.forgotten);
  const gone = facts.filter((f) => f.forgotten);
  return (
    <>
      <h3>Memory</h3>
      <p className="muted">
        What your companions remember about you. Every companion shares it. Correct a fact in your own words, or forget
        it; forgotten facts can come back.
      </p>
      {live.length === 0 ? <p className="muted">Nothing remembered yet.</p> : null}
      <ul className="settings-list facts">
        {live.map((f) => (
          <Fact key={f.id} fact={f} />
        ))}
      </ul>
      {gone.length > 0 ? (
        <details className="forgotten">
          <summary>Forgotten ({gone.length})</summary>
          <ul className="settings-list facts">
            {gone.map((f) => (
              <li key={f.id}>
                <span className="fact-text">{f.content}</span>
                <button type="button" onClick={() => actions.restoreFact(f.id)}>
                  Restore
                </button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </>
  );
}

function Fact({ fact }: { fact: MemoryFact }) {
  const [draft, setDraft] = useState<string | null>(null);
  const save = () => {
    if (draft !== null && draft.trim() && draft.trim() !== fact.content) actions.correctFact(fact.id, draft.trim());
    setDraft(null);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      save();
    } else if (e.key === "Escape") {
      e.stopPropagation();
      setDraft(null);
    }
  };
  if (draft !== null) {
    return (
      <li className="editing">
        <textarea aria-label="Correct this fact" value={draft} autoFocus onChange={(e) => setDraft(e.target.value)} onKeyDown={onKey} />
        <button type="button" onClick={save}>
          Save
        </button>
        <button type="button" className="ghost" onClick={() => setDraft(null)}>
          Cancel
        </button>
      </li>
    );
  }
  return (
    <li>
      <span className="fact-text">{fact.content}</span>
      <button type="button" onClick={() => setDraft(fact.content)}>
        Correct
      </button>
      <button type="button" onClick={() => actions.forgetFact(fact.id)}>
        Forget
      </button>
    </li>
  );
}

const STATE_LABEL: Record<DoctorCheck["state"], string> = { ok: "OK", warn: "Check", fail: "Problem", off: "Off" };

function DoctorSection() {
  const checks = useChat((s) => s.doctor);
  return (
    <>
      <h3>Doctor</h3>
      <p className="muted">Each part Kōkyū needs, whether it works, and how to fix it if not.</p>
      {!checks ? <p className="muted">Checking…</p> : null}
      <ul className="settings-list doctor">
        {(checks ?? []).map((c) => (
          <li key={c.id} className={`doctor-${c.state}`}>
            <span className="doctor-state">{STATE_LABEL[c.state]}</span>
            <span className="doctor-main">
              <strong>{c.label}</strong>
              <span className="muted">{c.detail}</span>
              {c.hint ? <span className="doctor-hint">{c.hint}</span> : null}
            </span>
          </li>
        ))}
      </ul>
      <button type="button" onClick={() => actions.runDoctor()}>
        Check again
      </button>
    </>
  );
}

function AboutSection() {
  return (
    <>
      <h3>About</h3>
      <p>Kōkyū: AI companions on your PC.</p>
      <p className="muted">
        Your chats, memory and settings stay on this PC. Camera frames, microphone audio and screen captures never leave it;
        a message goes to an API model only when you pick one.
      </p>
      <p className="muted">Proprietary software. All rights reserved.</p>
    </>
  );
}
