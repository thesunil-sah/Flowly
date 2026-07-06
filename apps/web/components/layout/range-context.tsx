"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { rangeForDays, type RangePresetKey } from "@/lib/range";
import type { StatsRange } from "@/lib/api";

// Dashboard-wide date range (F4). Lives in the dashboard layout so the chosen
// preset persists as the user moves between report destinations. The window is
// frozen per preset change (useMemo) so query keys don't churn every render.

type RangeContextValue = {
  presetDays: number;
  presetKey: RangePresetKey;
  setPresetDays: (days: number) => void;
  range: StatsRange;
};

const RangeContext = createContext<RangeContextValue | null>(null);

const KEY_BY_DAYS: Record<number, RangePresetKey> = { 1: "24h", 7: "7d", 30: "30d" };

export function RangeProvider({ children }: { children: ReactNode }) {
  const [presetDays, setPresetDays] = useState(7);
  const range = useMemo(() => rangeForDays(presetDays), [presetDays]);
  const value = useMemo<RangeContextValue>(
    () => ({ presetDays, presetKey: KEY_BY_DAYS[presetDays] ?? "7d", setPresetDays, range }),
    [presetDays, range],
  );
  return <RangeContext.Provider value={value}>{children}</RangeContext.Provider>;
}

export function useRange(): RangeContextValue {
  const ctx = useContext(RangeContext);
  if (ctx === null) throw new Error("useRange must be used within a RangeProvider");
  return ctx;
}
