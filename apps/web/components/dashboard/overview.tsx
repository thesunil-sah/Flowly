"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Radio } from "lucide-react";

import { BreakdownCard } from "@/components/reports/breakdown-card";
import { PagesCard } from "@/components/reports/pages-card";
import { CountryIcon, SourceIcon } from "@/components/reports/row-icon";
import { StatCards } from "@/components/reports/stat-cards";
import { TrafficChartCard } from "@/components/reports/traffic-chart";
import { UtmCard } from "@/components/reports/utm-card";
import { useRange } from "@/components/layout/range-context";
import { ShareControl } from "@/components/ShareControl";
import { ChartSkeleton, MetricCardsSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useAudience, useOverview, usePages, useSources, useTimeseries } from "@/hooks/useStats";

// The authed Overview: a premium composition of the reports kit fed by the
// authed stats hooks, mirroring the public share dashboard's overview section.
// "View all" on each summary card routes to that report's sidebar destination.

export function OverviewReport({ siteId }: { siteId: string }) {
  const router = useRouter();
  const { range } = useRange();

  const overview = useOverview(siteId, range);
  const timeseries = useTimeseries(siteId, range);
  const sources = useSources(siteId, range);
  const countries = useAudience(siteId, range, "country");
  const topPages = usePages(siteId, range, "top");

  // A loaded-but-empty overview means the snippet hasn't sent data yet (in this
  // window) — nudge toward install rather than showing a wall of zeros.
  const isEmpty =
    overview.data != null &&
    overview.data.pageviews.value === 0 &&
    overview.data.visitors.value === 0;

  if (isEmpty) {
    return (
      <EmptyState
        icon={Radio}
        title="No data yet"
        description="We haven't received any pageviews in this range. Install your snippet to start tracking."
        action={
          <Button asChild>
            <Link href="/sites">View install snippet</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {overview.data ? (
        <StatCards data={overview.data} animate />
      ) : overview.isError ? (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          Couldn&apos;t load metrics.
        </div>
      ) : (
        <MetricCardsSkeleton />
      )}

      {timeseries.data ? <TrafficChartCard data={timeseries.data} /> : <ChartSkeleton />}

      <div className="grid gap-4 lg:grid-cols-3">
        <BreakdownCard
          title="Sources"
          rows={sources.data?.sources ?? []}
          icon={(label) => <SourceIcon label={label} />}
          labelFallback="direct"
          limit={6}
          onViewAll={() => router.push("/acquisitions/referrers")}
        />
        <BreakdownCard
          title="Countries"
          rows={countries.data?.rows ?? []}
          icon={(label) => <CountryIcon code={label} />}
          labelFallback="Unknown"
          limit={6}
          onViewAll={() => router.push("/geo/countries")}
        />
        <PagesCard
          title="Top pages"
          rows={topPages.data?.rows ?? []}
          metric={topPages.data?.metric ?? "pageviews"}
          limit={6}
          onViewAll={() => router.push("/behavior/pages")}
        />
      </div>

      {sources.data && sources.data.utm.length > 0 ? <UtmCard rows={sources.data.utm} /> : null}

      <ShareControl siteId={siteId} />
    </div>
  );
}
