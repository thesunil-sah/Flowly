"use client";

import { useState } from "react";

import { Slider } from "@/components/ui/slider";
import { formatCompact } from "@/lib/format";
import { estimateMonthlyBill, formatUsd } from "@/lib/pricing";

// Interactive "what would I pay" slider over the graduated schedule. Snap
// points instead of a continuous scale: log-ish spacing is honest about the
// interesting range without pretending per-view precision matters here.
const SNAP_POINTS = [
  1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 2_500_000,
  5_000_000,
] as const;

export function PricingSlider() {
  const [index, setIndex] = useState(6); // 100k — the comparison-friendly midpoint
  const views = SNAP_POINTS[index];
  const bill = estimateMonthlyBill(views);

  return (
    <div className="flex flex-col gap-4">
      <Slider
        value={[index]}
        onValueChange={([v]) => setIndex(v)}
        min={0}
        max={SNAP_POINTS.length - 1}
        step={1}
        aria-label="Monthly pageviews"
      />
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm text-muted-foreground">
          <span className="font-semibold text-foreground tabular-nums">
            {formatCompact(views)}
          </span>{" "}
          pageviews / month
        </span>
        <span className="text-sm text-muted-foreground">
          ≈{" "}
          <span className="text-2xl font-bold text-foreground tabular-nums">
            {formatUsd(bill)}
          </span>{" "}
          / month
        </span>
      </div>
    </div>
  );
}
