// The one model control (K1-10; FR-M-1, 2, 4, 5, 6, 7): a chip in the input row
// with a local or cloud icon, the model's name and the effort label. It opens a
// popover with a search box and Local and API sections as one list; the current
// model has a check mark and picking a row is the whole action. While the kernel
// loads the model the chip shows a spinner; a failed load shows a warning.
// The effort slider sits under the list, with the levels the model offers
// (FR-M-8..11); while a reply is generating, its glow runs on the chip.
// Local rows carry the VRAM manager's fits / won't fit hint (K1-09, FR-M-3).
// K1-15 (D-068): the chip sits under the input box; each row is one line (name,
// size or price, fits, badges) with the backend's detail in its tooltip, and the
// footer says what was spent today.

import { invoke, isTauri } from "@tauri-apps/api/core";
import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import type { Effort, ModelListData, ModelRow, Spend } from "../../net/protocol";
import {
  canPickModel,
  currentEffort,
  currentEfforts,
  currentModelRef,
  modelLabel,
  modelRow,
  shownEffort as chipEffort,
} from "../chat-state";
import { glowFor } from "../effort-slider";
import {
  MODEL_ORDERS,
  badgesFor,
  companiesOf,
  effortLabel,
  filterCompanies,
  filterRows,
  formatSize,
  formatUsd,
  isLocalRef,
  modelFacts,
  parsePickerPrefs,
  sortRows,
  type ModelOrder,
  type PickerPrefs,
} from "../models";
import { actions, useChat } from "../store";
import { ContextSlider } from "./ContextSlider";
import { EffortSlider } from "./EffortSlider";

function KindIcon({ local }: { local: boolean }) {
  return local ? (
    // a small computer: runs on this PC
    <svg className="kind-icon" viewBox="0 0 16 16" aria-label="Runs on this PC" role="img">
      <rect x="2" y="3" width="12" height="8" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M6 13.5h4M8 11v2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ) : (
    // a cloud: an API model
    <svg className="kind-icon" viewBox="0 0 16 16" aria-label="API model" role="img">
      <path
        d="M4.5 12.5h7a3 3 0 0 0 .3-6 4 4 0 0 0-7.6 1A2.5 2.5 0 0 0 4.5 12.5z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ModelChip() {
  const ref = useChat(currentModelRef);
  const label = useChat((s) => modelLabel(s, currentModelRef(s)));
  const row = useChat((s) => modelRow(s, currentModelRef(s)));
  const shownEffort = useChat(chipEffort);
  const status = useChat((s) => s.modelStatus);
  const open = useChat((s) => s.pickerOpen);
  const enabled = useChat(canPickModel);
  const turn = useChat((s) => s.turn);
  const wrapper = useRef<HTMLDivElement>(null);

  const loading = status?.state === "loading" && status.model_ref === ref;
  const failed = status?.state === "failed" && status.model_ref === ref;
  // Idle, the hover card says what the model is (D-084); these say why the chip is busy.
  const title = loading
    ? `Loading ${label}…`
    : failed
      ? `${label} failed to load: ${status?.message ?? "unknown error"}`
      : turn !== "idle"
        ? "Switch models after the reply"
        : undefined;
  const full = row?.full ?? ref;
  const facts = row ? modelFacts(row) : "";
  const tip = !title && !open && full;

  // A click anywhere outside the chip and its popover closes it.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      // The in-app confirm (removing a key) sits on top of it: answering it is not "outside".
      if ((e.target as Element).closest?.(".confirm-layer")) return;
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) actions.closePicker();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // FR-M-9: while a reply is generating, the effort's glow runs on the chip.
  const glow = glowFor(shownEffort);
  const generating = turn !== "idle" && glow.intensity > 0;
  const glowStyle = generating
    ? ({ "--effort-glow": glow.intensity, "--effort-period": `${glow.periodS}s` } as CSSProperties)
    : undefined;

  const classes = [
    "model-chip",
    loading ? "loading" : "",
    failed ? "failed" : "",
    open ? "open" : "",
    generating ? "generating" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="model-picker" ref={wrapper}>
      <button
        type="button"
        className={classes}
        style={glowStyle}
        title={title}
        aria-label={`Model: ${label}`}
        aria-describedby={tip ? "model-tip" : undefined}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={!enabled && !open}
        onClick={() => (open ? actions.closePicker() : actions.openPicker())}
      >
        <KindIcon local={isLocalRef(ref)} />
        <span className="model-name">{label}</span>
        {shownEffort ? <span className="effort-label">{effortLabel(shownEffort)}</span> : null}
        {loading ? <span className="spinner" aria-hidden="true" /> : null}
        {failed ? (
          <span className="warn" aria-label="Failed to load">
            !
          </span>
        ) : null}
        <span className="caret" aria-hidden="true">
          ▾
        </span>
      </button>
      {tip ? (
        <div className="model-tip" id="model-tip" role="tooltip">
          <span className="tip-full">{full}</span>
          {facts ? <span className="tip-facts">{facts}</span> : null}
        </div>
      ) : null}
      {open ? <ModelPopover current={ref} /> : null}
    </div>
  );
}

/** A stable DOM id for a row, so the search box can point at the highlighted one. */
function optionId(ref: string): string {
  return `model-opt-${ref.replace(/[^A-Za-z0-9_-]/g, "_")}`;
}

function Row({
  row,
  current,
  active,
  onHover,
}: {
  row: ModelRow;
  current: boolean;
  active: boolean;
  onHover: () => void;
}) {
  const size = formatSize(row.size_bytes);
  // per 1M tokens, in / out (the API section's heading says so)
  const price = row.price_in || row.price_out ? `$${(row.price_in ?? 0).toFixed(2)} / $${(row.price_out ?? 0).toFixed(2)}` : null;
  const badges = badgesFor(row);
  return (
    <li>
      <button
        type="button"
        id={optionId(row.ref)}
        role="option"
        aria-selected={current}
        className={["model-row", active ? "active" : "", current ? "current" : ""].filter(Boolean).join(" ")}
        aria-disabled={!row.available}
        onMouseEnter={onHover}
        onClick={() => row.available && actions.setModel(row.ref)}
      >
        <span className="check" aria-hidden="true">
          {current ? "✓" : ""}
        </span>
        <span className="row-label">{row.label}</span>
        <span className={row.note ? "row-meta row-note" : "row-meta"}>
          {row.note ?? size ?? price ?? (row.unpriced ? "price unknown" : "")}
        </span>
        <span className="row-fit">
          {row.note ? null : row.fits === false ? (
            <span className="no-fit" title="Not enough free graphics memory beside the helper models">
              won't fit
            </span>
          ) : row.fits ? (
            <span className="fits">fits</span>
          ) : null}
        </span>
        <span className="row-badges">
          {badges.map((b) => (
            <span key={b} className="badge variant">
              {b}
            </span>
          ))}
        </span>
      </button>
    </li>
  );
}

function SpendFooter({ spend }: { spend: Spend }) {
  // A cap is only worth showing when the budget is on (FR-M-7); off, say so. The
  // hour and the month are in the tooltip.
  const of = (value: number, cap: number | null | undefined) =>
    `${formatUsd(value)}${spend.enabled && cap != null ? ` of ${formatUsd(cap)}` : ""}`;
  const more = `This hour ${of(spend.hour_usd ?? 0, spend.hourly_cap_usd)}; this month ${of(spend.month_usd, spend.monthly_cap_usd)}.`;
  return (
    <footer className="model-footer" title={more}>
      Spent today {of(spend.day_usd, spend.daily_cap_usd)}
      {spend.enabled ? "" : " · budget off"}
    </footer>
  );
}

/**
 * FR-R-6, D-059: the key goes from this box to the Windows Credential Manager
 * through the shell, which hands it to the kernel; it never crosses the kernel
 * socket and never enters the store. One endpoint's key at a time.
 */
function ApiKeyForm({ models }: { models: ModelListData }) {
  const status = models.api_provider ?? null;
  // A custom endpoint from the config is not a preset, but it is what the key is for.
  const presets = [
    ...(models.api_presets ?? []),
    ...(status && !(models.api_presets ?? []).some((p) => p.id === status.id) ? [{ id: status.id, label: status.label }] : []),
  ];
  const [provider, setProvider] = useState(status?.id ?? presets[0]?.id ?? "airouter");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  if (!isTauri()) {
    return <p className="key-form list-hint">Outside the desktop app the key comes from .env or config/secrets.yaml (developer setup).</p>;
  }

  const run = async (command: "set_api_key" | "delete_api_key", args: Record<string, string>) => {
    setBusy(true);
    try {
      const live = await invoke<boolean>(command, args);
      const done = command === "set_api_key" ? "Saved" : "Removed";
      setNote(live ? `${done}. Checking the model list…` : `${done}. It takes effect at the next start.`);
      if (input.current) input.current.value = "";
    } catch (err) {
      setNote(String(err)); // the shell's errors never contain the key
    } finally {
      setBusy(false);
    }
  };
  const save = (e: FormEvent) => {
    e.preventDefault();
    void run("set_api_key", { provider, key: input.current?.value ?? "" });
  };
  const remove = () => {
    if (!status) return;
    // UI1-09: asked in the window, not in the browser's confirm box
    void actions
      .confirm({ title: `Remove the saved ${status.label} key?`, body: "It is deleted from this PC. You can paste it again later.", action: "Remove", danger: true })
      .then((yes) => {
        if (yes) void run("delete_api_key", { provider: status.id });
      });
  };

  const source =
    status?.key === "app" ? "key saved on this PC" : status?.key === "developer" ? "key from the developer setup" : "no key";
  return (
    <form className="key-form" onSubmit={save}>
      <p className="list-hint">
        {status ? `${status.label}: ${source}.` : "No API endpoint."} Saving a key replaces any other.
      </p>
      <div className="key-row">
        <select value={provider} onChange={(e) => setProvider(e.target.value)} aria-label="API provider" disabled={busy}>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
        <input
          ref={input}
          type="password"
          placeholder="Paste the API key"
          aria-label="API key"
          autoComplete="off"
          spellCheck={false}
          disabled={busy}
        />
        <button type="submit" disabled={busy}>
          Save
        </button>
        {status?.key === "app" ? (
          <button type="button" onClick={remove} disabled={busy}>
            Remove
          </button>
        ) : null}
      </div>
      {note ? <p className="list-hint" role="status">{note}</p> : null}
    </form>
  );
}

const PICKER_PREFS_KEY = "kokyu.picker";

function loadPickerPrefs(): PickerPrefs {
  try {
    return parsePickerPrefs(localStorage.getItem(PICKER_PREFS_KEY));
  } catch {
    return parsePickerPrefs(null);
  }
}

function ModelPopover({ current }: { current: string | null }) {
  const models = useChat((s) => s.models);
  const efforts = useChat(currentEfforts);
  const effort = useChat(currentEffort);
  const [keyOpen, setKeyOpen] = useState(false);
  const [query, setQuery] = useState("");
  // D-127: the order and the companies shown, kept between sessions
  const [prefs, setPrefs] = useState<PickerPrefs>(loadPickerPrefs);
  const changePrefs = (patch: Partial<PickerPrefs>) => {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    try {
      localStorage.setItem(PICKER_PREFS_KEY, JSON.stringify(next));
    } catch {
      // storage full or off: the choice lasts until the picker closes
    }
  };
  const [active, setActive] = useState(0);
  const search = useRef<HTMLInputElement>(null);
  const popover = useRef<HTMLDivElement>(null);

  useEffect(() => {
    search.current?.focus();
    // D-127: keep the opening height, so filtering never moves the controls under the pointer
    if (popover.current) popover.current.style.minHeight = `${popover.current.offsetHeight}px`;
  }, []);

  // Chat memory (D-098): the thread's model's row, for its context range and fit point
  const currentRow = useMemo(
    () => [...(models?.local ?? []), ...(models?.api ?? [])].find((r) => r.ref === current) ?? null,
    [models, current],
  );
  // D-127: local models have no price; only A–Z reorders them
  const local = useMemo(
    () => sortRows(filterRows(models?.local ?? [], query), prefs.order === "name" ? "name" : "company"),
    [models, query, prefs.order],
  );
  // D-126: the API models chosen in Settings, and the thread's own even if it is not one of them.
  // D-127: "All models", or a search, reaches every model the endpoint has (an older version too).
  const everyApi = models?.api ?? [];
  const chosen = useMemo(() => everyApi.filter((r) => r.listed !== false || r.ref === current), [everyApi, current]);
  const pool = prefs.all || query ? everyApi : chosen;
  const companies = useMemo(() => companiesOf(pool), [pool]);
  const api = useMemo(
    () => sortRows(filterCompanies(filterRows(pool, query), prefs.companies), prefs.order),
    [pool, query, prefs],
  );
  const toggleCompany = (name: string) =>
    changePrefs({ companies: prefs.companies.includes(name) ? prefs.companies.filter((c) => c !== name) : [...prefs.companies, name] });
  const picked = prefs.companies.filter((c) => companies.includes(c));
  // Keyboard order follows the list; rows that cannot be picked are skipped.
  const pickable = useMemo(() => [...local, ...api].filter((r) => r.available), [local, api]);
  const activeRef = pickable[Math.min(active, pickable.length - 1)]?.ref ?? null;
  // The row under the mouse, even one that cannot be picked, else the keyboard's.
  const [pointed, setPointed] = useState<ModelRow | null>(null);
  const shown = pointed ?? pickable.find((r) => r.ref === activeRef) ?? null;

  // The highlight starts on the current model, not the first row: an Enter
  // straight after opening must not load something else (a two-minute load).
  const startAtCurrent = (rows: ModelRow[]) => {
    const i = rows.findIndex((r) => r.ref === current);
    setActive(i >= 0 ? i : 0);
  };
  useEffect(() => {
    if (!query) startAtCurrent(pickable);
    // Only when the list arrives or changes; typing resets to the top match itself.
  }, [models]);

  // The highlighted row stays visible while arrowing through a long list.
  useEffect(() => {
    if (activeRef) document.getElementById(optionId(activeRef))?.scrollIntoView({ block: "nearest" });
  }, [activeRef]);

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      actions.closePicker();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, Math.max(0, pickable.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" && activeRef && !e.nativeEvent.isComposing) {
      e.preventDefault();
      actions.setModel(activeRef);
    }
  };

  const hover = (row: ModelRow) => () => {
    setPointed(row);
    const i = pickable.findIndex((r) => r.ref === row.ref);
    if (i >= 0) setActive(i);
  };

  const spend = models?.spend ?? null;

  return (
    <div className="model-popover" ref={popover} role="dialog" aria-label="Choose a model">
      <input
        ref={search}
        className="model-search"
        type="search"
        placeholder="Search models"
        value={query}
        onChange={(e) => {
          const next = e.target.value;
          setQuery(next);
          if (next) setActive(0);
          else startAtCurrent([...(models?.local ?? []), ...(models?.api ?? [])].filter((r) => r.available));
        }}
        onKeyDown={onKeyDown}
        aria-label="Search models"
        aria-controls="model-listbox"
        aria-activedescendant={activeRef ? optionId(activeRef) : undefined}
      />
      <div
        className="model-list"
        role="listbox"
        id="model-listbox"
        aria-label="Models"
        onMouseLeave={() => setPointed(null)}
      >
        {models === null ? <p className="list-hint">Looking for models…</p> : null}

        {models !== null ? (
          <section>
            <h3 className="list-head">Local</h3>
            {models.local_error ? <p className="list-hint">Ollama: {models.local_error}</p> : null}
            {local.length === 0 && !models.local_error ? (
              <p className="list-hint">{query ? "No local model matches." : "No local models found."}</p>
            ) : null}
            <ul>
              {local.map((r) => (
                <Row key={r.ref} row={r} current={r.ref === current} active={r.ref === activeRef} onHover={hover(r)} />
              ))}
            </ul>
          </section>
        ) : null}

        {models !== null ? (
          <section>
            <h3 className="list-head">
              API{models.api_provider ? ` · ${models.api_provider.label}` : ""}
              {models.api.some((r) => r.price_in || r.price_out) ? <span className="per">$ per 1M in / out</span> : null}
              {models.api_stale ? <span className="badge stale">cached</span> : null}
              <button type="button" className="refresh key" title="Choose which API models show here" onClick={() => actions.openSettings("models")}>
                Edit list
              </button>
              <button
                type="button"
                className="refresh key"
                title="Add or change the API key"
                aria-expanded={keyOpen}
                onClick={() => setKeyOpen((o) => !o)}
              >
                Key
              </button>
              <button
                type="button"
                className="refresh again"
                title="Fetch the model list again"
                aria-label="Refresh API models"
                onClick={() => actions.refreshModels()}
              >
                ↻
              </button>
            </h3>
            {everyApi.length > 1 ? (
              <div className="model-tools">
                {everyApi.length > chosen.length ? (
                  <select
                    className="model-sort"
                    value={prefs.all ? "all" : "list"}
                    aria-label="Which API models"
                    onChange={(e) => changePrefs({ all: e.target.value === "all" })}
                  >
                    <option value="list">My list ({chosen.length})</option>
                    <option value="all">All models ({everyApi.length})</option>
                  </select>
                ) : null}
                <select
                  className="model-sort"
                  value={prefs.order}
                  aria-label="Sort API models"
                  onChange={(e) => changePrefs({ order: e.target.value as ModelOrder })}
                >
                  {MODEL_ORDERS.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </select>
                {companies.length > 1 ? (
                  <div className="model-companies" role="group" aria-label="Show these companies">
                    <button type="button" aria-pressed={picked.length === 0} onClick={() => changePrefs({ companies: [] })}>
                      All
                    </button>
                    {companies.map((c) => (
                      <button key={c} type="button" aria-pressed={picked.includes(c)} onClick={() => toggleCompany(c)}>
                        {c}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
            {/* A failed refresh is said out loud even when the cached list is still shown. */}
            {models.api_error && models.api.length > 0 ? (
              <p className="list-hint">Couldn't refresh the list ({models.api_error}); showing the cached one.</p>
            ) : null}
            {api.length === 0 ? (
              <p className="list-hint">
                {query && models.api.length
                  ? "No API model matches."
                  : models.api_key
                    ? models.api_error
                      ? `Couldn't fetch the list: ${models.api_error}`
                      : models.api.length
                        ? "None chosen. Edit list adds some."
                        : "No API models listed."
                    : "No API key yet. Add one with Key above."}
              </p>
            ) : null}
            <ul>
              {api.map((r, i) => (
                <Fragment key={r.ref}>
                  {/* FR-M-4: grouped by provider; the rows come sorted by id, so a new vendor starts a group */}
                  {prefs.order === "company" && r.group && r.group !== api[i - 1]?.group ? (
                    <li className="list-hint" role="presentation">
                      {r.group}
                    </li>
                  ) : null}
                  <Row row={r} current={r.ref === current} active={r.ref === activeRef} onHover={hover(r)} />
                </Fragment>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
      {shown ? (
        <div className="model-detail" aria-live="polite">
          <span className="tip-full">{shown.full ?? shown.ref}</span>
          <span className="tip-facts">{modelFacts(shown) || "\u00a0"}</span>
        </div>
      ) : null}
      {efforts.length > 0 ? (
        <section className="effort-section" aria-label="Effort">
          <h3 className="list-head">Effort</h3>
          <EffortSlider supported={efforts} value={effort} onChange={(next) => actions.setEffort(next as Effort)} />
        </section>
      ) : null}
      {currentRow?.context ? (
        <section className="effort-section context-section" aria-label="Chat memory">
          <h3 className="list-head" title="How much of this chat she can keep in mind, for this model in every chat">
            Chat memory
          </h3>
          <ContextSlider
            context={currentRow.context}
            local={currentRow.kind === "local"}
            onChange={(tokens) => actions.setContext(currentRow.ref, tokens)}
          />
        </section>
      ) : null}
      {keyOpen && models !== null ? <ApiKeyForm models={models} /> : null}
      {spend ? <SpendFooter spend={spend} /> : null}
    </div>
  );
}
