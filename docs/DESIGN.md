# DESIGN — Kōkyū

The look as it stands, written down so new screens (the setup screen, the companion creator) match it. UI-2 was built screen by screen from the user's references (D-102..D-113), not from a mock first, so this file records what exists rather than a plan (UI2-02). The references are in `reference-images/`; the user models roleplay on c.ai.

## Colour roles

All colours are CSS variables on `:root` (`src/app/app.css`); a theme swaps them (`src/app/theme.ts`, eight presets, set in Settings → Appearance). Never write a colour literal for a role below.

| Variable | Role |
|---|---|
| `--bg` | the window behind everything |
| `--panel`, `--panel-2` | raised surfaces; `--panel-2` for hover, inputs and cards inside a panel |
| `--line` | borders and dividers |
| `--text`, `--muted` | body text; secondary text (times, hints, notes) |
| `--accent` | fills: the send button, New chat, the switch when on |
| `--accent-text` | the accent used for text and icons; `theme.ts` swaps it when the accent is unreadable on the theme (D-112) |
| `--on-accent`, `--accent-ink` | text on an accent fill |
| `--user`, `--reply` | the two message bubbles |
| `--danger` | errors and destructive actions only |
| `--code-*` | code colouring (D-093) |

A test holds every preset to 7:1 for text and 3:1 for the accent (D-113).

## Type

- One family: the system UI font (`system-ui`, Segoe UI on Windows); monospace `ui-monospace`, Cascadia Code, Consolas for code. No bundled font yet.
- Sizes in use: 12 (notes, labels, badges), 13 (secondary UI), 14 (UI default), 15 (`--chat-size`, the messages; changeable in Appearance), 16–18 (titles in dialogs), 20–22 (headings), 40 and 64 only for the empty state and the Stage.
- **Nothing under 12 px for text.** The only smaller sizes are glyphs inside small badges (`.caret`, `.warn`, `.no-fit`).
- Uppercase small labels (section heads) use 12 px with letter spacing; never smaller.

## Space and shape

- Spacing in steps of 2 and 4 px: 4, 6, 8, 10, 12, 14, 16, 20, 24.
- Radii: `--radius` (14 px) for cards, bubbles and dialogs; 8–10 px for buttons and inputs; 999 px for pills and round swatches.
- The chat column is at most `--column` (800 px) wide; the sidebar `--sidebar` (260 px), hideable (D-100).
- The top bar is three columns: left (her chip, the pet button), the title centred, right (Chat | Stage, Temp Chat, the window's buttons). The title shrinks with an ellipsis rather than overlap (UI2-00m).

## Icons

Stroke-only line icons in `src/app/ui/Icon.tsx`, drawn in the current text colour, stroke 1.7. No emoji as icons. A new icon is a path added there, in the same 24-unit grid.

## Motion

Short and quiet: 150 ms for presses and hovers, about 400 ms for fades (captions, toasts). Nothing loops forever except the thinking word and the loading strip. Respect the window's state: nothing animates behind a dialog.

## Focus and keys

Every control is reachable by keyboard and shows a 2 px `--accent` outline on `:focus-visible`. Esc closes the top dialog first, then stops a reply (D-095). Dialogs trap focus and give it back on close.

## Text in the UI (FR-C-4, D-082)

- Plain words, second person, short. "Kōkyū's engine", never KASANE or a phase code.
- Only working controls: nothing disabled as a placeholder.
- Every long user text is cut with an ellipsis in a single-line place (titles, chips, sidebar rows) and wraps anywhere in a message (`overflow-wrap: anywhere`).
- An input with a limit says so before the limit is hit (a counter), and a paste over it is never cut silently.
