// The window's keyboard shortcuts (UI1-10, D-095) and the Ctrl+K palette's list,
// as pure functions so they are testable without a DOM: Ctrl+N a new chat, Ctrl+K
// the palette, Ctrl+, Settings, Esc stops a reply. The palette lists what works now:
// actions, companions and conversations.

import { canPickModel, canStartThread, type ChatState, type SettingsSection } from "./chat-state";

export type Shortcut = "new_chat" | "palette" | "settings" | "stop";

interface KeyLike {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  defaultPrevented?: boolean;
  isComposing?: boolean;
}

export function shortcutFor(e: KeyLike): Shortcut | null {
  if (e.isComposing) return null;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && !e.altKey && !e.shiftKey) {
    const k = e.key.toLowerCase();
    if (k === "n") return "new_chat";
    if (k === "k") return "palette";
    if (k === ",") return "settings";
  }
  // An Escape something else used (closing a menu, cancelling an edit) is not a Stop.
  if (e.key === "Escape" && !mod && !e.altKey && !e.shiftKey && !e.defaultPrevented) return "stop";
  return null;
}

/** A dialog or pop-up is open: Escape and the shortcuts belong to it. */
export function anyModal(s: ChatState): boolean {
  return s.settings !== null || s.roleplayOpen || s.profile !== null || s.confirm !== null || s.pickerOpen || s.palette;
}

export type PaletteAction =
  | { kind: "new_chat" }
  | { kind: "new_roleplay" }
  | { kind: "model" }
  | { kind: "settings"; section: SettingsSection }
  | { kind: "companion"; id: string }
  | { kind: "profile"; id: string }
  | { kind: "thread"; id: string };

export interface PaletteItem {
  key: string;
  label: string;
  group: "Actions" | "Companions" | "Conversations";
  hint?: string;
  action: PaletteAction;
}

/** With nothing typed, this many recent conversations; a search shows more. */
const RECENT = 6;
const FOUND = 20;

function matches(label: string, words: string[]): boolean {
  const l = label.toLowerCase();
  return words.every((w) => l.includes(w));
}

export function paletteItems(s: ChatState, query: string): PaletteItem[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const startable = canStartThread(s);
  const actions: PaletteItem[] = [
    ...(startable
      ? [
          { key: "new", label: "New chat", group: "Actions" as const, hint: "Ctrl+N", action: { kind: "new_chat" as const } },
          { key: "rp", label: "New roleplay…", group: "Actions" as const, action: { kind: "new_roleplay" as const } },
        ]
      : []),
    ...(canPickModel(s) ? [{ key: "model", label: "Choose a model", group: "Actions" as const, action: { kind: "model" as const } }] : []),
    { key: "settings", label: "Settings", group: "Actions", hint: "Ctrl+,", action: { kind: "settings", section: "models" } },
    { key: "appearance", label: "Appearance", group: "Actions", action: { kind: "settings", section: "appearance" } },
    { key: "voice", label: "Voice: Read aloud, dictation key", group: "Actions", action: { kind: "settings", section: "voice" } },
    { key: "memory", label: "Memory", group: "Actions", action: { kind: "settings", section: "memory" } },
    { key: "doctor", label: "Doctor", group: "Actions", action: { kind: "settings", section: "doctor" } },
  ];
  const companions: PaletteItem[] = s.roster.flatMap((w) => [
    ...(w.id !== s.companion?.id
      ? [{ key: `talk-${w.id}`, label: `Talk to ${w.name}`, group: "Companions" as const, action: { kind: "companion" as const, id: w.id } }]
      : []),
    { key: `profile-${w.id}`, label: `${w.name}'s profile`, group: "Companions" as const, action: { kind: "profile" as const, id: w.id } },
  ]);
  // Opening another conversation waits for the reply (as the sidebar does).
  const threads: PaletteItem[] =
    s.turn === "idle"
      ? s.threads
          .filter((t) => t.id !== s.thread?.id)
          .map((t) => ({
            key: `thread-${t.id}`,
            label: t.title || (t.mode === "roleplay" ? "New story" : "New chat"),
            group: "Conversations" as const,
            action: { kind: "thread" as const, id: t.id },
          }))
      : [];
  if (!words.length) return [...actions, ...companions, ...threads.slice(0, RECENT)];
  return [
    ...actions.filter((i) => matches(i.label, words)),
    ...companions.filter((i) => matches(i.label, words)),
    ...threads.filter((i) => matches(i.label, words)).slice(0, FOUND),
  ];
}
