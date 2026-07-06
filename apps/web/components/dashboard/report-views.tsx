"use client";

import Link from "next/link";
import { Languages, Lock, MapPin } from "lucide-react";
import { useState, type ReactNode } from "react";

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
import { useFilters } from "@/components/layout/filter-context";
import { useRange } from "@/components/layout/range-context";
import { SegmentedTabs } from "@/components/segmented-tabs";
import { TableSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ApiError } from "@/lib/api";
import {
  useAudience,
  useChannelReferrers,
  useChannels,
  usePages,
  useSources,
  type AudienceDimension,
  type DrilldownChannel,
  type PageKind,
} from "@/hooks/useStats";

// Authed report bodies (F4 + Phase 10): the same presentational reports kit the
// public share page uses, fed from the authed stats hooks. Each is one drill-down
// destination in the sidebar; the overview composition lives in `overview.tsx`.
// Every body reads the active filters so a click on one report re-slices them all.

const DRILLDOWN_LIMIT = 25;

const AUDIENCE_TITLES: Record<AudienceDimension, string> = {
  country: "Countries",
  device: "Devices",
  browser: "Browsers",
  os: "OS",
  screen: "Screen sizes",
  city: "Cities",
  language: "Languages",
};

const AUDIENCE_ICONS: Record<AudienceDimension, (label: string) => ReactNode> = {
  country: (label) => <CountryIcon code={label} />,
  device: (label) => <DeviceIcon label={label} />,
  browser: (label) => <BrowserIcon label={label} />,
  os: () => <OsIcon />,
  screen: () => <DeviceIcon label="desktop" />,
  city: () => <MapPin className="size-4 text-muted-foreground" />,
  language: () => <Languages className="size-4 text-muted-foreground" />,
};

// Dimensions that map to a filterable events column (screen/city/language are
// not in the server filter allowlist, so their rows aren't click-to-filter).
const FILTERABLE_DIMENSIONS = new Set<AudienceDimension>(["country", "device", "browser", "os"]);

function ErrorCard({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
      {children}
    </div>
  );
}

export function AudienceReport({ siteId, dimension }: { siteId: string; dimension: AudienceDimension }) {
  const { range } = useRange();
  const { filters, setFilter } = useFilters();
  const audience = useAudience(siteId, range, dimension, filters);

  // A 402 means this dimension (city) is paid-only and the account is on free —
  // show an upgrade prompt rather than a generic error (Phase 11 gate).
  if (audience.error instanceof ApiError && audience.error.status === 402) {
    return (
      <EmptyState
        icon={Lock}
        title={`${AUDIENCE_TITLES[dimension]} is a paid report`}
        description="Upgrade to a paid plan to see city-level breakdowns of your traffic."
        action={
          <Button asChild>
            <Link href="/billing">Upgrade</Link>
          </Button>
        }
      />
    );
  }
  if (audience.isError) return <ErrorCard>Couldn&apos;t load this report.</ErrorCard>;
  if (!audience.data) return <TableSkeleton rows={10} />;

  const onSelect = FILTERABLE_DIMENSIONS.has(dimension)
    ? (label: string) => label && setFilter(dimension, label)
    : undefined;

  return (
    <BreakdownCard
      title={AUDIENCE_TITLES[dimension]}
      rows={audience.data.rows}
      icon={AUDIENCE_ICONS[dimension]}
      labelFallback="Unknown"
      limit={DRILLDOWN_LIMIT}
      onSelect={onSelect}
    />
  );
}

export function PagesReport({ siteId, kind, title }: { siteId: string; kind: PageKind; title: string }) {
  const { range } = useRange();
  const { filters, setFilter } = useFilters();
  // Only "top" pages support the traffic/engagement toggle; entry/exit are
  // inherently traffic-ranked session views.
  const [sort, setSort] = useState<"traffic" | "engagement">("traffic");
  const effectiveSort = kind === "top" ? sort : "traffic";
  const pages = usePages(siteId, range, kind, filters, effectiveSort);

  return (
    <div className="flex flex-col gap-3">
      {kind === "top" && (
        <SegmentedTabs
          tabs={[
            { key: "traffic", label: "By traffic" },
            { key: "engagement", label: "By engagement" },
          ]}
          active={sort}
          onChange={(key) => setSort(key as "traffic" | "engagement")}
        />
      )}
      {pages.isError ? (
        <ErrorCard>Couldn&apos;t load this report.</ErrorCard>
      ) : !pages.data ? (
        <TableSkeleton rows={10} />
      ) : (
        <PagesCard
          title={title}
          rows={pages.data.rows}
          metric={pages.data.metric}
          limit={DRILLDOWN_LIMIT}
          engagement={effectiveSort === "engagement"}
          onSelect={(label) => label && setFilter("path", label)}
        />
      )}
    </div>
  );
}

export function ReferrersReport({ siteId }: { siteId: string }) {
  const { range } = useRange();
  const { filters, setFilter } = useFilters();
  const sources = useSources(siteId, range, filters);

  if (sources.isError) return <ErrorCard>Couldn&apos;t load this report.</ErrorCard>;
  if (!sources.data) return <TableSkeleton rows={10} />;

  return (
    <BreakdownCard
      title="Referrers"
      rows={sources.data.sources}
      icon={(label) => <SourceIcon label={label} />}
      labelFallback="direct"
      limit={DRILLDOWN_LIMIT}
      onSelect={(label) => label && setFilter("source", label)}
    />
  );
}

export function CampaignsReport({ siteId }: { siteId: string }) {
  const { range } = useRange();
  const { filters } = useFilters();
  const sources = useSources(siteId, range, filters);

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

const CHANNEL_TITLES: Record<DrilldownChannel, string> = {
  search: "Search engines",
  social: "Social networks",
  ai: "AI platforms",
};

export function ChannelsReport({ siteId }: { siteId: string }) {
  const { range } = useRange();
  const { filters } = useFilters();
  const channels = useChannels(siteId, range, filters);

  if (channels.isError) return <ErrorCard>Couldn&apos;t load this report.</ErrorCard>;
  if (!channels.data) return <TableSkeleton rows={5} />;

  // Reuse the breakdown card by mapping the channel label into the row `label`.
  const rows = channels.data.channels.map((c) => ({
    label: c.channel,
    pageviews: c.pageviews,
    visitors: c.visitors,
  }));
  return (
    <BreakdownCard
      title="Channels"
      rows={rows}
      icon={(label) => <SourceIcon label={label} />}
      labelFallback="direct"
      limit={DRILLDOWN_LIMIT}
    />
  );
}

export function ChannelReferrersReport({ siteId, channel }: { siteId: string; channel: DrilldownChannel }) {
  const { range } = useRange();
  const { filters } = useFilters();
  const referrers = useChannelReferrers(siteId, range, channel, filters);

  if (referrers.isError) return <ErrorCard>Couldn&apos;t load this report.</ErrorCard>;
  if (!referrers.data) return <TableSkeleton rows={10} />;
  if (referrers.data.rows.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
        No {CHANNEL_TITLES[channel].toLowerCase()} traffic in this range
      </div>
    );
  }

  return (
    <BreakdownCard
      title={CHANNEL_TITLES[channel]}
      rows={referrers.data.rows}
      icon={(label) => <SourceIcon label={label} />}
      labelFallback="(unknown)"
      limit={DRILLDOWN_LIMIT}
    />
  );
}
