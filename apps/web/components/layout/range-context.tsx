"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { rangeForDays, type RangePresetKey } from "@/lib/range";
import type { StatsRange } from "@/lib/api";

// Dashboard-wide date range (F4 + Phase 10). Lives in the dashboard layout so the
// chosen window persists as the user moves between report destinations. The
// window is frozen per change (useMemo) so query keys don't churn every render.
// State is either a rolling preset (recomputed to "now") or an explicit custom
// [from, to) window entered via the date picker.

type RangeState =
  | { kind: "preset"; days: number }
  | { kind: "custom"; range: StatsRange };

type RangeContextValue = {
  presetKey: RangePresetKey | "custom";
  setPresetDays: (days: number) => void;
  setCustomRange: (from: string, to: string) => void;
  range: StatsRange;
};

const RangeContext = createContext<RangeContextValue | null>(null);

const KEY_BY_DAYS: Record<number, RangePresetKey> = { 1: "24h", 7: "7d", 30: "30d" };

export function RangeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<RangeState>({ kind: "preset", days: 7 });

  const range = useMemo(
    () => (state.kind === "custom" ? state.range : rangeForDays(state.days)),
    [state],
  );

  const value = useMemo<RangeContextValue>(
    () => ({
      presetKey: state.kind === "custom" ? "custom" : (KEY_BY_DAYS[state.days] ?? "7d"),
      setPresetDays: (days) => setState({ kind: "preset", days }),
      setCustomRange: (from, to) => setState({ kind: "custom", range: { from, to } }),
      range,
    }),
    [state, range],
  );

  return <RangeContext.Provider value={value}>{children}</RangeContext.Provider>;
}

export function useRange(): RangeContextValue {
  const ctx = useContext(RangeContext);
  if (ctx === null) throw new Error("useRange must be used within a RangeProvider");
  return ctx;
}
