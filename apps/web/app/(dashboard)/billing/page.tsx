"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { useCheckout, usePortal, useUsage } from "@/hooks/useBilling";
import type { BillingInterval, BillingTier } from "@/lib/api";

const numberFmt = new Intl.NumberFormat();

const TIERS: { tier: BillingTier; label: string; blurb: string }[] = [
  { tier: "pro", label: "Pro", blurb: "For growing sites — up to 100k pageviews/mo." },
  { tier: "business", label: "Business", blurb: "For high traffic — up to 1M pageviews/mo." },
];

function UsageCard() {
  const { data, isLoading } = useUsage();
  if (isLoading || !data) {
    return <div className="rounded border border-gray-300 p-4 text-sm text-gray-600">Loading…</div>;
  }
  const pct = Math.min(100, Math.round(data.pct));
  const barColor =
    data.status === "over" ? "bg-red-500" : data.status === "warning" ? "bg-amber-500" : "bg-black";

  return (
    <div className="flex flex-col gap-3 rounded border border-gray-300 p-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600">Current plan</div>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium capitalize">
          {data.plan}
        </span>
      </div>
      <div className="text-2xl font-semibold tabular-nums">
        {numberFmt.format(data.used)}
        <span className="text-base font-normal text-gray-500">
          {" "}
          / {numberFmt.format(data.quota)} pageviews this month
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
        <div className={`h-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      {data.status === "over" ? (
        <p className="text-sm text-red-700">
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
      <div className="rounded border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-800">
        Thanks! Your subscription is being activated — it&apos;ll appear here in a moment.
      </div>
    );
  }
  if (state === "cancel") {
    return (
      <div className="rounded border border-gray-300 bg-gray-50 px-4 py-2 text-sm text-gray-700">
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
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Billing</h1>
        <Link href="/dashboard" className="text-sm text-gray-600 underline">
          ← Dashboard
        </Link>
      </div>

      <CheckoutReturn />
      <UsageCard />

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-gray-600">Plans</h2>
        {TIERS.map((t) => (
          <div
            key={t.tier}
            className="flex flex-wrap items-center justify-between gap-3 rounded border border-gray-300 p-4"
          >
            <div>
              <div className="font-medium">{t.label}</div>
              <div className="text-sm text-gray-600">{t.blurb}</div>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => upgrade(t.tier, "monthly")}
                disabled={checkout.isPending}
                className="rounded bg-black px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                Monthly
              </button>
              <button
                type="button"
                onClick={() => upgrade(t.tier, "annual")}
                disabled={checkout.isPending}
                className="rounded border border-black px-3 py-2 text-sm disabled:opacity-50"
              >
                Annual
              </button>
            </div>
          </div>
        ))}
        {checkout.isError ? (
          <p className="text-sm text-red-600">{checkout.error.message}</p>
        ) : null}
      </div>

      <div className="flex flex-col gap-2 border-t border-gray-200 pt-4">
        <h2 className="text-sm font-semibold text-gray-600">Manage subscription</h2>
        <button
          type="button"
          onClick={() => portal.mutate()}
          disabled={portal.isPending}
          className="self-start text-sm text-gray-600 underline disabled:opacity-50"
        >
          {portal.isPending ? "Opening…" : "Open customer portal"}
        </button>
        {portal.isError ? (
          <p className="text-sm text-red-600">{portal.error.message}</p>
        ) : null}
      </div>
    </main>
  );
}
