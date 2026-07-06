"use client";

import { formatNumber } from "@/lib/format";

// Recharts theme: every color is a CSS variable from globals.css, passed
// straight into SVG attributes — the cascade resolves var() per theme, so
// charts flip light/dark with zero JS. Never hex literals here or in charts.

export const CHART_SERIES = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
] as const;

export const gridProps = {
  stroke: "var(--border)",
  strokeDasharray: "3 3",
  vertical: false,
} as const;

export const axisProps = {
  tick: { fill: "var(--muted-foreground)", fontSize: 12 },
  tickLine: false,
  axisLine: false,
} as const;

/** Soft fade-to-transparent fill for <Area>; render inside <defs>. */
export function ChartGradient({ id, color }: { id: string; color: string }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor={color} stopOpacity={0.25} />
      <stop offset="100%" stopColor={color} stopOpacity={0} />
    </linearGradient>
  );
}

type TooltipEntry = {
  name?: string | number;
  value?: number | string;
  color?: string;
};

/** Custom tooltip content: pass as `content={<ChartTooltip />}`. */
export function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: ReadonlyArray<TooltipEntry>;
  label?: string | number;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md">
      {label !== undefined && (
        <div className="mb-1 font-medium text-popover-foreground">{label}</div>
      )}
      <ul className="space-y-0.5">
        {payload.map((entry, i) => (
          <li key={i} className="flex items-center gap-2 text-muted-foreground">
            <span
              className="inline-block size-2 rounded-full"
              style={{ background: entry.color }}
              aria-hidden
            />
            <span>{entry.name}</span>
            <span className="ml-auto pl-3 font-medium tabular-nums text-popover-foreground">
              {typeof entry.value === "number" ? formatNumber(entry.value) : entry.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
