// Settings (K1-13, K1-13b; FR-SET-1..3, FR-MEM-4, FR-SC-1). A dialog over the chat
// with five sections for now: Models (the Ollama address, a custom API endpoint and
// the budget, editable; the model lists read-only), Screen (the screen companions,
// now and at start), Memory (read, correct, forget, restore the remembered facts),
// Doctor (each component's state with a fix hint) and About. What is edited here is
// saved in settings.json and applies at once (D-070). Voice, Waifus, Scenes, Pets
// and Advanced arrive with their phases.

import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";

import type { BudgetCaps, DoctorCheck, MemoryFact, ModelRow, SettingsChange, SettingsData } from "../../net/protocol";
import { modelLabel, type SettingsSection } from "../chat-state";
import { formatSize, formatUsd } from "../models";
import { actions, useChat } from "../store";

const SECTIONS: { id: SettingsSection; label: string }[] = [
  { id: "models", label: "Models" },
  { id: "screen", label: "Screen" },
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
          {section === "screen" ? <ScreenSection /> : null}
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

type FormName = "ollama" | "custom" | "budget" | "screen";

/** Which form was saved last and whether its answer is back: the kernel's `settings`
 * frame answers every save, with `problem` set when it refused the change. */
function useSaving() {
  const prefs = useChat((s) => s.prefs);
  const [asked, setAsked] = useState<{ form: FormName; prefs: SettingsData | null } | null>(null);
  const save = (form: FormName, change: SettingsChange) => {
    if (actions.saveSettings(change)) setAsked({ form, prefs });
  };
  const status = (form: FormName): string | null => {
    if (asked?.form !== form) return null;
    if (prefs === asked.prefs) return "Saving…";
    return prefs?.problem ?? "Saved.";
  };
  return { save, status, failed: (form: FormName) => asked?.form === form && prefs !== asked.prefs && !!prefs?.problem };
}

function FormStatus({ text, failed }: { text: string | null; failed: boolean }) {
  if (!text) return null;
  return (
    <span className={failed ? "settings-status failed" : "settings-status"} role={failed ? "alert" : "status"}>
      {text}
    </span>
  );
}

function ModelsSection() {
  const models = useChat((s) => s.models);
  const prefs = useChat((s) => s.prefs);
  const defaultLabel = useChat((s) => modelLabel(s, s.defaults?.model_ref ?? s.models?.default_ref ?? null));
  const saving = useSaving();
  const spend = models?.spend;
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
        New chats use <strong>{defaultLabel}</strong>. Pick a model for a chat with the chip under the message box. The
        default model and the llama.cpp presets are set in <code>config/config.yaml</code>.
      </p>

      <h4>On this PC</h4>
      {prefs ? <OllamaForm key={prefs.ollama_url} prefs={prefs} saving={saving} /> : null}
      {!models ? <p className="muted">Asking the kernel…</p> : null}
      {models?.local_error ? <p className="muted">{models.local_error}</p> : null}
      <ul className="settings-list">{(models?.local ?? []).map(row)}</ul>

      <h4>API {models?.api_provider ? `· ${models.api_provider.label}` : ""}</h4>
      {models ? (
        <p className="muted">
          {models.api_key ? `Key saved; ${models.api.length} models listed.` : "No API key. Add one with Key in the model picker."}
        </p>
      ) : null}
      {prefs ? <CustomApiForm key={JSON.stringify(prefs.custom_api)} prefs={prefs} saving={saving} /> : null}

      <h4>Budget</h4>
      {spend ? (
        <p className="muted">
          {spend.enabled
            ? `This hour ${spent(spend.hour_usd, spend.hourly_cap_usd)}; today ${spent(spend.day_usd, spend.daily_cap_usd)}; this month ${spent(spend.month_usd, spend.monthly_cap_usd)}.`
            : "The budget is off: API spending is not capped."}
        </p>
      ) : null}
      {prefs ? <BudgetForm key={JSON.stringify(prefs.budget)} prefs={prefs} saving={saving} /> : null}

      {prefs ? <p className="muted settings-file">Your changes here are saved in {prefs.file}.</p> : null}
    </>
  );
}

type Saving = ReturnType<typeof useSaving>;

function OllamaForm({ prefs, saving }: { prefs: SettingsData; saving: Saving }) {
  const [url, setUrl] = useState(prefs.ollama_url);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    saving.save("ollama", { ollama_url: url.trim() });
  };
  return (
    <form className="settings-form" onSubmit={submit}>
      <label className="settings-field">
        <span>Ollama address</span>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://127.0.0.1:11434" inputMode="url" spellCheck={false} />
      </label>
      <div className="settings-actions">
        <button type="submit" disabled={!url.trim() || url.trim() === prefs.ollama_url}>
          Save
        </button>
        {prefs.saved.includes("ollama_url") ? (
          <button type="button" className="ghost" onClick={() => saving.save("ollama", { ollama_url: "" })}>
            Use the default
          </button>
        ) : null}
        <FormStatus text={saving.status("ollama")} failed={saving.failed("ollama")} />
      </div>
    </form>
  );
}

function CustomApiForm({ prefs, saving }: { prefs: SettingsData; saving: Saving }) {
  const current = prefs.custom_api;
  const [label, setLabel] = useState(current?.label ?? "");
  const [url, setUrl] = useState(current?.base_url ?? "");
  const changed = label.trim() !== (current?.label ?? "") || url.trim() !== (current?.base_url ?? "");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    saving.save("custom", { custom_api: { label: label.trim(), base_url: url.trim() } });
  };
  return (
    <form className="settings-form" onSubmit={submit}>
      <p className="settings-form-title">Your own endpoint</p>
      <div className="settings-row">
        <label className="settings-field narrow">
          <span>Name</span>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="My endpoint" maxLength={40} />
        </label>
        <label className="settings-field">
          <span>Address</span>
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/v1" inputMode="url" spellCheck={false} />
        </label>
      </div>
      <div className="settings-actions">
        <button type="submit" disabled={!label.trim() || !url.trim() || !changed}>
          Save
        </button>
        {current ? (
          <button type="button" className="ghost" onClick={() => saving.save("custom", { custom_api: null })}>
            Remove
          </button>
        ) : null}
        <FormStatus text={saving.status("custom")} failed={saving.failed("custom")} />
      </div>
      <p className="muted settings-hint">
        Any OpenAI-compatible API. Save its key with Key in the model picker. Its models have no listed prices, so they run
        only while the budget is off.
      </p>
    </form>
  );
}

const CAPS: { key: keyof Omit<BudgetCaps, "enabled">; label: string }[] = [
  { key: "hourly_usd", label: "Per hour (USD)" },
  { key: "daily_usd", label: "Per day (USD)" },
  { key: "monthly_usd", label: "Per month (USD)" },
];

function BudgetForm({ prefs, saving }: { prefs: SettingsData; saving: Saving }) {
  const [enabled, setEnabled] = useState(prefs.budget.enabled);
  const [caps, setCaps] = useState(() => CAPS.map((c) => (prefs.budget[c.key] == null ? "" : String(prefs.budget[c.key]))));
  // An empty box is no cap; anything else must read as a number, or a typo would lift the cap.
  const values = caps.map((v) => (v.trim() === "" ? null : Number(v.trim())));
  const unreadable = values.some((v) => v !== null && !Number.isFinite(v));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (unreadable) return;
    const [hourly_usd, daily_usd, monthly_usd] = values as (number | null)[];
    saving.save("budget", { budget: { enabled, hourly_usd: hourly_usd ?? null, daily_usd: daily_usd ?? null, monthly_usd: monthly_usd ?? null } });
  };
  return (
    <form className="settings-form" onSubmit={submit}>
      <label className="switch">
        <input type="checkbox" role="switch" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        <span className="switch-track" aria-hidden="true" />
        Cap API spending
      </label>
      <div className="settings-row">
        {CAPS.map((c, i) => (
          <label key={c.key} className="settings-field money">
            <span>{c.label}</span>
            <input
              value={caps[i]}
              disabled={!enabled}
              inputMode="decimal"
              placeholder="no cap"
              onChange={(e) => setCaps(caps.map((v, j) => (j === i ? e.target.value : v)))}
            />
          </label>
        ))}
      </div>
      <div className="settings-actions">
        <button type="submit" disabled={unreadable}>
          Save
        </button>
        <FormStatus
          text={unreadable ? "Enter an amount in dollars, or leave it empty for no cap." : saving.status("budget")}
          failed={unreadable || saving.failed("budget")}
        />
      </div>
      <p className="muted settings-hint">A cap of 0 means no API spending at all. Empty means no cap.</p>
    </form>
  );
}

const SCREEN_MODES: { mode: "task_guide" | "ocr_watch"; label: string; about: string }[] = [
  { mode: "task_guide", label: "Task Guide", about: "Keeps track of the task you name and nudges you when you drift from it." },
  { mode: "ocr_watch", label: "OCR watch", about: "Now and then, a short remark about what is on your screen." },
];

function ScreenSection() {
  const screen = useChat((s) => s.screen);
  const prefs = useChat((s) => s.prefs);
  const canToggle = useChat((s) => s.role === "driver" && s.connection === "online");
  // A refusal (no local vision model, FR-SC-3) is a notice in the chat, hidden behind this dialog.
  const refused = useChat((s) => (s.notice?.code === "vision_unavailable" ? s.notice.text : null));
  const saving = useSaving();
  return (
    <>
      <h3>Screen</h3>
      <p className="muted">
        Screen companions look at your screen with a local model that can see images. What they see never leaves this PC.
        A chip under the message box shows while one is on.
      </p>
      <ul className="settings-list screen">
        {SCREEN_MODES.map((m) => (
          <li key={m.mode}>
            <span className="doctor-main">
              <strong>{m.label}</strong>
              <span className="muted">{m.about}</span>
            </span>
            <label className="switch">
              <input
                type="checkbox"
                role="switch"
                checked={screen?.[m.mode].on ?? false}
                disabled={!canToggle || !screen}
                onChange={(e) => actions.setScreenCompanion(m.mode, e.target.checked)}
              />
              <span className="switch-track" aria-hidden="true" />
              On now
            </label>
            <label className="switch">
              <input
                type="checkbox"
                role="switch"
                checked={prefs?.screen[m.mode] ?? false}
                disabled={!prefs}
                onChange={(e) => saving.save("screen", { screen: { [m.mode]: e.target.checked } })}
              />
              <span className="switch-track" aria-hidden="true" />
              On at start
            </label>
          </li>
        ))}
      </ul>
      <FormStatus text={refused ?? (saving.failed("screen") ? saving.status("screen") : null)} failed />
      <p className="muted settings-hint">Both start off unless you set them to start with Kōkyū.</p>
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
