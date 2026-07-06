"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { CountUp } from "@/components/motion";
import type { MetricDelta, Overview } from "@/lib/api";
import { formatDuration, formatNumber, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

// Delta stat cards (phpAnalytics reference). Presentational: data in, no
// hooks — the share page, the hero demo embed, and the sample fallback all
// render these same cards.

function DeltaBadge({ delta, invert }: { delta: MetricDelta; invert?: boolean }) {
  if (delta.change_pct === null) return null;
  const up = delta.change_pct > 0;
  const flat = delta.change_pct === 0;
  // For most metrics up is good; for bounce rate lower is better, so invert.
  const good = invert ? !up : up;
  const Arrow = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-medium",
        flat
          ? "bg-muted text-muted-foreground"
          : good
            ? "bg-success/10 text-success"
            : "bg-destructive/10 text-destructive",
      )}
    >
      {!flat && <Arrow className="size-3" aria-hidden />}
      {Math.abs(delta.change_pct)}%
    </span>
  );
}

function StatCard({
  label,
  delta,
  format,
  invert,
  animate,
}: {
  label: string;
  delta: MetricDelta;
  format: (n: number) => string;
  invert?: boolean;
  animate?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-1 flex items-baseline justify-between gap-2">
        <span className="text-2xl font-semibold tabular-nums">
          {animate ? <CountUp value={delta.value} format={format} /> : format(delta.value)}
        </span>
        <DeltaBadge delta={delta} invert={invert} />
      </div>
    </div>
  );
}

export function StatCards({
  data,
  animate = false,
  compact = false,
}: {
  data: Overview;
  animate?: boolean;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid gap-3",
        compact ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5",
      )}
    >
      <StatCard label="Visitors" delta={data.visitors} format={formatNumber} animate={animate} />
      <StatCard label="Pageviews" delta={data.pageviews} format={formatNumber} animate={animate} />
      {!compact && (
        <StatCard label="Sessions" delta={data.sessions} format={formatNumber} animate={animate} />
      )}
      <StatCard
        label="Bounce rate"
        delta={data.bounce_rate}
        format={formatPercent}
        invert
        animate={animate}
      />
      <StatCard
        label="Avg. duration"
        delta={data.avg_duration}
        format={formatDuration}
        animate={animate}
      />
    </div>
  );
}
