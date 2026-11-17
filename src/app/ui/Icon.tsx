// A few line icons for the message bar and the shell (UI1-07, UI1-09). Stroke-only,
// in the text colour; the full icon set arrives with the design standard (UI-2, D-086).

const PATHS = {
  copy: "M9 9h10v10H9zM5 15V5h10",
  check: "M5 12.5l4.5 4.5L19 7.5",
  regenerate: "M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5v4h-4",
  edit: "M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4",
  down: "M12 5v14M6 13l6 6 6-6",
  plus: "M12 5v14M5 12h14",
  chevron: "M7 10l5 5 5-5",
  pin: "M9 4h6l-1 6 4 4H6l4-4zM12 14v6",
  more: "M6 12h.01M12 12h.01M18 12h.01",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  mic: "M12 3.5a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0v-5a3 3 0 0 0-3-3zM5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6",
  speaker: "M4 9.5h3.5L12 5.5v13l-4.5-4H4zM15.5 9.2a4 4 0 0 1 0 5.6M18.2 6.6a7.6 7.6 0 0 1 0 10.8",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} />
    </svg>
  );
}
