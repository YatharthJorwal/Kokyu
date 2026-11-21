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
  left: "M15 6l-6 6 6 6",
  right: "M9 6l6 6-6 6",
  rewind: "M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4.5 4.5v4h4",
  branch: "M6 4v16M6 9a6 6 0 0 0 6 6h6M15 12l3 3-3 3",
  sidebar: "M4 5h16v14H4zM9.5 5v14",
  // Settings' sections (D-102)
  models: "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4",
  monitor: "M3.5 5h17v11h-17zM9 20h6M12 16v4",
  memory: "M12 5.5a3 3 0 0 0-5.6-1.5A3.5 3.5 0 0 0 4 9.5a3.5 3.5 0 0 0 1 6.5 3 3 0 0 0 7 1.5zM12 5.5a3 3 0 0 1 5.6-1.5A3.5 3.5 0 0 1 20 9.5a3.5 3.5 0 0 1-1 6.5 3 3 0 0 1-7 1.5zM12 5.5V19",
  pulse: "M3 12h4l2.5-6 5 12 2.5-6h4",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5.5M12 7.5h.01",
  close: "M6 6l12 12M18 6L6 18",
  cat: "M4.5 9.5 4 3.5l5 3h6l5-3-.5 6c1 1.3 1.5 2.8 1.5 4.5 0 4.1-4 6.5-9 6.5s-9-2.4-9-6.5c0-1.7.5-3.2 1.5-4.5zM9 13.5h.01M15 13.5h.01M10.5 16.5l1.5 1 1.5-1",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} />
    </svg>
  );
}
