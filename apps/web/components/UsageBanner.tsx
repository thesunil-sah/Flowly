"use client";

import Link from "next/link";

import { useUsage } from "@/hooks/useBilling";
import { estimateMonthlyBill, formatUsd, FREE_MONTHLY_VIEWS } from "@/lib/pricing";
import { formatNumber } from "@/lib/format";

// The dashboard-wide usage strip (F5). Three states, all driven by
// usage_summary flags (never blocks the dashboard — that's the Phase 14
// PaywallModal's job once the 402 lock lands):
//   • warning  — free account approaching the limit (amber)
//   • over/locked — free account past the limit (red nudge → upgrade)
//   • bill-estimate — paying account with usage, running month-to-date estimate
export function UsageBanner() {
  const { data } = useUsage();
  if (!data) return null;

  const paying = data.plan !== "free";

  // Paying accounts: a quiet month-to-date bill estimate (only once there's a
  // bill to show, i.e. past the free allotment).
  if (paying) {
    if (data.used <= FREE_MONTHLY_VIEWS) return null;
    const bill = formatUsd(estimateMonthlyBill(data.used));
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/40 px-6 py-2 text-sm text-muted-foreground">
        <span>
          <span className="font-medium text-foreground tabular-nums">{formatNumber(data.used)}</span>{" "}
          pageviews this month · estimated bill{" "}
          <span className="font-medium text-foreground tabular-nums">{bill}</span>
        </span>
        <Link href="/billing" className="font-medium text-foreground underline">
          Billing
        </Link>
      </div>
    );
  }

  // Free accounts: warning → locked nudges.
  if (data.status === "ok") return null;

  const blocked = data.status === "locked";
  const tone = blocked ? "border-destructive/30 bg-destructive/10" : "border-warning/30 bg-warning/10";
  const pct = Math.round(data.pct);
  const message = blocked
    ? `You've used ${pct}% of your free monthly pageviews. Upgrade to keep your reports accurate.`
    : `You're at ${pct}% of your free monthly pageviews.`;

  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 border-b px-6 py-2 text-sm ${tone}`}>
      <span>{message}</span>
      <Link href="/billing" className="font-medium underline">
        {blocked ? "Upgrade now" : "View pricing"}
      </Link>
    </div>
  );
}
