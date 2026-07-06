"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { BreakdownCard } from "@/components/reports/breakdown-card";
import { LiveDot } from "@/components/reports/live-dot";
import { PagesCard } from "@/components/reports/pages-card";
import { SourceIcon } from "@/components/reports/row-icon";
import {
  SAMPLE_DOMAIN,
  SAMPLE_OVERVIEW,
  SAMPLE_PAGES,
  SAMPLE_SOURCES,
  sampleTimeseries,
} from "@/components/reports/sample-data";
import { StatCards } from "@/components/reports/stat-cards";
import { TrafficChartCard } from "@/components/reports/traffic-chart";
import { rangeForDays } from "@/components/public-dashboard/public-dashboard";
import { ChartSkeleton, MetricCardsSkeleton } from "@/components/skeletons";
import {
  usePublicMeta,
  usePublicOverview,
  usePublicPages,
  usePublicSources,
  usePublicTimeseries,
} from "@/hooks/usePublicStats";
import type { Overview, Pages, Sources, Timeseries } from "@/lib/api";

// The landing hero's demo dashboard: Flowly's own stats through the Phase 8
// public share API (token = NEXT_PUBLIC_DEMO_SHARE_TOKEN, public by design).
// No token / unreachable API → the SAME composition fed labeled sample data,
// so the marketing page never depends on a running backend.

const DEMO_TOKEN = process.env.NEXT_PUBLIC_DEMO_SHARE_TOKEN;

function DemoBody({
  domain,
  caption,
  overview,
  timeseries,
  sources,
  pages,
  exploreHref,
}: {
  domain: string;
  caption: string;
  overview: Overview;
  timeseries: Timeseries;
  sources: Sources;
  pages: Pages;
  exploreHref?: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <LiveDot />
        <span className="font-medium">{domain}</span>
        <span className="text-muted-foreground">· {caption}</span>
      </div>

      <StatCards data={overview} compact animate />
      <TrafficChartCard data={timeseries} height={200} />
      <div className="grid gap-3 sm:grid-cols-2">
        <BreakdownCard
          title="Top sources"
          rows={sources.sources}
          icon={(label) => <SourceIcon label={label} />}
          labelFallback="direct"
          limit={5}
        />
        <PagesCard
          title="Top pages"
          rows={pages.rows}
          metric={pages.metric}
          limit={5}
        />
      </div>

      {exploreHref && (
        <Link
          href={exploreHref}
          className="inline-flex items-center gap-1 self-end text-sm text-primary hover:underline"
        >
          Explore the full live demo
          <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      )}
    </div>
  );
}

function SampleDemo() {
  const [timeseries] = useState(() => sampleTimeseries());
  return (
    <DemoBody
      domain={SAMPLE_DOMAIN}
      caption="Sample data"
      overview={SAMPLE_OVERVIEW}
      timeseries={timeseries}
      sources={SAMPLE_SOURCES}
      pages={SAMPLE_PAGES}
    />
  );
}

function LiveDemo({ token }: { token: string }) {
  // Freeze the 7d window once — a fresh Date per render would mint a new
  // query key every render and refetch forever.
  const [range] = useState(() => rangeForDays(7));
  const meta = usePublicMeta(token);
  const overview = usePublicOverview(token, range, true, { refetchInterval: 60_000 });
  const timeseries = usePublicTimeseries(token, range);
  const sources = usePublicSources(token, range);
  const pages = usePublicPages(token, range, "top");

  // Revoked token or API down → the labeled sample, never an error flash.
  if (meta.isError || overview.isError) return <SampleDemo />;

  if (!meta.data || !overview.data || !timeseries.data || !sources.data || !pages.data) {
    return (
      <div className="flex flex-col gap-3">
        <MetricCardsSkeleton count={4} />
        <ChartSkeleton />
      </div>
    );
  }

  return (
    <DemoBody
      domain={meta.data.domain}
      caption="Live demo — last 7 days"
      overview={overview.data}
      timeseries={timeseries.data}
      sources={sources.data}
      pages={pages.data}
      exploreHref={`/share/${encodeURIComponent(token)}`}
    />
  );
}

export function DemoEmbed() {
  return (
    <div className="relative">
      {/* soft indigo glow behind the frame */}
      <div
        className="absolute -inset-4 rounded-3xl bg-primary/10 blur-2xl"
        aria-hidden
      />
      <div className="relative min-h-[560px] rounded-2xl border border-border bg-card p-4 shadow-lg ring-1 ring-primary/10 sm:p-5">
        {DEMO_TOKEN ? <LiveDemo token={DEMO_TOKEN} /> : <SampleDemo />}
      </div>
    </div>
  );
}
