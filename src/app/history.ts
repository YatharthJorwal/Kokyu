// The sidebar's history, grouped by day (K1-03, FR-C-6): Today, Yesterday,
// Previous 7 days, Older. Pure: the caller passes "now", so it is testable and a
// window left open past midnight regroups on the next render.

import type { ThreadInfo } from "../net/protocol";

export type GroupName = "Today" | "Yesterday" | "Previous 7 days" | "Older";

export interface ThreadGroup {
  name: GroupName;
  threads: ThreadInfo[];
}

const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDay(ms: number): number {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/** Kernel timestamps are Unix seconds; this also accepts milliseconds. */
export function toMs(ts: number): number {
  return ts < 1e12 ? ts * 1000 : ts;
}

export function groupOf(updatedAt: number, nowMs: number): GroupName {
  const today = startOfDay(nowMs);
  const t = toMs(updatedAt);
  if (t >= today) return "Today";
  if (t >= today - DAY_MS) return "Yesterday";
  if (t >= today - 7 * DAY_MS) return "Previous 7 days";
  return "Older";
}

const ORDER: GroupName[] = ["Today", "Yesterday", "Previous 7 days", "Older"];

/** Newest first inside each group; empty groups are left out. */
export function groupThreads(threads: ThreadInfo[], nowMs: number): ThreadGroup[] {
  const buckets = new Map<GroupName, ThreadInfo[]>();
  for (const t of [...threads].sort((a, b) => b.updated_at - a.updated_at)) {
    const name = groupOf(t.updated_at, nowMs);
    const list = buckets.get(name) ?? [];
    list.push(t);
    buckets.set(name, list);
  }
  return ORDER.filter((n) => buckets.has(n)).map((name) => ({ name, threads: buckets.get(name) ?? [] }));
}
