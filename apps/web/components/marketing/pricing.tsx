import Link from "next/link";
import { Check } from "lucide-react";

import { PricingSlider } from "@/components/marketing/pricing-slider";
import { Button } from "@/components/ui/button";
import { formatNumber } from "@/lib/format";
import { PRICING_TIERS } from "@/lib/pricing";

// Metered pricing: free-vs-paying framing + the graduated rate table rendered
// server-side from PRICING_TIERS (one source of truth — lib/pricing.ts), NOT
// fixed plan tiers.

const FREE_FEATURES = [
  "1,000 pageviews / month",
  "Live visitors + all reports",
  "Public share links & CSV export",
  "30-day data retention",
] as const;

function tierLabel(lower: number, upTo: number | null): string {
  if (lower === 0) return `First ${formatNumber(upTo!)} views`;
  if (upTo === null) return `Over ${formatNumber(lower)}`;
  return `${formatNumber(lower)} – ${formatNumber(upTo)}`;
}

function tierRate(centsPer1k: number): string {
  if (centsPer1k === 0) return "Free";
  return `$${(centsPer1k / 100).toFixed(2)} / 1k`;
}

export function Pricing() {
  const rows = PRICING_TIERS.map((tier, i) => ({
    label: tierLabel(i === 0 ? 0 : PRICING_TIERS[i - 1].upTo!, tier.upTo),
    rate: tierRate(tier.centsPer1k),
  }));

  return (
    <section id="pricing" className="scroll-mt-20 bg-muted/40">
      <div className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Pay for what you use. Nothing more.
          </h2>
          <p className="mt-3 text-lg text-muted-foreground">
            No plans to outgrow, no jump from $9 to $19 — the rate falls as you scale.
          </p>
        </div>

        <div className="mx-auto grid max-w-4xl gap-4 lg:grid-cols-2">
          {/* Free */}
          <div className="flex flex-col rounded-lg border border-border bg-card p-6 shadow-card">
            <h3 className="font-semibold">Free</h3>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="text-4xl font-bold">$0</span>
              <span className="text-sm text-muted-foreground">forever</span>
            </div>
            <ul className="mt-5 flex flex-1 flex-col gap-2.5">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm">
                  <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                  {f}
                </li>
              ))}
            </ul>
            <Button variant="outline" className="mt-6 w-full" asChild>
              <Link href="/sign-up">Start for free</Link>
            </Button>
          </div>

          {/* Pay as you go */}
          <div className="flex flex-col rounded-lg border border-primary bg-card p-6 shadow-card ring-1 ring-primary/30">
            <h3 className="font-semibold">Pay as you go</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Metered — the same dashboard, billed only for the views you actually get.
            </p>
            <table className="mt-4 w-full text-sm">
              <tbody>
                {rows.map((r) => (
                  <tr key={r.label} className="border-t border-border first:border-t-0">
                    <td className="py-1.5 text-muted-foreground">{r.label}</td>
                    <td className="py-1.5 text-right font-medium tabular-nums">{r.rate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-5 border-t border-border pt-5">
              <PricingSlider />
            </div>
            <Button className="mt-6 w-full" asChild>
              <Link href="/sign-up">Start your 7-day free trial</Link>
            </Button>
          </div>
        </div>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          All your sites summed per account · up to 5 sites · 7-day free trial when you upgrade
        </p>
      </div>
    </section>
  );
}
