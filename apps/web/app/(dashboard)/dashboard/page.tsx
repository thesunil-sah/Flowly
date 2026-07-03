"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import {
  BreakdownTable,
  MetricCards,
  PagesTable,
  TrafficChart,
  UtmTable,
} from "@/components/stats";
import {
  useAudience,
  usePages,
  useOverview,
  useSources,
  useTimeseries,
  type AudienceDimension,
  type PageKind,
} from "@/hooks/useStats";
import { useSites } from "@/hooks/useSites";
import type { StatsRange } from "@/lib/api";

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

function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: T; label: string }[];
  active: T;
  onChange: (key: T) => void;
}) {
  return (
    <div className="flex gap-1">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={`rounded px-2 py-1 text-xs ${
            active === t.key ? "bg-black text-white" : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
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
        <div className="rounded border border-gray-300 p-6 text-sm text-gray-400">
          {overview.isError ? "Couldn't load metrics." : "Loading metrics…"}
        </div>
      )}

      {timeseries.data && <TrafficChart data={timeseries.data} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <BreakdownTable title="Sources" rows={sources.data?.sources ?? []} labelFallback="direct" />

        <div className="rounded border border-gray-300 p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-600">Audience</h2>
            <Tabs tabs={AUDIENCE_TABS} active={dimension} onChange={setDimension} />
          </div>
          <BreakdownTable title="" rows={audience.data?.rows ?? []} labelFallback="Unknown" />
        </div>
      </div>

      <div className="rounded border border-gray-300 p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-600">Pages</h2>
          <Tabs tabs={PAGE_TABS} active={pageKind} onChange={setPageKind} />
        </div>
        <PagesTable rows={pages.data?.rows ?? []} metric={pages.data?.metric ?? "pageviews"} />
      </div>

      {sources.data && <UtmTable rows={sources.data.utm} />}
    </div>
  );
}

export default function DashboardPage() {
  const { data: sites, isLoading } = useSites();
  const [selected, setSelected] = useState<string | null>(null);
  const [presetDays, setPresetDays] = useState(7);
  // Freeze the window when the preset changes so query keys don't churn on every
  // render; re-selecting a preset refreshes "now".
  const range = useMemo(() => rangeForDays(presetDays), [presetDays]);

  if (isLoading) {
    return <main className="flex flex-1 items-center justify-center p-6">Loading…</main>;
  }

  if (!sites || sites.length === 0) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-2 p-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-gray-600">No sites yet. Add one to start seeing your traffic.</p>
        <Link href="/sites" className="rounded bg-black px-4 py-2 text-sm text-white">
          Add a site
        </Link>
      </main>
    );
  }

  const activeSiteId = selected ?? sites[0].site_id;

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          {sites.length > 1 && (
            <select
              value={activeSiteId}
              onChange={(e) => setSelected(e.target.value)}
              className="rounded border border-gray-300 px-3 py-1.5 text-sm"
            >
              {sites.map((s) => (
                <option key={s.id} value={s.site_id}>
                  {s.domain}
                </option>
              ))}
            </select>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Tabs
            tabs={PRESETS.map((p) => ({ key: p.key, label: p.label }))}
            active={PRESETS.find((p) => p.days === presetDays)!.key}
            onChange={(key) => setPresetDays(PRESETS.find((p) => p.key === key)!.days)}
          />
          <Link href="/sites" className="text-sm text-gray-600 underline">
            Add site
          </Link>
          <Link href="/live" className="text-sm text-gray-600 underline">
            Live →
          </Link>
        </div>
      </div>

      <StatsView key={activeSiteId} siteId={activeSiteId} range={range} />
    </main>
  );
}
