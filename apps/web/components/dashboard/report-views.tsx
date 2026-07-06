"use client";

import type { ReactNode } from "react";

import { BreakdownCard } from "@/components/reports/breakdown-card";
import { PagesCard } from "@/components/reports/pages-card";
import {
  BrowserIcon,
  CountryIcon,
  DeviceIcon,
  OsIcon,
  SourceIcon,
} from "@/components/reports/row-icon";
import { UtmCard } from "@/components/reports/utm-card";
import { useRange } from "@/components/layout/range-context";
import { TableSkeleton } from "@/components/skeletons";
import { useAudience, usePages, useSources, type AudienceDimension, type PageKind } from "@/hooks/useStats";

// Authed report bodies (F4): the same presentational reports kit the public
// share page uses, fed from the authed stats hooks. Each is one drill-down
// destination in the sidebar; the overview composition lives in `overview.tsx`.

const DRILLDOWN_LIMIT = 25;

const AUDIENCE_TITLES: Record<AudienceDimension, string> = {
  country: "Countries",
  device: "Devices",
  browser: "Browsers",
  os: "OS",
};

const AUDIENCE_ICONS: Record<AudienceDimension, (label: string) => ReactNode> = {
  country: (label) => <CountryIcon code={label} />,
  device: (label) => <DeviceIcon label={label} />,
  browser: (label) => <BrowserIcon label={label} />,
  os: () => <OsIcon />,
};

function ErrorCard({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
      {children}
    </div>
  );
}

export function AudienceReport({ siteId, dimension }: { siteId: string; dimension: AudienceDimension }) {
  const { range } = useRange();
  const audience = useAudience(siteId, range, dimension);

  if (audience.isError) return <ErrorCard>Couldn&apos;t load this report.</ErrorCard>;
  if (!audience.data) return <TableSkeleton rows={10} />;

  return (
    <BreakdownCard
      title={AUDIENCE_TITLES[dimension]}
      rows={audience.data.rows}
      icon={AUDIENCE_ICONS[dimension]}
      labelFallback="Unknown"
      limit={DRILLDOWN_LIMIT}
    />
  );
}

export function PagesReport({ siteId, kind, title }: { siteId: string; kind: PageKind; title: string }) {
  const { range } = useRange();
  const pages = usePages(siteId, range, kind);

  if (pages.isError) return <ErrorCard>Couldn&apos;t load this report.</ErrorCard>;
  if (!pages.data) return <TableSkeleton rows={10} />;

  return <PagesCard title={title} rows={pages.data.rows} metric={pages.data.metric} limit={DRILLDOWN_LIMIT} />;
}

export function ReferrersReport({ siteId }: { siteId: string }) {
  const { range } = useRange();
  const sources = useSources(siteId, range);

  if (sources.isError) return <ErrorCard>Couldn&apos;t load this report.</ErrorCard>;
  if (!sources.data) return <TableSkeleton rows={10} />;

  return (
    <BreakdownCard
      title="Referrers"
      rows={sources.data.sources}
      icon={(label) => <SourceIcon label={label} />}
      labelFallback="direct"
      limit={DRILLDOWN_LIMIT}
    />
  );
}

export function CampaignsReport({ siteId }: { siteId: string }) {
  const { range } = useRange();
  const sources = useSources(siteId, range);

  if (sources.isError) return <ErrorCard>Couldn&apos;t load this report.</ErrorCard>;
  if (!sources.data) return <TableSkeleton rows={8} />;
  if (sources.data.utm.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
        No UTM campaign traffic in this range
      </div>
    );
  }
  return <UtmCard rows={sources.data.utm} />;
}
