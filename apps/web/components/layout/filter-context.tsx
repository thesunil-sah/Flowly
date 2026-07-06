"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import type { StatsFilters } from "@/lib/api";

// Dashboard-wide filters (Phase 10). Like the range context, this lives in the
// dashboard layout so a chosen slice (e.g. country=US, device=mobile) persists
// as the user moves between report destinations. Filters stack (AND) and are
// threaded into every stats query. In-memory only — a filter is a transient
// exploration, not a saved preference, so it resets on reload (matches range).

type FilterContextValue = {
  filters: StatsFilters;
  setFilter: (key: string, value: string) => void;
  removeFilter: (key: string) => void;
  clearFilters: () => void;
};

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<StatsFilters>({});

  const value = useMemo<FilterContextValue>(
    () => ({
      filters,
      setFilter: (key, val) => setFilters((f) => ({ ...f, [key]: val })),
      removeFilter: (key) =>
        setFilters((f) => {
          const next = { ...f };
          delete next[key];
          return next;
        }),
      clearFilters: () => setFilters({}),
    }),
    [filters],
  );

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (ctx === null) throw new Error("useFilters must be used within a FilterProvider");
  return ctx;
}
