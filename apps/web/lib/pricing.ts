// ONE source of pricing truth: the marketing slider renders from this now;
// the F5 billing UI and the Phase 14 metered-billing estimate must consume
// this same module. Rates are held as integer cents-per-1k and summed
// per-view pro-rata, rounding once at the end — so the advertised boundary
// bills are exact (10k → $8.91, 100k → $17.91, 1M → $62.91), no float drift.

export type PricingTier = {
  /** Upper bound of the tier in monthly pageviews; null = unbounded top tier. */
  upTo: number | null;
  /** Price for 1,000 views inside this tier, in cents. */
  centsPer1k: number;
};

export const FREE_MONTHLY_VIEWS = 1_000;

export const PRICING_TIERS: PricingTier[] = [
  { upTo: FREE_MONTHLY_VIEWS, centsPer1k: 0 },
  { upTo: 10_000, centsPer1k: 99 },
  { upTo: 100_000, centsPer1k: 10 },
  { upTo: 1_000_000, centsPer1k: 5 },
  { upTo: null, centsPer1k: 3 },
];

/** Graduated monthly bill in integer cents for a month's pageview count. */
export function estimateMonthlyBillCents(views: number): number {
  let remaining = Math.max(0, Math.floor(views));
  let lowerBound = 0;
  let cents = 0;
  for (const tier of PRICING_TIERS) {
    const capacity = tier.upTo === null ? remaining : tier.upTo - lowerBound;
    const inTier = Math.min(remaining, capacity);
    cents += (inTier * tier.centsPer1k) / 1000;
    remaining -= inTier;
    if (tier.upTo === null || remaining <= 0) break;
    lowerBound = tier.upTo;
  }
  return Math.round(cents);
}

/** Graduated monthly bill in dollars (for display). */
export function estimateMonthlyBill(views: number): number {
  return estimateMonthlyBillCents(views) / 100;
}

const usdFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function formatUsd(dollars: number): string {
  return usdFmt.format(dollars);
}
