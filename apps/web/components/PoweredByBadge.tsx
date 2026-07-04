import Link from "next/link";

// The free-tier "Powered by Flowly" badge shown on public shared dashboards
// (Phase 8). Paid tiers hide it (white-label is Phase 10); visibility is driven
// by the `show_badge` flag on the public dashboard payload.

export function PoweredByBadge() {
  return (
    <Link
      href="/"
      className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-500 shadow-sm hover:text-gray-700"
    >
      <span aria-hidden>📊</span>
      Powered by <span className="font-semibold text-gray-700">Flowly</span>
    </Link>
  );
}
