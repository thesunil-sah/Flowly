"use client";

import { X } from "lucide-react";

import { useFilters } from "@/components/layout/filter-context";
import { Button } from "@/components/ui/button";

// The applied-filters chip bar (Phase 10). Rendered in every report's header;
// each chip removes its filter on click, and "Clear all" wipes the set. Returns
// null when nothing is filtered so it takes no space in the common case.

const FILTER_LABELS: Record<string, string> = {
  country: "Country",
  device: "Device",
  browser: "Browser",
  os: "OS",
  source: "Source",
  path: "Page",
};

export function ActiveFilters() {
  const { filters, removeFilter, clearFilters } = useFilters();
  const keys = Object.keys(filters);
  if (keys.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {keys.map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => removeFilter(key)}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1 text-xs transition-colors hover:bg-accent"
        >
          <span className="text-muted-foreground">{FILTER_LABELS[key] ?? key}:</span>
          <span className="max-w-[12rem] truncate font-medium">{filters[key] || "(none)"}</span>
          <X className="size-3 text-muted-foreground" aria-hidden />
          <span className="sr-only">Remove filter</span>
        </button>
      ))}
      {keys.length > 1 && (
        <Button variant="ghost" size="xs" onClick={clearFilters}>
          Clear all
        </Button>
      )}
    </div>
  );
}
