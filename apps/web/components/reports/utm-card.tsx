"use client";

import type { UtmRow } from "@/lib/api";
import { formatNumber } from "@/lib/format";

// UTM campaigns table (full share page only — the hero embed omits it).
export function UtmCard({ rows }: { rows: UtmRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-card">
      <h2 className="mb-2 text-sm font-semibold text-muted-foreground">UTM campaigns</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted-foreground">
            <th className="font-normal">Source</th>
            <th className="font-normal">Medium</th>
            <th className="font-normal">Campaign</th>
            <th className="w-20 text-right font-normal">Visitors</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              <td className="truncate py-1.5">{r.utm_source}</td>
              <td className="truncate py-1.5 text-muted-foreground">{r.utm_medium || "—"}</td>
              <td className="truncate py-1.5 text-muted-foreground">{r.utm_campaign || "—"}</td>
              <td className="py-1.5 text-right tabular-nums">{formatNumber(r.visitors)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
