import type { StatsRange } from "@/lib/api";

// The one place the dashboard's date presets + range math live (F4). The public
// share page keeps its own copy since it can't share the authed range context.

export const RANGE_PRESETS = [
  { key: "24h", label: "24h", days: 1 },
  { key: "7d", label: "7 days", days: 7 },
  { key: "30d", label: "30 days", days: 30 },
] as const;

export type RangePresetKey = (typeof RANGE_PRESETS)[number]["key"];

/** Build a [now-days, now) window as ISO-8601 UTC strings. */
export function rangeForDays(days: number): StatsRange {
  const to = new Date();
  const from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000);
  return { from: from.toISOString(), to: to.toISOString() };
}
