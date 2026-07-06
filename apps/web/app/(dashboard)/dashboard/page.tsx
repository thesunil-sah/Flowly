"use client";

import Link from "next/link";
import { LayoutGrid } from "lucide-react";
import { useMemo, useState } from "react";

import { useActiveSite } from "@/components/layout/site-context";
import { SegmentedTabs } from "@/components/segmented-tabs";
import { PageSkeleton } from "@/components/skeletons";
import {
  BreakdownTable,
  MetricCards,
  PagesTable,
  TrafficChart,
  UtmTable,
} from "@/components/stats";
import { ShareControl } from "@/components/ShareControl";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  useAudience,
  usePages,
  useOverview,
  useSources,
  useTimeseries,
  type AudienceDimension,
  type PageKind,
} from "@/hooks/useStats";
import { downloadExportCsv, type StatsRange } from "@/lib/api";

const PRESETS = [
  { key: "24h", label: "24h", days: 1 },
  { key: "7d", label: "7 days", days: 7 },
  { key: "30d", label: "30 days", days: 30 },
] as const;

const AUDIENCE_TABS: { key: AudienceDimension; label: string }[] = [
  { key: "country", label: "Countries" },
  { key: "device", label: "Devices" },
  { key: "browser", label: "Browsers" },
  { key: "os", label: "OS" },
];

const PAGE_TABS: { key: PageKind; label: string }[] = [
  { key: "top", label: "Top" },
  { key: "entry", label: "Entry" },
  { key: "exit", label: "Exit" },
];

function rangeForDays(days: number): StatsRange {
  const to = new Date();
  const from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000);
  return { from: from.toISOString(), to: to.toISOString() };
}

function StatsView({ siteId, range }: { siteId: string; range: StatsRange }) {
  const [dimension, setDimension] = useState<AudienceDimension>("country");
  const [pageKind, setPageKind] = useState<PageKind>("top");

  const overview = useOverview(siteId, range);
  const timeseries = useTimeseries(siteId, range);
  const sources = useSources(siteId, range);
  const audience = useAudience(siteId, range, dimension);
  const pages = usePages(siteId, range, pageKind);

  return (
    <div className="flex flex-col gap-4">
      {overview.data ? (
        <MetricCards data={overview.data} />
      ) : (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          {overview.isError ? "Couldn't load metrics." : "Loading metrics…"}
        </div>
      )}

      {timeseries.data && <TrafficChart data={timeseries.data} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <BreakdownTable title="Sources" rows={sources.data?.sources ?? []} labelFallback="direct" />

        <div className="rounded-lg border border-border bg-card p-4 shadow-card">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-muted-foreground">Audience</h2>
            <SegmentedTabs tabs={AUDIENCE_TABS} active={dimension} onChange={setDimension} />
          </div>
          <BreakdownTable title="" rows={audience.data?.rows ?? []} labelFallback="Unknown" />
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4 shadow-card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-muted-foreground">Pages</h2>
          <SegmentedTabs tabs={PAGE_TABS} active={pageKind} onChange={setPageKind} />
        </div>
        <PagesTable rows={pages.data?.rows ?? []} metric={pages.data?.metric ?? "pageviews"} />
      </div>

      {sources.data && <UtmTable rows={sources.data.utm} />}

      <ShareControl siteId={siteId} />
    </div>
  );
}

export default function DashboardPage() {
  const { activeSiteId, sites, isLoading } = useActiveSite();
  const [presetDays, setPresetDays] = useState(7);
  // Freeze the window when the preset changes so query keys don't churn on every
  // render; re-selecting a preset refreshes "now".
  const range = useMemo(() => rangeForDays(presetDays), [presetDays]);

  if (isLoading) {
    return <PageSkeleton />;
  }

  if (sites.length === 0 || !activeSiteId) {
    return (
      <EmptyState
        icon={LayoutGrid}
        title="No sites yet"
        description="Add a site and install the snippet to start seeing your traffic."
        action={
          <Button asChild>
            <Link href="/sites">Add a site</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="flex items-center gap-2">
          <SegmentedTabs
            tabs={PRESETS.map((p) => ({ key: p.key, label: p.label }))}
            active={PRESETS.find((p) => p.days === presetDays)!.key}
            onChange={(key) => setPresetDays(PRESETS.find((p) => p.key === key)!.days)}
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => downloadExportCsv(activeSiteId, range, "overview")}
          >
            Export CSV
          </Button>
        </div>
      </div>

      <StatsView key={activeSiteId} siteId={activeSiteId} range={range} />
    </div>
  );
}
