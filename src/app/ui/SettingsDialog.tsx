// Settings (K1-13, K1-13b; FR-SET-1..3, FR-MEM-4, FR-SC-1). A dialog over the chat
// with five sections for now: Models (the Ollama address, a custom API endpoint and
// the budget, editable; the model lists read-only), Screen (the screen companions,
// now and at start), Memory (read, correct, forget, restore the remembered facts),
// Doctor (each component's state with a fix hint) and About. What is edited here is
// saved in settings.json and applies at once (D-070). Appearance is this window's own
// look, kept on this PC by the page (D-073). Voice: Read aloud (kept by the engine)
// and the dictation key (kept by the page, like Appearance) (D-097). Pet: her pet's
// behaviour and size (the page's) and Create pet (D-103). Waifus, Scenes and Advanced
// arrive with their phases.

import { Suspense, lazy, useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

import type { BudgetCaps, DoctorCheck, MemoryFact, ModelRow, ServerData, SettingsChange, SettingsData } from "../../net/protocol";
import { currentMode, modelLabel, type Companion, type SettingsSection } from "../chat-state";
import { DEFAULT_DICTATION_KEY, keyName, keyProblem } from "../dictation";
import { PICTURE_ACCEPT } from "../file-upload";
import { setDictationKey, useDictationKey } from "../dictation-key";
import { VOICE_START_S } from "../read-aloud";
import { formatSize, formatUsd } from "../models";
import { PET_SIZE_MAX, PET_SIZE_MIN, POSES, petPrompt, type Pose } from "../pet-brain";
import { actions, setPetPrefs, useChat, usePetPrefs } from "../store";
import { ACCENTS, PRESETS, applyTheme, loadTheme, saveTheme, type Preset, type Theme } from "../theme";
import { version } from "../../../package.json";
import { Icon, type IconName } from "./Icon";
import { petDraftUrl, petPoseUrl } from "./Pet";
import { Portrait } from "./Portrait";

const SECTIONS: { id: SettingsSection; label: string; icon: IconName }[] = [
  { id: "models", label: "Models", icon: "models" },
  { id: "appearance", label: "Appearance", icon: "sun" },
  { id: "pet", label: "Pet", icon: "cat" },
  { id: "voice", label: "Voice", icon: "mic" },
  { id: "screen", label: "Screen", icon: "monitor" },
  { id: "memory", label: "Memory", icon: "memory" },
  { id: "doctor", label: "Doctor", icon: "pulse" },
  { id: "about", label: "About", icon: "info" },
];

/** One setting (D-102): its name and a muted line on the left, its control on the right. */
function Row({ title, about, children }: { title: string; about?: ReactNode; children?: ReactNode }) {
  return (
    <div className="setting-row">
      <div className="setting-text">
        <strong>{title}</strong>
        {about ? <span className="muted">{about}</span> : null}
      </div>
      {children ? <div className="setting-control">{children}</div> : null}
    </div>
  );
}

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
              <Icon name={s.icon} size={17} />
              {s.label}
            </button>
          ))}
        </nav>
        <section className="settings-body">
          <button type="button" className="settings-close" aria-label="Close settings" title="Close (Esc)" onClick={() => actions.closeSettings()}>
            <Icon name="close" size={16} />
          </button>
          {section === "models" ? <ModelsSection /> : null}
          {section === "appearance" ? <AppearanceSection /> : null}
          {section === "pet" ? <PetSection /> : null}
          {section === "voice" ? <VoiceSection /> : null}
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

/** A provider's card (D-102): a status dot, its name, a muted line, and Edit opening its form. */
function ProviderCard({ name, badge, dot, about, editing, onEdit, extra, children }: {
  name: string;
  badge?: string;
  dot?: "ok" | "fail" | null;
  about: ReactNode;
  editing: boolean;
  onEdit?: () => void;
  extra?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="provider-card">
      <div className="provider-head">
        <div className="setting-text">
          <span className="provider-name">
            <strong>{name}</strong>
            {badge ? <span className="provider-badge">{badge}</span> : null}
            {dot ? <span className={`status-dot ${dot}`} aria-label={dot === "ok" ? "Working" : "Not working"} /> : null}
          </span>
          <span className="muted">{about}</span>
        </div>
        {onEdit ? (
          <button type="button" onClick={onEdit} aria-expanded={editing}>
            {editing ? "Done" : "Edit"}
          </button>
        ) : null}
        {extra}
      </div>
      {editing ? children : null}
    </div>
  );
}

function ModelsSection() {
  const models = useChat((s) => s.models);
  const prefs = useChat((s) => s.prefs);
  const defaultLabel = useChat((s) => modelLabel(s, s.defaults?.model_ref ?? s.models?.default_ref ?? null));
  const saving = useSaving();
  const [editing, setEditing] = useState<"ollama" | "custom" | null>(null);
  const toggle = (card: "ollama" | "custom") => setEditing((e) => (e === card ? null : card));
  const spend = models?.spend;
  const custom = prefs?.custom_api ?? null;
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

      <div className="provider-list">
        <ProviderCard
          name="Ollama"
          badge="On this PC"
          dot={models ? (models.local_error ? "fail" : "ok") : null}
          about={models?.local_error ?? (models ? `${models.local.length} models · ${prefs?.ollama_url ?? ""}` : "Looking for models…")}
          editing={editing === "ollama" && !!prefs}
          onEdit={prefs ? () => toggle("ollama") : undefined}
        >
          {prefs ? <OllamaForm key={prefs.ollama_url} prefs={prefs} saving={saving} /> : null}
        </ProviderCard>
        {models ? (
          <ProviderCard
            name={models.api_provider?.label ?? "API"}
            dot={models.api_key ? "ok" : "fail"}
            about={models.api_key ? `Key saved; ${models.api.length} models listed.` : "No API key. Add one with Key in the model picker."}
            editing={false}
          />
        ) : null}
        {custom ? (
          <ProviderCard
            name={custom.label}
            badge="Custom"
            about={custom.base_url}
            editing={editing === "custom"}
            onEdit={() => toggle("custom")}
            extra={
              <button type="button" className="danger-text" onClick={() => saving.save("custom", { custom_api: null })}>
                Remove
              </button>
            }
          >
            {prefs ? <CustomApiForm key={JSON.stringify(custom)} prefs={prefs} saving={saving} /> : null}
          </ProviderCard>
        ) : prefs && editing === "custom" ? (
          <div className="provider-card">
            <CustomApiForm key="new" prefs={prefs} saving={saving} />
            <button type="button" className="ghost" onClick={() => setEditing(null)}>
              Cancel
            </button>
          </div>
        ) : prefs ? (
          <button type="button" className="provider-add" onClick={() => setEditing("custom")}>
            <Icon name="plus" size={15} />
            Add your own endpoint
          </button>
        ) : null}
      </div>
      <FormStatus text={editing === null ? saving.status("custom") : null} failed={saving.failed("custom")} />

      <h4>Budget</h4>
      {spend ? (
        <p className="muted">
          {spend.enabled
            ? `This hour ${spent(spend.hour_usd, spend.hourly_cap_usd)}; today ${spent(spend.day_usd, spend.daily_cap_usd)}; this month ${spent(spend.month_usd, spend.monthly_cap_usd)}.`
            : "The budget is off: API spending is not capped."}
        </p>
      ) : null}
      {prefs ? <BudgetForm key={JSON.stringify(prefs.budget)} prefs={prefs} saving={saving} /> : null}

      {models && models.local.length > 0 ? (
        <>
          <h4>On this PC</h4>
          <ul className="settings-list">{models.local.map(row)}</ul>
        </>
      ) : null}

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
      {current ? null : <p className="settings-form-title">Your own endpoint</p>}
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
        <FormStatus text={saving.status("custom")} failed={saving.failed("custom")} />
      </div>
      <p className="muted settings-hint">
        Any OpenAI-compatible API. Save its key with Key in the model picker. Its models have no listed prices, so what they
        cost is not counted against your spending cap.
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

/** D-097: Read aloud (the engine keeps it) and the dictation key (this page keeps it). */
function VoiceSection() {
  const readAloud = useChat((s) => s.readAloud);
  const canToggle = useChat((s) => s.role === "driver" && s.connection === "online");
  const key = useDictationKey((s) => s.key);
  const [capturing, setCapturing] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  // While capturing, the next key press is the new key. Escape cancels; the capture
  // listener runs first, so neither the dialog nor a shortcut sees that press.
  useEffect(() => {
    if (!capturing) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.key === "Escape") {
        setCapturing(false);
        setProblem(null);
        return;
      }
      if (["Control", "Shift", "Alt", "Meta", "AltGraph"].includes(e.key)) return; // still choosing
      const name = keyName(e);
      const why = keyProblem(name);
      if (why) {
        setProblem(why);
        return;
      }
      setDictationKey(name as string);
      setProblem(null);
      setCapturing(false);
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [capturing]);

  return (
    <>
      <h3>Voice</h3>
      <p className="muted">
        Her voice and your speech are handled on this PC. Nothing you say is kept after it is written down.
      </p>
      <div className="setting-group">
        <Row
          title="Read aloud"
          about={`She reads each reply aloud once it is written, in chats and roleplays (in a roleplay, only what she says). Her voice takes about ${VOICE_START_S} seconds to start.`}
        >
          <label className="switch">
            <input
              type="checkbox"
              role="switch"
              checked={readAloud?.on ?? false}
              disabled={!canToggle || !readAloud}
              onChange={(e) => actions.setReadAloud(e.target.checked)}
            />
            <span className="switch-track" aria-hidden="true" />
            {readAloud?.on ? "On" : "Off"}
          </label>
        </Row>
        <Row
          title="Dictation key"
          about="Press it to start speaking and again to stop; your words go into the message box and are not sent. It works while the Kōkyū window is in front."
        >
          {capturing ? (
            <span className="key-capture" role="status">
              Press a key… (Esc to cancel)
            </span>
          ) : (
            <kbd className="key-chip">{key}</kbd>
          )}
          <button
            type="button"
            onClick={() => {
              setProblem(null);
              setCapturing((c) => !c);
            }}
          >
            {capturing ? "Cancel" : "Change…"}
          </button>
          {key !== DEFAULT_DICTATION_KEY && !capturing ? (
            <button type="button" className="ghost" onClick={() => setDictationKey(DEFAULT_DICTATION_KEY)}>
              Use {DEFAULT_DICTATION_KEY}
            </button>
          ) : null}
        </Row>
      </div>
      <FormStatus text={problem} failed />
    </>
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
      <div className="setting-group">
        {SCREEN_MODES.map((m) => (
          <Row key={m.mode} title={m.label} about={m.about}>
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
          </Row>
        ))}
      </div>
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
      <div className="setting-group doctor">
        {(checks ?? []).map((c) => (
          <Row
            key={c.id}
            title={c.label}
            about={
              <>
                {c.detail}
                {c.hint ? <span className="doctor-hint">{c.hint}</span> : null}
              </>
            }
          >
            <span className={`doctor-state doctor-${c.state}`}>{STATE_LABEL[c.state]}</span>
          </Row>
        ))}
      </div>
      <button type="button" onClick={() => actions.runDoctor()}>
        Check again
      </button>
    </>
  );
}

/** One row of choices; the picked one is pressed. */
function Choices<T extends string>({ label, value, options, onPick }: {
  label: string;
  value: T;
  options: { id: T; label: string }[];
  onPick: (id: T) => void;
}) {
  return (
    <div className="settings-choices" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.id} type="button" aria-pressed={o.id === value} onClick={() => onPick(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

// three.js loads only when the picture viewer opens.
const PictureViewer = lazy(() => import("./PictureViewer").then((m) => ({ default: m.PictureViewer })));

const POSE_LABELS: Record<Pose, string> = {
  idle: "Idle",
  walk_1: "Walk 1",
  walk_2: "Walk 2",
  sit: "Sit",
  sleep: "Sleep",
  eat: "Eat",
  wave: "Wave",
  think: "Think",
  talk: "Talk",
  happy: "Happy",
  sad: "Sad",
  surprised: "Surprised",
};

/** D-103 (FR-P-1..3): her pet's behaviour and size, and Create pet. */
function PetSection() {
  const prefs = usePetPrefs();
  const companion = useChat((s) => s.companion);
  const roster = useChat((s) => s.roster);
  const online = useChat((s) => s.connection === "online");
  const draft = useChat((s) => s.petDraft);
  const name = companion?.name ?? "her";
  // A list of the characters: whose new pet to make, or whom to switch to (D-110).
  const [picking, setPicking] = useState<"new" | "switch" | null>(null);
  const roleplay = useChat((s) => currentMode(s) === "roleplay");
  const [making, setMaking] = useState<string | null>(null);
  const hadDraft = useRef(false);
  useEffect(() => {
    if (hadDraft.current && !draft) setMaking(null);   // saved or cancelled: back to her pet
    hadDraft.current = draft !== null;
  }, [draft]);
  const targetId = draft?.waifu_id ?? making;
  const target = targetId ? (roster.find((c) => c.id === targetId) ?? null) : null;
  return (
    <>
      <h3>Pet</h3>
      <p className="muted">A chibi {name} walking along the bottom of the chat while you talk. The cat button beside her name shows or hides it.</p>
      <div className="setting-group">
        <Row title="Show the pet" about="In chats and roleplays, while this companion is active.">
          <label className="switch">
            <input type="checkbox" role="switch" checked={prefs.show} onChange={(e) => setPetPrefs({ show: e.target.checked })} />
            <span className="switch-track" aria-hidden="true" />
          </label>
        </Row>
        <Row title="Behaviour" about="Roam walks, sits and eats; she naps after a long quiet.">
          <Choices
            label="Behaviour"
            value={prefs.mode}
            options={[
              { id: "roam", label: "Roam" },
              { id: "stay", label: "Stay put" },
              { id: "sleep", label: "Sleep" },
            ]}
            onPick={(mode) => setPetPrefs({ mode })}
          />
        </Row>
        <Row title="Size">
          <input
            type="range"
            className="pet-size"
            min={PET_SIZE_MIN}
            max={PET_SIZE_MAX}
            step={5}
            value={prefs.size}
            aria-label="Pet size"
            onChange={(e) => setPetPrefs({ size: Number(e.target.value) })}
          />
          <span className="pet-size-value">{prefs.size}%</span>
        </Row>
      </div>

      {target ? (
        <>
          <h4>{draft ? `Check ${target.name}'s new pet` : `Make ${target.name}'s pet`}</h4>
          {draft ? null : (
            <button type="button" className="ghost pet-back" onClick={() => setMaking(null)}>
              Back
            </button>
          )}
          <CreatePet id={target.id} name={target.name} online={online} draft={draft} own={target.petOwn ?? false} has={!!target.pet} />
        </>
      ) : picking ? (
        <>
          <h4>{picking === "new" ? "Make a new pet" : "Switch character"}</h4>
          <p className="muted">
            {picking === "new" ? "Whose pet? Each character has one; making a new one replaces theirs." : "Talk to someone else; their pet comes with them."}
          </p>
          <ul className="pet-pick">
            {roster.map((c) => {
              const current = picking === "switch" && c.id === companion?.id;
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    disabled={current}
                    onClick={() => {
                      if (picking === "new") setMaking(c.id);
                      else actions.switchWaifu(c.id);
                      setPicking(null);
                    }}
                  >
                    <Portrait id={c.id} name={c.name} portrait={c.portrait ?? null} className="pet-pick-face" />
                    <span>{c.name}</span>
                    <span className="muted">{current ? "Talking now" : c.pet ? "Has a pet" : "No pet yet"}</span>
                  </button>
                </li>
              );
            })}
          </ul>
          {picking === "new" ? (
            <p className="settings-hint">Want a different pet entirely, not one of these characters? Make a new character first, then make its pet here.</p>
          ) : null}
          <button type="button" className="ghost pet-back" onClick={() => setPicking(null)}>
            Cancel
          </button>
        </>
      ) : (
        <ActivePet
          companion={companion}
          name={name}
          online={online}
          onNew={() => setPicking("new")}
          onSwitch={roleplay || roster.length < 2 ? null : () => setPicking("switch")}
        />
      )}
    </>
  );
}

function ActivePet({ companion, name, online, onNew, onSwitch }: {
  companion: Companion | null;
  name: string;
  online: boolean;
  onNew: () => void;
  /** null in a roleplay (she stays for the story, D-101) or with no one else to switch to. */
  onSwitch: (() => void) | null;
}) {
  return (
    <>
      <h4>{companion?.pet ? `${name}'s pet` : `Create ${name}'s pet`}</h4>
      {companion?.pet ? (
        <div className="pet-poses">
          {(companion.petPoses ?? []).map((pose) => (
            <figure key={pose}>
              <img src={petPoseUrl(companion.id, pose, companion.pet ?? "")} alt="" />
              <figcaption>{POSE_LABELS[pose as Pose] ?? pose}</figcaption>
            </figure>
          ))}
        </div>
      ) : null}
      {companion ? <CreatePet id={companion.id} name={name} online={online} draft={null} own={companion.petOwn ?? false} has={!!companion.pet} /> : null}
      <div className="pet-actions pet-more">
        {onSwitch ? (
          <button type="button" className="pet-new" onClick={onSwitch}>
            Switch character
          </button>
        ) : null}
        <button type="button" className="pet-new" onClick={onNew}>
          Make a new pet
        </button>
      </div>
    </>
  );
}

function CreatePet({ id, name, online, draft, own, has }: {
  id: string;
  name: string;
  online: boolean;
  draft: ServerData["pet_draft"] | null;
  own: boolean;
  has: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [viewer, setViewer] = useState(false);
  const closeViewer = useCallback(() => setViewer(false), []);
  const [labels, setLabels] = useState<(Pose | null)[]>([]);

  useEffect(() => {
    // A new sheet: each cell that holds a pose starts with its place in the grid.
    setLabels(draft ? draft.cells.map((full, n) => (full ? POSES[n] : null)) : []);
  }, [draft]);

  const copy = () => {
    void navigator.clipboard.writeText(petPrompt(name)).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    });
  };
  const used = labels.filter((l): l is Pose => l !== null);
  const repeated = used.length !== new Set(used).size;

  if (draft) {
    return (
      <div className="pet-steps">
        <p className="muted">Check each pose and fix any label that is wrong. A cell set to Leave out is not used.</p>
        <div className="pet-cells">
          {draft.cells.map((full, n) =>
            full ? (
              <figure key={n}>
                <img src={petDraftUrl(id, n, draft.stamp)} alt={`Cell ${n + 1}`} />
                <select
                  aria-label={`Cell ${n + 1}`}
                  value={labels[n] ?? ""}
                  onChange={(e) => setLabels((old) => old.map((l, i) => (i === n ? ((e.target.value || null) as Pose | null) : l)))}
                >
                  <option value="">Leave out</option>
                  {POSES.map((p) => (
                    <option key={p} value={p}>
                      {POSE_LABELS[p]}
                    </option>
                  ))}
                </select>
              </figure>
            ) : null,
          )}
        </div>
        {repeated ? <p className="settings-hint pet-warn">Each pose can be used once.</p> : null}
        <div className="pet-actions">
          <button type="button" className="ghost" onClick={() => actions.dropPetDraft()}>
            Cancel
          </button>
          <button type="button" disabled={!online || repeated || used.length === 0} onClick={() => actions.savePet(id, labels)}>
            Save pet
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="pet-steps">
      <ol>
        <li>
          <span>Copy the prompt and paste it into an image model that makes pictures, such as ChatGPT.</span>
          <button type="button" onClick={copy}>
            {copied ? "Copied" : "Copy prompt"}
          </button>
        </li>
        <li>
          <span>Add a picture of {name}: take one of her model, then copy or save it.</span>
          <button type="button" onClick={() => setViewer(true)}>
            Take her picture
          </button>
          {viewer ? (
            <Suspense fallback={null}>
              <PictureViewer id={id} name={name} onClose={closeViewer} />
            </Suspense>
          ) : null}
        </li>
        <li>
          <span>Save the sheet it draws and upload it here. Kōkyū cuts out the twelve poses for you to check.</span>
          <label className={online ? "pet-upload" : "pet-upload disabled"}>
            Upload the sheet
            <input
              type="file"
              accept={PICTURE_ACCEPT}
              disabled={!online}
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void actions.sendPetSheet(id, file);
              }}
            />
          </label>
        </li>
      </ol>
      {has && own ? (
        <button type="button" className="danger-text" onClick={() => actions.removePet(id)}>
          Remove this pet
        </button>
      ) : null}
    </div>
  );
}

function AppearanceSection() {
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const change = (patch: Partial<Theme>) => {
    const next = { ...theme, ...patch };
    setTheme(next);
    saveTheme(next);
    applyTheme(next);
  };
  const accent = theme.accent ?? PRESETS[theme.preset].vars["--accent"];
  return (
    <>
      <h3>Appearance</h3>
      <p className="muted">How this window looks. Saved on this PC for every Kōkyū window.</p>
      <div className="setting-group">
        <div className="setting-row stacked">
          <div className="setting-text">
            <strong>Theme</strong>
          </div>
          <div className="theme-cards" role="group" aria-label="Theme">
            {(Object.keys(PRESETS) as Preset[]).map((id) => (
              <button key={id} type="button" aria-pressed={theme.preset === id} onClick={() => change({ preset: id })}>
                <span className="theme-sample" style={{ background: PRESETS[id].vars["--bg"], borderColor: PRESETS[id].vars["--line"] }}>
                  <span style={{ background: PRESETS[id].vars["--panel"] }} />
                  <span style={{ background: PRESETS[id].vars["--accent"] }} />
                </span>
                {PRESETS[id].label}
              </button>
            ))}
          </div>
        </div>
        <Row title="Accent color" about="Buttons, links and highlights.">
          <div className="settings-choices accents" role="group" aria-label="Accent color">
            <button type="button" aria-pressed={theme.accent === null} onClick={() => change({ accent: null })}>
              The theme's own
            </button>
            {ACCENTS.map((c) => (
              <button
                key={c}
                type="button"
                className="swatch"
                style={{ background: c }}
                aria-pressed={theme.accent === c}
                aria-label={`Accent ${c}`}
                onClick={() => change({ accent: c })}
              />
            ))}
            <label className="swatch custom" title="Any color">
              <input type="color" value={accent} aria-label="Pick any accent color" onChange={(e) => change({ accent: e.target.value.toLowerCase() })} />
            </label>
          </div>
        </Row>
        <Row title="Messages" about="Her replies as open text, or in bubbles.">
          <Choices
            label="Messages"
            value={theme.messages}
            options={[
              { id: "open", label: "Open" },
              { id: "bubbles", label: "Bubbles" },
            ]}
            onPick={(messages) => change({ messages })}
          />
        </Row>
        <Row title="Text size" about="Only the conversation's text.">
          <Choices
            label="Text size"
            value={theme.size}
            options={[
              { id: "small", label: "Small" },
              { id: "normal", label: "Normal" },
              { id: "large", label: "Large" },
            ]}
            onPick={(size) => change({ size })}
          />
        </Row>
      </div>
    </>
  );
}

function AboutSection() {
  return (
    <>
      <h3>About</h3>
      <p>Kōkyū {version}: AI companions on your PC.</p>
      <p className="muted">
        Engine: KASANE. Kasane (重ね) are the layered robes of the Heian court; the engine layers each companion's
        persona, the conversation's mode and her voice.
      </p>
      <p className="muted">
        Your chats, memory and settings stay on this PC. Camera frames, microphone audio and screen captures never leave it;
        a message goes to an API model only when you pick one.
      </p>
      <p className="muted">Proprietary software. All rights reserved.</p>
    </>
  );
}
