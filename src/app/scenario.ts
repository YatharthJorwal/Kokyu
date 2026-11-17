// The New roleplay dialog's card (K1c-08, FR-MODE-6) as pure logic: its fields, the
// limits the kernel checks (KASANE/protocol: SCENARIO_*_MAX) and the card a form
// becomes. The dialog (ui/RoleplayDialog.tsx) only renders this.

import type { Scenario } from "../net/protocol";

export type ScenarioField = keyof Required<Scenario>;

export interface FieldSpec {
  key: ScenarioField;
  label: string;
  hint: string;
  multiline: boolean;
  max: number;
}

/** The kernel refuses a longer field (protocol.Scenario). */
export const TITLE_MAX = 120;
export const FIELD_MAX = 2000;
export const OPENING_MAX = 4000;

export const SCENARIO_FIELDS: readonly FieldSpec[] = [
  { key: "title", label: "Title", hint: "A rainy night at the café", multiline: false, max: TITLE_MAX },
  { key: "setting", label: "Setting", hint: "Where and when the story takes place", multiline: false, max: FIELD_MAX },
  { key: "user_role", label: "You play", hint: "Who you are in the story", multiline: false, max: FIELD_MAX },
  { key: "her_role", label: "She is to you", hint: "An old friend, a rival, a stranger…", multiline: false, max: FIELD_MAX },
  { key: "opening", label: "Her opening line", hint: "How she starts the story (optional)", multiline: true, max: OPENING_MAX },
  { key: "rules", label: "Rules", hint: "Anything the story should keep to (optional)", multiline: true, max: FIELD_MAX },
];

export type ScenarioForm = Record<ScenarioField, string>;

export const EMPTY_FORM: ScenarioForm = { title: "", setting: "", user_role: "", her_role: "", opening: "", rules: "" };

/** A saved card into the form's fields (missing ones empty). */
export function formFromCard(card: Scenario): ScenarioForm {
  const form = { ...EMPTY_FORM };
  for (const f of SCENARIO_FIELDS) form[f.key] = card[f.key] ?? "";
  return form;
}

/** The form as a card: trimmed, empty fields left out, each cut to the kernel's limit. */
export function cardFromForm(form: ScenarioForm): Scenario {
  const card: Scenario = {};
  for (const f of SCENARIO_FIELDS) {
    const value = form[f.key].trim().slice(0, f.max);
    if (value) card[f.key] = value;
  }
  return card;
}

/** Nothing filled in: starting it is a blank roleplay, and there is nothing to save. */
export function isBlankCard(card: Scenario): boolean {
  return Object.keys(card).length === 0;
}

/** Whether the form still says what the saved card says (Update has nothing to do). */
export function sameCard(a: Scenario, b: Scenario): boolean {
  return SCENARIO_FIELDS.every((f) => (a[f.key] ?? "").trim() === (b[f.key] ?? "").trim());
}
