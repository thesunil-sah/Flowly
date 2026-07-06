import type { Overview, Pages, Sources, Timeseries } from "@/lib/api";

// Static sample data for the landing-page demo frame when no
// NEXT_PUBLIC_DEMO_SHARE_TOKEN is configured (or the share API is
// unreachable). Always rendered with a visible "Sample data" caption —
// plausible numbers, honestly labeled.

export const SAMPLE_DOMAIN = "demo.flowly.app";

export const SAMPLE_OVERVIEW: Overview = {
  visitors: { value: 1_824, previous: 1_561, change_pct: 16.8 },
  pageviews: { value: 4_312, previous: 3_988, change_pct: 8.1 },
  sessions: { value: 2_102, previous: 1_930, change_pct: 8.9 },
  bounce_rate: { value: 42.6, previous: 45.1, change_pct: -5.5 },
  avg_duration: { value: 127, previous: 118, change_pct: 7.6 },
};

/** Last-7-days daily buckets ending today, so the sample never looks stale. */
export function sampleTimeseries(): Timeseries {
  const visitors = [212, 248, 231, 296, 305, 262, 270];
  const pageviews = [498, 571, 540, 703, 731, 615, 654];
  const day = 24 * 60 * 60 * 1000;
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  return {
    interval: "day",
    points: visitors.map((v, i) => ({
      bucket: new Date(today.getTime() - (6 - i) * day).toISOString(),
      visitors: v,
      pageviews: pageviews[i],
    })),
  };
}

export const SAMPLE_SOURCES: Sources = {
  sources: [
    { label: "direct", visitors: 612, pageviews: 1_402 },
    { label: "google.com", visitors: 488, pageviews: 1_240 },
    { label: "news.ycombinator.com", visitors: 271, pageviews: 689 },
    { label: "x.com", visitors: 182, pageviews: 402 },
    { label: "reddit.com", visitors: 141, pageviews: 328 },
  ],
  utm: [],
};

export const SAMPLE_PAGES: Pages = {
  kind: "top",
  metric: "pageviews",
  rows: [
    { label: "/", count: 1_671, visitors: 1_204 },
    { label: "/pricing", count: 842, visitors: 705 },
    { label: "/blog/cookieless-analytics", count: 611, visitors: 548 },
    { label: "/docs", count: 502, visitors: 371 },
    { label: "/changelog", count: 286, visitors: 232 },
  ],
};
