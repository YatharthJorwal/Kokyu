// Settings → Appearance (D-073): how the chat window looks. Kept in this window's
// localStorage, not settings.json: it is the client's own look and the kernel never
// needs it. Pure logic here; `applyTheme` is the one function that touches the page.

export type Preset = "kokyu" | "midnight" | "light" | "sakura" | "paper" | "ocean" | "forest" | "mocha";
export type MessageStyle = "open" | "bubbles";
export type TextSize = "small" | "normal" | "large";

export interface Theme {
  preset: Preset;
  /** null = the preset's own accent. */
  accent: string | null;
  messages: MessageStyle;
  size: TextSize;
  /** The Stage caption's glow (D-111); null = DEFAULT_GLOW, Yuri's pink. */
  glow?: string | null;
}

export const DEFAULT_THEME: Theme = { preset: "kokyu", accent: null, messages: "open", size: "normal", glow: null };
export const DEFAULT_GLOW = "#ffc3e2";
export const GLOWS = [DEFAULT_GLOW, "#cba6f7", "#8fd4ff", "#9cf0c0", "#ffd38a", "#ffffff"];

/** The CSS variables each preset sets (app.css reads them; its :root holds Kōkyū's). */
export const PRESETS: Record<Preset, { label: string; scheme: "dark" | "light"; vars: Record<string, string> }> = {
  kokyu: {
    label: "Kōkyū",
    scheme: "dark",
    vars: {
      "--bg": "#17131c",
      "--panel": "#1f1a26",
      "--panel-2": "#2a2333",
      "--line": "#352d41",
      "--text": "#f1ecf7",
      "--muted": "#a39bb4",
      "--accent": "#f27aa6",
      "--user": "#2f2840",
      "--reply": "#241e2c",
      "--danger": "#e5707a",
    },
  },
  // Neutral greys, like the character-chat sites the user pointed at.
  midnight: {
    label: "Midnight",
    scheme: "dark",
    vars: {
      "--bg": "#18181b",
      "--panel": "#1f1f23",
      "--panel-2": "#2a2a2f",
      "--line": "#34343a",
      "--text": "#ececf1",
      "--muted": "#9d9da8",
      "--accent": "#a8b4ff",
      "--user": "#2f2f35",
      "--reply": "#26262b",
      "--danger": "#e5707a",
    },
  },
  light: {
    label: "Light",
    scheme: "light",
    vars: {
      "--bg": "#faf8fc",
      "--panel": "#f1edf5",
      "--panel-2": "#e6e0ee",
      "--line": "#d9d1e3",
      "--text": "#211b29",
      "--muted": "#6c6380",
      "--accent": "#d3477e",
      "--user": "#ebe3f3",
      "--reply": "#f1edf5",
      "--danger": "#c23b4a",
    },
  },
  // D-113: more presets, two light and three dark.
  sakura: {
    label: "Sakura",
    scheme: "light",
    vars: {
      "--bg": "#fff6f9",
      "--panel": "#fdecf2",
      "--panel-2": "#f8dce7",
      "--line": "#efc9d8",
      "--text": "#2b1720",
      "--muted": "#7d5b69",
      "--accent": "#d6487f",
      "--user": "#f9e1ea",
      "--reply": "#fdecf2",
      "--danger": "#c23b4a",
    },
  },
  paper: {
    label: "Paper",
    scheme: "light",
    vars: {
      "--bg": "#faf7f0",
      "--panel": "#f2ede2",
      "--panel-2": "#e8e1d2",
      "--line": "#dbd2c0",
      "--text": "#2a251c",
      "--muted": "#6e6555",
      "--accent": "#b5651d",
      "--user": "#efe7d6",
      "--reply": "#f2ede2",
      "--danger": "#b83a3a",
    },
  },
  ocean: {
    label: "Ocean",
    scheme: "dark",
    vars: {
      "--bg": "#0f1720",
      "--panel": "#16212c",
      "--panel-2": "#1f2d3b",
      "--line": "#2a3b4c",
      "--text": "#e6eef6",
      "--muted": "#93a6b8",
      "--accent": "#5cc8e6",
      "--user": "#1d3042",
      "--reply": "#152330",
      "--danger": "#e5707a",
    },
  },
  forest: {
    label: "Forest",
    scheme: "dark",
    vars: {
      "--bg": "#121a15",
      "--panel": "#18231c",
      "--panel-2": "#213026",
      "--line": "#2c3e31",
      "--text": "#e7f0e9",
      "--muted": "#99ad9e",
      "--accent": "#7fcf8f",
      "--user": "#22352a",
      "--reply": "#18241d",
      "--danger": "#e5707a",
    },
  },
  mocha: {
    label: "Mocha",
    scheme: "dark",
    vars: {
      "--bg": "#1b1613",
      "--panel": "#241d19",
      "--panel-2": "#2f2621",
      "--line": "#3d322b",
      "--text": "#f3ebe4",
      "--muted": "#b3a397",
      "--accent": "#e8a26b",
      "--user": "#33291f",
      "--reply": "#261f1a",
      "--danger": "#e5707a",
    },
  },
};

export const ACCENTS = ["#f27aa6", "#a8b4ff", "#8fd4a4", "#f2b56b", "#c49bff", "#6cc6e8"];

export const TEXT_SIZES: Record<TextSize, string> = { small: "14px", normal: "15px", large: "17px" };

const HEX = /^#[0-9a-f]{6}$/i;

/** A stored theme, checked field by field: anything unknown falls back to the default. */
export function parseTheme(raw: string | null): Theme {
  let data: unknown;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = null;
  }
  const d = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const pick = <T extends string>(value: unknown, allowed: readonly T[], fallback: T): T =>
    allowed.includes(value as T) ? (value as T) : fallback;
  return {
    preset: pick(d.preset, Object.keys(PRESETS) as Preset[], DEFAULT_THEME.preset),
    accent: typeof d.accent === "string" && HEX.test(d.accent) ? d.accent.toLowerCase() : null,
    messages: pick(d.messages, ["open", "bubbles"] as const, DEFAULT_THEME.messages),
    size: pick(d.size, Object.keys(TEXT_SIZES) as TextSize[], DEFAULT_THEME.size),
    glow: typeof d.glow === "string" && HEX.test(d.glow) ? d.glow.toLowerCase() : null,
  };
}

function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

/** Dark or light text on the accent, whichever reads better (WCAG relative luminance). */
export function inkFor(hex: string): string {
  return luminance(hex) > 0.35 ? "#1a1320" : "#ffffff";
}

/** WCAG contrast ratio of two colors, 1 to 21. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** The accent for text and icons on the page: the accent itself when it can be read
 * on the background (3:1, WCAG's floor for large text and icons), else the text color,
 * so a white accent on the light theme never hides her name (D-112). */
export function accentText(accent: string, bg: string, text: string): string {
  return contrast(accent, bg) >= 3 ? accent : text;
}

/** Every CSS variable and data attribute a theme sets on <html>. */
export function themeVars(theme: Theme): Record<string, string> {
  const preset = PRESETS[theme.preset];
  const accent = theme.accent ?? preset.vars["--accent"];
  return {
    ...preset.vars,
    "--accent": accent,
    "--on-accent": inkFor(accent),
    "--accent-text": accentText(accent, preset.vars["--bg"], preset.vars["--text"]),
    "--chat-size": TEXT_SIZES[theme.size],
    "--caption-glow": theme.glow ?? DEFAULT_GLOW,
  };
}

export const THEME_KEY = "kokyu.theme";

export function loadTheme(): Theme {
  try {
    return parseTheme(localStorage.getItem(THEME_KEY));
  } catch {
    return DEFAULT_THEME;   // storage blocked: the default look
  }
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, JSON.stringify(theme));
  } catch {
    // storage blocked: the look still applies for this session
  }
}

export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  for (const [name, value] of Object.entries(themeVars(theme))) root.style.setProperty(name, value);
  root.style.colorScheme = PRESETS[theme.preset].scheme;
  root.dataset.scheme = PRESETS[theme.preset].scheme;
  root.dataset.messages = theme.messages;
}
