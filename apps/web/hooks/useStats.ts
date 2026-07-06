"use client";

import { useQuery } from "@tanstack/react-query";

import {
  apiFetch,
  statsPath,
  type Breakdown,
  type Channels,
  type Heatmap,
  type Overview,
  type Pages,
  type Sources,
  type StatsFilters,
  type StatsRange,
  type Timeseries,
} from "@/lib/api";

// Every stats query is keyed by (endpoint, siteId, range, filters, …variant) so
// changing the site, the date range, or an active filter refetches and caches
// independently. `enabled` gates on a chosen site so hooks are safe to call
// before one is selected. Filters (Phase 10) are threaded verbatim as query
// params and folded into the key via a stable serialization.

function filterKey(filters: StatsFilters): string {
  // Sorted so key order can't churn the cache for the same set of filters.
  return Object.keys(filters)
    .sort()
    .map((k) => `${k}=${filters[k]}`)
    .join("&");
}

export function useOverview(
  siteId: string | null,
  range: StatsRange,
  filters: StatsFilters = {},
  compare = true,
) {
  return useQuery({
    queryKey: ["stats", "overview", siteId, range.from, range.to, filterKey(filters), compare],
    queryFn: () =>
      apiFetch<Overview>(
        statsPath("overview", siteId!, range, { ...filters, ...(compare ? { compare: "previous" } : {}) }),
      ),
    enabled: !!siteId,
  });
}

export function useTimeseries(siteId: string | null, range: StatsRange, filters: StatsFilters = {}) {
  return useQuery({
    queryKey: ["stats", "timeseries", siteId, range.from, range.to, filterKey(filters)],
    queryFn: () => apiFetch<Timeseries>(statsPath("timeseries", siteId!, range, filters)),
    enabled: !!siteId,
  });
}

export function useSources(siteId: string | null, range: StatsRange, filters: StatsFilters = {}) {
  return useQuery({
    queryKey: ["stats", "sources", siteId, range.from, range.to, filterKey(filters)],
    queryFn: () => apiFetch<Sources>(statsPath("sources", siteId!, range, filters)),
    enabled: !!siteId,
  });
}

export type AudienceDimension =
  | "country"
  | "device"
  | "browser"
  | "os"
  | "screen"
  | "city"
  | "language";

export function useAudience(
  siteId: string | null,
  range: StatsRange,
  dimension: AudienceDimension,
  filters: StatsFilters = {},
) {
  return useQuery({
    queryKey: ["stats", "audience", siteId, range.from, range.to, dimension, filterKey(filters)],
    queryFn: () =>
      apiFetch<Breakdown>(statsPath("audience", siteId!, range, { ...filters, dimension })),
    enabled: !!siteId,
  });
}

export type PageKind = "top" | "entry" | "exit";
export type PageSort = "traffic" | "engagement";

export function usePages(
  siteId: string | null,
  range: StatsRange,
  kind: PageKind,
  filters: StatsFilters = {},
  sort: PageSort = "traffic",
) {
  return useQuery({
    queryKey: ["stats", "pages", siteId, range.from, range.to, kind, sort, filterKey(filters)],
    queryFn: () => apiFetch<Pages>(statsPath("pages", siteId!, range, { ...filters, kind, sort })),
    enabled: !!siteId,
  });
}

export function useChannels(siteId: string | null, range: StatsRange, filters: StatsFilters = {}) {
  return useQuery({
    queryKey: ["stats", "channels", siteId, range.from, range.to, filterKey(filters)],
    queryFn: () => apiFetch<Channels>(statsPath("channels", siteId!, range, filters)),
    enabled: !!siteId,
  });
}

export type DrilldownChannel = "search" | "social" | "ai";

export function useChannelReferrers(
  siteId: string | null,
  range: StatsRange,
  channel: DrilldownChannel,
  filters: StatsFilters = {},
) {
  return useQuery({
    queryKey: ["stats", "channel-referrers", siteId, range.from, range.to, channel, filterKey(filters)],
    queryFn: () => apiFetch<Breakdown>(statsPath(`channels/${channel}`, siteId!, range, filters)),
    enabled: !!siteId,
  });
}

export function useHeatmap(siteId: string | null, range: StatsRange, filters: StatsFilters = {}) {
  // Bucket in the viewer's own timezone (§4 display-time localization).
  const tz = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";
  return useQuery({
    queryKey: ["stats", "heatmap", siteId, range.from, range.to, tz, filterKey(filters)],
    queryFn: () => apiFetch<Heatmap>(statsPath("heatmap", siteId!, range, { ...filters, tz })),
    enabled: !!siteId,
  });
}
