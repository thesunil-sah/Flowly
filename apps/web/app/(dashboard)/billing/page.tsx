"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { PaywallModal } from "@/components/PaywallModal";
import { TableSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { usePortal, useUsage } from "@/hooks/useBilling";
import { estimateMonthlyBill, formatUsd, FREE_MONTHLY_VIEWS } from "@/lib/pricing";
import { formatNumber } from "@/lib/format";

// F5 billing surface, oriented to the Phase 14 metered model: a usage meter, a
// month-to-date bill estimate from the ONE pricing source (lib/pricing.ts), and
// subscription management. Upgrading goes through the PaywallModal; managing an
// existing subscription goes to the Stripe Customer Portal.

function UsageEstimateCard() {
  const { data, isLoading } = useUsage();
  if (isLoading || !data) {
    return <TableSkeleton rows={3} />;
  }

  const pct = Math.min(100, Math.round(data.pct));
  const barColor =
    data.status === "locked"
      ? "bg-destructive"
      : data.status === "warning"
        ? "bg-warning"
        : "bg-primary";
  const bill = formatUsd(estimateMonthlyBill(data.used));

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5 shadow-card">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">Current plan</span>
        <span className="rounded-full bg-muted px-3 py-1 text-sm font-medium capitalize">
          {data.plan}
        </span>
      </div>

      <div>
        <div className="text-2xl font-semibold tabular-nums">
          {formatNumber(data.used)}
          <span className="text-base font-normal text-muted-foreground"> pageviews this month</span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
          <div className={`h-full ${barColor}`} style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="flex items-end justify-between border-t border-border pt-4">
        <div>
          <div className="text-sm text-muted-foreground">Estimated bill this month</div>
          <div className="text-xs text-muted-foreground">
            First {formatNumber(FREE_MONTHLY_VIEWS)} views free · the rate falls as you scale
          </div>
        </div>
        <div className="text-3xl font-bold tabular-nums">{bill}</div>
      </div>

      <Link href="/pricing" className="text-sm font-medium text-primary underline">
        See full pricing →
      </Link>
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
  const portal = usePortal();
  const [paywallOpen, setPaywallOpen] = useState(false);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <h1 className="text-2xl font-semibold">Billing</h1>

      <CheckoutReturn />
      <UsageEstimateCard />

      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-card">
        <div>
          <h2 className="font-medium">Pay as you go</h2>
          <p className="text-sm text-muted-foreground">
            Start a 7-day free trial, then pay only for the pageviews you actually get — across all
            your sites.
          </p>
        </div>
        <Button className="self-start" onClick={() => setPaywallOpen(true)}>
          Upgrade
        </Button>
      </div>

      <div className="flex flex-col gap-2 border-t border-border pt-4">
        <h2 className="text-sm font-semibold text-muted-foreground">Manage subscription</h2>
        <p className="text-sm text-muted-foreground">
          Update your card, download invoices, or cancel from the Stripe portal.
        </p>
        <Button
          variant="link"
          className="self-start px-0"
          onClick={() => portal.mutate()}
          disabled={portal.isPending}
        >
          {portal.isPending ? "Opening…" : "Open customer portal"}
        </Button>
        {portal.isError ? <p className="text-sm text-destructive">{portal.error.message}</p> : null}
      </div>

      <PaywallModal open={paywallOpen} onOpenChange={setPaywallOpen} />
    </div>
  );
}
