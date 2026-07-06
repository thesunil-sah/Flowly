"use client";

import type { Heatmap } from "@/lib/api";
import { formatNumber } from "@/lib/format";

// Time-of-day / day-of-week heatmap (Phase 10). A 7×24 grid of cells whose
// intensity is the pageview share of the busiest cell, rendered with the indigo
// chart token at varying opacity (tokens only — no raw color, honors the grep
// gate). Buckets are already localized to the viewer's timezone by the server.

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]; // dow 1..7

export function HeatmapCard({ data }: { data: Heatmap }) {
  // Index cells by (dow, hour) for O(1) lookup while laying out the grid.
  const byCell = new Map(data.cells.map((c) => [`${c.dow}:${c.hour}`, c]));
  const max = Math.max(1, ...data.cells.map((c) => c.pageviews));

  return (
    <div className="flex flex-col rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-muted-foreground">Activity by hour</h2>
        <span className="text-xs text-muted-foreground">{data.timezone}</span>
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[34rem]">
          {/* hour axis */}
          <div className="mb-1 flex pl-9 text-[10px] text-muted-foreground">
            {Array.from({ length: 24 }, (_, h) => (
              <span key={h} className="flex-1 text-center tabular-nums">
                {h % 6 === 0 ? h : ""}
              </span>
            ))}
          </div>
          {DAY_LABELS.map((label, i) => {
            const dow = i + 1;
            return (
              <div key={dow} className="flex items-center gap-1">
                <span className="w-8 shrink-0 text-[10px] text-muted-foreground">{label}</span>
                <div className="flex flex-1 gap-0.5">
                  {Array.from({ length: 24 }, (_, hour) => {
                    const cell = byCell.get(`${dow}:${hour}`);
                    const pv = cell?.pageviews ?? 0;
                    // Floor a visible tint so non-zero cells never look empty.
                    const opacity = pv === 0 ? 0 : 0.15 + (pv / max) * 0.85;
                    return (
                      <div
                        key={hour}
                        className="h-4 flex-1 rounded-[3px] bg-muted"
                        title={`${label} ${hour}:00 — ${formatNumber(pv)} pageviews`}
                      >
                        <div
                          className="h-full w-full rounded-[3px] bg-chart-1"
                          style={{ opacity }}
                          aria-hidden
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
