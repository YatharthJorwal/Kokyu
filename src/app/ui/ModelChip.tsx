// The one model control (K1-10; FR-M-1, 2, 4, 5, 6, 7): a chip in the input row
// with a local or cloud icon, the model's name and the effort label. It opens a
// popover with a search box and Local and API sections as one list; the current
// model has a check mark and picking a row is the whole action. While the kernel
// loads the model the chip shows a spinner; a failed load shows a warning.
// The effort slider joins the popover in K1-11, the fits hint with K1-09.

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import type { ModelRow, Spend } from "../../net/protocol";
import { canPickModel, currentEffort, currentModelRef, modelLabel } from "../chat-state";
import { badgesFor, effortLabel, filterRows, formatSize, formatUsd, isLocalRef } from "../models";
import { actions, useChat } from "../store";

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
  const effort = useChat(currentEffort);
  const status = useChat((s) => s.modelStatus);
  const open = useChat((s) => s.pickerOpen);
  const enabled = useChat(canPickModel);
  const turn = useChat((s) => s.turn);
  const wrapper = useRef<HTMLDivElement>(null);

  const loading = status?.state === "loading" && status.model_ref === ref;
  const failed = status?.state === "failed" && status.model_ref === ref;
  const title = loading
    ? `Loading ${label}…`
    : failed
      ? `${label} failed to load: ${status?.message ?? "unknown error"}`
      : turn !== "idle"
        ? "Switch models after the reply"
        : "Choose the model";

  // A click anywhere outside the chip and its popover closes it.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) actions.closePicker();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const classes = ["model-chip", loading ? "loading" : "", failed ? "failed" : "", open ? "open" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="model-picker" ref={wrapper}>
      <button
        type="button"
        className={classes}
        title={title}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={!enabled && !open}
        onClick={() => (open ? actions.closePicker() : actions.openPicker())}
      >
        <KindIcon local={isLocalRef(ref)} />
        <span className="model-name">{label}</span>
        {effort ? <span className="effort-label">{effortLabel(effort)}</span> : null}
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
  const price =
    row.price_in || row.price_out ? `$${(row.price_in ?? 0).toFixed(2)} / $${(row.price_out ?? 0).toFixed(2)} per M` : null;
  const meta = [row.detail, size, price].filter(Boolean).join(" · ");
  const badges = badgesFor(row);
  return (
    <li>
      <button
        type="button"
        id={optionId(row.ref)}
        role="option"
        aria-selected={current}
        className={["model-row", active ? "active" : "", current ? "current" : ""].filter(Boolean).join(" ")}
        disabled={!row.available}
        onMouseEnter={onHover}
        onClick={() => actions.setModel(row.ref)}
        title={row.note ?? row.ref}
      >
        <span className="check" aria-hidden="true">
          {current ? "✓" : ""}
        </span>
        <span className="row-main">
          <span className="row-label">
            {row.label}
            {badges.map((b) => (
              <span key={b} className="badge variant">
                {b}
              </span>
            ))}
          </span>
          {meta ? <span className="row-meta">{meta}</span> : null}
        </span>
        {row.note ? <span className="row-note">{row.note}</span> : null}
      </button>
    </li>
  );
}

function SpendFooter({ spend }: { spend: Spend }) {
  // A cap is only worth showing when the budget is on (FR-M-7); off, say so.
  const cap = (value: number | null) => (spend.enabled && value !== null ? ` of ${formatUsd(value)}` : "");
  return (
    <footer className="model-footer">
      <span>
        Hour {formatUsd(spend.hour_usd ?? 0)}
        {cap(spend.hourly_cap_usd ?? null)}
      </span>
      <span>
        Today {formatUsd(spend.day_usd)}
        {cap(spend.daily_cap_usd)}
      </span>
      <span>
        Month {formatUsd(spend.month_usd)}
        {cap(spend.monthly_cap_usd)}
      </span>
      {spend.enabled ? null : <span>Budget off</span>}
    </footer>
  );
}

function ModelPopover({ current }: { current: string | null }) {
  const models = useChat((s) => s.models);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const search = useRef<HTMLInputElement>(null);

  useEffect(() => {
    search.current?.focus();
  }, []);

  const local = useMemo(() => filterRows(models?.local ?? [], query), [models, query]);
  const api = useMemo(() => filterRows(models?.api ?? [], query), [models, query]);
  // Keyboard order follows the list; rows that cannot be picked are skipped.
  const pickable = useMemo(() => [...local, ...api].filter((r) => r.available), [local, api]);
  const activeRef = pickable[Math.min(active, pickable.length - 1)]?.ref ?? null;

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
    } else if (e.key === "Enter" && activeRef) {
      e.preventDefault();
      actions.setModel(activeRef);
    }
  };

  const hover = (ref: string) => () => {
    const i = pickable.findIndex((r) => r.ref === ref);
    if (i >= 0) setActive(i);
  };

  const spend = models?.spend ?? null;

  return (
    <div className="model-popover" role="dialog" aria-label="Choose a model">
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
      <div className="model-list" role="listbox" id="model-listbox" aria-label="Models">
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
                <Row key={r.ref} row={r} current={r.ref === current} active={r.ref === activeRef} onHover={hover(r.ref)} />
              ))}
            </ul>
          </section>
        ) : null}

        {models !== null ? (
          <section>
            <h3 className="list-head">
              API
              {models.api_stale ? <span className="badge stale">cached</span> : null}
              <button
                type="button"
                className="refresh"
                title="Fetch the model list again"
                aria-label="Refresh API models"
                onClick={() => actions.refreshModels()}
              >
                ↻
              </button>
            </h3>
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
                      : "No API models listed."
                    : "No API key yet. Cloud models show up here once one is set up."}
              </p>
            ) : null}
            <ul>
              {api.map((r) => (
                <Row key={r.ref} row={r} current={r.ref === current} active={r.ref === activeRef} onHover={hover(r.ref)} />
              ))}
            </ul>
          </section>
        ) : null}
      </div>
      {spend ? <SpendFooter spend={spend} /> : null}
    </div>
  );
}
