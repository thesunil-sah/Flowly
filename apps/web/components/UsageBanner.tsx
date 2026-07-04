"use client";

import Link from "next/link";

import { useUsage } from "@/hooks/useBilling";

// The soft-cap nudge (Phase 7): amber at >=80%, red at >=100%. It only nudges —
// it never blocks the dashboard, and data keeps ingesting past the quota.
export function UsageBanner() {
  const { data } = useUsage();
  if (!data || data.status === "ok") return null;

  const over = data.status === "over";
  const tone = over
    ? "bg-red-50 text-red-800 border-red-200"
    : "bg-amber-50 text-amber-800 border-amber-200";
  const pct = Math.round(data.pct);
  const message = over
    ? `You've used ${pct}% of your ${data.plan} plan's monthly pageviews. Upgrade to keep your reports accurate.`
    : `You're at ${pct}% of your ${data.plan} plan's monthly pageviews.`;

  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 border-b px-6 py-2 text-sm ${tone}`}>
      <span>{message}</span>
      <Link href="/billing" className="font-medium underline">
        {over ? "Upgrade now" : "View plans"}
      </Link>
    </div>
  );
}
