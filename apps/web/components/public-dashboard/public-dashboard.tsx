"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";

import { PoweredByBadge } from "@/components/PoweredByBadge";
import { BreakdownCard } from "@/components/reports/breakdown-card";
import { PagesCard } from "@/components/reports/pages-card";
import {
  BrowserIcon,
  CountryIcon,
  DeviceIcon,
  OsIcon,
  SourceIcon,
} from "@/components/reports/row-icon";
import { StatCards } from "@/components/reports/stat-cards";
import { TrafficChartCard } from "@/components/reports/traffic-chart";
import { UtmCard } from "@/components/reports/utm-card";
import { SegmentedTabs } from "@/components/segmented-tabs";
import { ChartSkeleton, MetricCardsSkeleton } from "@/components/skeletons";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  ReportSidebar,
  type PublicSection,
} from "@/components/public-dashboard/report-sidebar";
import type { AudienceDimension, PageKind } from "@/hooks/useStats";
import {
  usePublicAudience,
  usePublicMeta,
  usePublicOverview,
  usePublicPages,
  usePublicSources,
  usePublicTimeseries,
} from "@/hooks/usePublicStats";
import type { StatsRange } from "@/lib/api";

// The phpAnalytics-style public share dashboard: grouped report sidebar
// (in-page state), delta stat cards, icon-rich breakdown cards with
// "View all". Compositions only — all rendering lives in components/reports/.

const PRESETS = [
  { key: "24h", label: "24h", days: 1 },
  { key: "7d", label: "7 days", days: 7 },
  { key: "30d", label: "30 days", days: 30 },
] as const;

export function rangeForDays(days: number): StatsRange {
  const to = new Date();
  const from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000);
  return { from: from.toISOString(), to: to.toISOString() };
}

const AUDIENCE_TITLES: Record<AudienceDimension, string> = {
  country: "Countries",
  device: "Devices",
  browser: "Browsers",
  os: "OS",
};

function renderCountryIcon(label: string): ReactNode {
  return <CountryIcon code={label} />;
}
function renderDeviceIcon(label: string): ReactNode {
  return <DeviceIcon label={label} />;
}
function renderBrowserIcon(label: string): ReactNode {
  return <BrowserIcon label={label} />;
}
function renderOsIcon(): ReactNode {
  return <OsIcon />;
}

const AUDIENCE_ICONS: Record<AudienceDimension, (label: string) => ReactNode> = {
  country: renderCountryIcon,
  device: renderDeviceIcon,
  browser: renderBrowserIcon,
  os: renderOsIcon,
};

function SectionPanel({
  token,
  range,
  section,
  onSelect,
}: {
  token: string;
  range: StatsRange;
  section: PublicSection;
  onSelect: (s: PublicSection) => void;
}) {
  // Params derive from the active section; TanStack re-keys per param change.
  const dimension: AudienceDimension = section.startsWith("audience-")
    ? (section.slice("audience-".length) as AudienceDimension)
    : "country";
  const kind: PageKind = section.startsWith("pages-")
    ? (section.slice("pages-".length) as PageKind)
    : "top";

  const overview = usePublicOverview(token, range);
  const timeseries = usePublicTimeseries(token, range);
  const sources = usePublicSources(token, range);
  const audience = usePublicAudience(token, range, dimension);
  const pages = usePublicPages(token, range, kind);

  if (section === "overview") {
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
            onViewAll={() => onSelect("sources")}
          />
          <BreakdownCard
            title="Countries"
            rows={audience.data?.rows ?? []}
            icon={(label) => <CountryIcon code={label} />}
            labelFallback="Unknown"
            limit={6}
            onViewAll={() => onSelect("audience-country")}
          />
          <PagesCard
            title="Top pages"
            rows={pages.data?.rows ?? []}
            metric={pages.data?.metric ?? "pageviews"}
            limit={6}
            onViewAll={() => onSelect("pages-top")}
          />
        </div>
      </div>
    );
  }

  if (section.startsWith("pages-")) {
    const titles: Record<PageKind, string> = {
      top: "Top pages",
      entry: "Entry pages",
      exit: "Exit pages",
    };
    return (
      <PagesCard
        title={titles[kind]}
        rows={pages.data?.rows ?? []}
        metric={pages.data?.metric ?? "pageviews"}
        limit={25}
      />
    );
  }

  if (section === "sources") {
    return (
      <BreakdownCard
        title="Sources"
        rows={sources.data?.sources ?? []}
        icon={(label) => <SourceIcon label={label} />}
        labelFallback="direct"
        limit={25}
      />
    );
  }

  if (section === "campaigns") {
    return sources.data && sources.data.utm.length > 0 ? (
      <UtmCard rows={sources.data.utm} />
    ) : (
      <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
        No UTM campaign traffic in this range
      </div>
    );
  }

  return (
    <BreakdownCard
      title={AUDIENCE_TITLES[dimension]}
      rows={audience.data?.rows ?? []}
      icon={AUDIENCE_ICONS[dimension]}
      labelFallback="Unknown"
      limit={25}
    />
  );
}

export function PublicDashboard({ token }: { token: string }) {
  const [section, setSection] = useState<PublicSection>("overview");
  const [presetDays, setPresetDays] = useState(7);
  // Freeze the window per preset change so query keys don't churn each render.
  const range = useMemo(() => rangeForDays(presetDays), [presetDays]);
  const meta = usePublicMeta(token);

  if (meta.isError) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-2 p-6">
        <h1 className="text-2xl font-semibold">Dashboard not found</h1>
        <p className="text-muted-foreground">This share link is invalid or has been revoked.</p>
      </main>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 p-4 lg:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            Flowly
          </Link>
          <div className="h-5 w-px bg-border" aria-hidden />
          <div>
            <p className="text-xs tracking-wide text-muted-foreground uppercase">
              Public dashboard
            </p>
            <h1 className="text-lg leading-tight font-semibold">{meta.data?.domain ?? "…"}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SegmentedTabs
            tabs={PRESETS.map((p) => ({ key: p.key, label: p.label }))}
            active={PRESETS.find((p) => p.days === presetDays)!.key}
            onChange={(key) => setPresetDays(PRESETS.find((p) => p.key === key)!.days)}
          />
          <ThemeToggle />
        </div>
      </header>

      <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[220px_1fr] lg:items-start">
        <ReportSidebar active={section} onSelect={setSection} />
        <SectionPanel token={token} range={range} section={section} onSelect={setSection} />
      </div>

      {meta.data?.show_badge && (
        <div className="flex justify-center pt-2">
          <PoweredByBadge />
        </div>
      )}
    </div>
  );
}
