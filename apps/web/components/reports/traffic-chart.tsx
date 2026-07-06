"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  axisProps,
  ChartGradient,
  ChartTooltip,
  gridProps,
} from "@/components/charts/chart-theme";
import type { Timeseries } from "@/lib/api";
import { formatCompact } from "@/lib/format";

// Premium traffic chart card: indigo area + gradient over the F0 chart theme.
// Presentational — data in, height configurable (embed uses ~200).
export function TrafficChartCard({
  data,
  height = 260,
  title = "Traffic over time",
}: {
  data: Timeseries;
  height?: number;
  title?: string;
}) {
  const isHour = data.interval === "hour";
  const tick = (iso: string) => {
    const d = new Date(iso);
    return isHour
      ? d.toLocaleTimeString([], { hour: "2-digit" })
      : d.toLocaleDateString([], { month: "short", day: "numeric" });
  };
  const points = data.points.map((p) => ({ ...p, label: tick(p.bucket) }));

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-card">
      <h2 className="mb-3 text-sm font-semibold text-muted-foreground">{title}</h2>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
            <defs>
              <ChartGradient id="reportTrafficGradient" color="var(--chart-1)" />
            </defs>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="label" minTickGap={24} {...axisProps} />
            <YAxis allowDecimals={false} width={40} tickFormatter={formatCompact} {...axisProps} />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--border)" }} />
            <Area
              type="monotone"
              dataKey="visitors"
              stroke="var(--chart-1)"
              strokeWidth={2}
              fill="url(#reportTrafficGradient)"
              dot={false}
              name="Visitors"
            />
            <Line
              type="monotone"
              dataKey="pageviews"
              stroke="var(--chart-2)"
              strokeWidth={2}
              dot={false}
              name="Pageviews"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
