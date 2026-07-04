"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

import { PoweredByBadge } from "@/components/PoweredByBadge";
import {
  BreakdownTable,
  MetricCards,
  PagesTable,
  TrafficChart,
  UtmTable,
} from "@/components/stats";
import {
  usePublicAudience,
  usePublicMeta,
  usePublicOverview,
  usePublicPages,
  usePublicSources,
  usePublicTimeseries,
} from "@/hooks/usePublicStats";
import type { AudienceDimension, PageKind } from "@/hooks/useStats";
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

function PublicStatsView({ token, range }: { token: string; range: StatsRange }) {
  const [dimension, setDimension] = useState<AudienceDimension>("country");
  const [pageKind, setPageKind] = useState<PageKind>("top");

  const overview = usePublicOverview(token, range);
  const timeseries = usePublicTimeseries(token, range);
  const sources = usePublicSources(token, range);
  const audience = usePublicAudience(token, range, dimension);
  const pages = usePublicPages(token, range, pageKind);

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

export default function SharePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [presetDays, setPresetDays] = useState(7);
  const range = useMemo(() => rangeForDays(presetDays), [presetDays]);
  const meta = usePublicMeta(token);

  if (meta.isError) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-2 p-6">
        <h1 className="text-2xl font-semibold">Dashboard not found</h1>
        <p className="text-gray-600">This share link is invalid or has been revoked.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Shared dashboard</p>
          <h1 className="text-2xl font-semibold">{meta.data?.domain ?? "…"}</h1>
        </div>
        <Tabs
          tabs={PRESETS.map((p) => ({ key: p.key, label: p.label }))}
          active={PRESETS.find((p) => p.days === presetDays)!.key}
          onChange={(key) => setPresetDays(PRESETS.find((p) => p.key === key)!.days)}
        />
      </div>

      <PublicStatsView token={token} range={range} />

      {meta.data?.show_badge && (
        <div className="flex justify-center pt-2">
          <PoweredByBadge />
        </div>
      )}
    </main>
  );
}
