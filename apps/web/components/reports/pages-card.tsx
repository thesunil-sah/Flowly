"use client";

import { Button } from "@/components/ui/button";
import type { PageRow } from "@/lib/api";
import { formatDuration, formatNumber } from "@/lib/format";

// Pages card: mono path labels, primary metric + visitors, share bar like
// BreakdownCard (PageRow's shape differs — count vs pageviews — so it gets
// its own component rather than a lossy adapter). On the engagement ranking the
// rows also carry avg time-on-page + bounce rate, shown as extra columns.

export function PagesCard({
  title,
  rows,
  metric,
  limit,
  onViewAll,
  onSelect,
  engagement = false,
  labelFallback = "(none)",
}: {
  title: string;
  rows: PageRow[];
  metric: string;
  limit?: number;
  onViewAll?: () => void;
  /** When set, each row becomes a click-to-filter button (page drill-down). */
  onSelect?: (label: string) => void;
  /** Show avg time-on-page + bounce columns (engagement ranking). */
  engagement?: boolean;
  labelFallback?: string;
}) {
  const shown = limit ? rows.slice(0, limit) : rows;
  const max = Math.max(1, ...shown.map((r) => r.count));

  return (
    <div className="flex flex-col rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-muted-foreground">{title}</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground capitalize">{metric}</span>
          {onViewAll && rows.length > 0 && (
            <Button variant="ghost" size="xs" onClick={onViewAll}>
              View all
            </Button>
          )}
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">No data in this range</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {shown.map((r) => {
            const inner = (
              <>
                <span
                  className="absolute inset-y-0 left-0 rounded-md bg-primary/10"
                  style={{ width: `${Math.round((r.count / max) * 100)}%` }}
                  aria-hidden
                />
                <span className="relative min-w-0 flex-1 truncate font-mono text-sm">
                  {r.label || labelFallback}
                </span>
                {engagement && (
                  <>
                    <span className="relative w-16 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
                      {r.avg_duration != null ? formatDuration(r.avg_duration) : "—"}
                    </span>
                    <span className="relative w-14 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
                      {r.bounce_rate != null ? `${r.bounce_rate}%` : "—"}
                    </span>
                  </>
                )}
                <span className="relative shrink-0 text-sm font-medium tabular-nums">
                  {formatNumber(r.count)}
                </span>
                <span className="relative w-14 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
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
