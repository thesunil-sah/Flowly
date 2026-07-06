import Link from "next/link";

// The free-tier "Powered by Flowly" badge shown on public shared dashboards
// (Phase 8). Paid tiers hide it (white-label is Phase 15); visibility is driven
// by the `show_badge` flag on the public dashboard payload.

export function PoweredByBadge() {
  return (
    <Link
      href="/"
      className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground shadow-card hover:text-foreground"
    >
      <span aria-hidden>📊</span>
      Powered by <span className="font-semibold text-foreground">Flowly</span>
    </Link>
  );
}
