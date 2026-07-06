"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { BreakdownRow } from "@/lib/api";
import { formatNumber } from "@/lib/format";

// Icon-rich breakdown card (phpAnalytics reference): leading icon, label, an
// indigo share bar proportional to the top row, right-aligned visitors, and
// an optional "View all" that hands navigation to the composition.

export function BreakdownCard({
  title,
  rows,
  icon,
  limit,
  onViewAll,
  onSelect,
  labelFallback = "(none)",
  emptyText = "No data in this range",
}: {
  title: string;
  rows: BreakdownRow[];
  icon?: (label: string) => ReactNode;
  limit?: number;
  onViewAll?: () => void;
  /** When set, each row becomes a click-to-filter button (Phase 10). */
  onSelect?: (label: string) => void;
  labelFallback?: string;
  emptyText?: string;
}) {
  const shown = limit ? rows.slice(0, limit) : rows;
  const max = Math.max(1, ...shown.map((r) => r.visitors));

  return (
    <div className="flex flex-col rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-muted-foreground">{title}</h2>
        {onViewAll && rows.length > 0 && (
          <Button variant="ghost" size="xs" onClick={onViewAll}>
            View all
          </Button>
        )}
      </div>

      {shown.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {shown.map((r) => {
            const inner = (
              <>
                {/* share bar behind the row content */}
                <span
                  className="absolute inset-y-0 left-0 rounded-md bg-primary/10"
                  style={{ width: `${Math.round((r.visitors / max) * 100)}%` }}
                  aria-hidden
                />
                <span className="relative flex min-w-0 flex-1 items-center gap-2.5 text-sm">
                  {icon?.(r.label)}
                  <span className="truncate">{r.label || labelFallback}</span>
                </span>
                <span className="relative shrink-0 text-sm font-medium tabular-nums">
                  {formatNumber(r.visitors)}
                </span>
              </>
            );
            const rowClass = "relative flex items-center gap-2.5 rounded-md px-2 py-1.5";
            return (
              <li key={r.label || labelFallback}>
                {onSelect ? (
                  <button
                    type="button"
                    onClick={() => onSelect(r.label)}
                    className={`${rowClass} w-full text-left transition-colors hover:bg-muted`}
                  >
                    {inner}
                  </button>
                ) : (
                  <div className={rowClass}>{inner}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
