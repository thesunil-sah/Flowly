"use client";

import { useSearchParams } from "next/navigation";

import { TableSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { useCheckout, usePortal, useUsage } from "@/hooks/useBilling";
import type { BillingInterval, BillingTier } from "@/lib/api";
import { formatNumber } from "@/lib/format";

const TIERS: { tier: BillingTier; label: string; blurb: string }[] = [
  { tier: "pro", label: "Pro", blurb: "For growing sites — up to 100k pageviews/mo." },
  { tier: "business", label: "Business", blurb: "For high traffic — up to 1M pageviews/mo." },
];

function UsageCard() {
  const { data, isLoading } = useUsage();
  if (isLoading || !data) {
    return <TableSkeleton rows={3} />;
  }
  const pct = Math.min(100, Math.round(data.pct));
  const barColor =
    data.status === "over" ? "bg-destructive" : data.status === "warning" ? "bg-warning" : "bg-primary";

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">Current plan</div>
        <span className="rounded-full bg-muted px-3 py-1 text-sm font-medium capitalize">
          {data.plan}
        </span>
      </div>
      <div className="text-2xl font-semibold tabular-nums">
        {formatNumber(data.used)}
        <span className="text-base font-normal text-muted-foreground">
          {" "}
          / {formatNumber(data.quota)} pageviews this month
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className={`h-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      {data.status === "over" ? (
        <p className="text-sm text-destructive">
          You&apos;re over your monthly quota. Your data is still being collected — upgrade to keep
          your reports accurate.
        </p>
      ) : null}
    </div>
  );
}

function CheckoutReturn() {
  const params = useSearchParams();
  const state = params.get("checkout");
  if (state === "success") {
    return (
      <div className="rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm">
        Thanks! Your subscription is being activated — it&apos;ll appear here in a moment.
      </div>
    );
  }
  if (state === "cancel") {
    return (
      <div className="rounded-lg border border-border bg-muted px-4 py-2 text-sm text-muted-foreground">
        Checkout canceled — no charge was made.
      </div>
    );
  }
  return null;
}

export default function BillingPage() {
  const checkout = useCheckout();
  const portal = usePortal();

  function upgrade(tier: BillingTier, interval: BillingInterval) {
    checkout.mutate({ tier, interval });
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">Billing</h1>

      <CheckoutReturn />
      <UsageCard />

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-muted-foreground">Plans</h2>
        {TIERS.map((t) => (
          <div
            key={t.tier}
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-4 shadow-card"
          >
            <div>
              <div className="font-medium">{t.label}</div>
              <div className="text-sm text-muted-foreground">{t.blurb}</div>
            </div>
            <div className="flex gap-2">
              <Button onClick={() => upgrade(t.tier, "monthly")} disabled={checkout.isPending}>
                Monthly
              </Button>
              <Button
                variant="outline"
                onClick={() => upgrade(t.tier, "annual")}
                disabled={checkout.isPending}
              >
                Annual
              </Button>
            </div>
          </div>
        ))}
        {checkout.isError ? (
          <p className="text-sm text-destructive">{checkout.error.message}</p>
        ) : null}
      </div>

      <div className="flex flex-col gap-2 border-t border-border pt-4">
        <h2 className="text-sm font-semibold text-muted-foreground">Manage subscription</h2>
        <Button
          variant="link"
          className="self-start px-0"
          onClick={() => portal.mutate()}
          disabled={portal.isPending}
        >
          {portal.isPending ? "Opening…" : "Open customer portal"}
        </Button>
        {portal.isError ? (
          <p className="text-sm text-destructive">{portal.error.message}</p>
        ) : null}
      </div>
    </div>
  );
}
