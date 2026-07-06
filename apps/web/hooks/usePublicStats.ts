"use client";

import { useQuery } from "@tanstack/react-query";

import {
  publicFetch,
  publicStatsPath,
  type Breakdown,
  type Overview,
  type Pages,
  type PublicSite,
  type Sources,
  type StatsRange,
  type Timeseries,
} from "@/lib/api";
import type { AudienceDimension, PageKind } from "@/hooks/useStats";

// Public (share-token) mirrors of the authed stats hooks. Same shapes, but keyed
// by token instead of site_id and fetched with no auth header (publicFetch).

export function usePublicMeta(token: string) {
  return useQuery({
    queryKey: ["public", "meta", token],
    queryFn: () => publicFetch<PublicSite>(`/public/${encodeURIComponent(token)}`),
  });
}

export function usePublicOverview(
  token: string,
  range: StatsRange,
  compare = true,
  opts: { refetchInterval?: number } = {},
) {
  return useQuery({
    queryKey: ["public", "overview", token, range.from, range.to, compare],
    queryFn: () =>
      publicFetch<Overview>(
        publicStatsPath(token, "overview", range, compare ? { compare: "previous" } : {}),
      ),
    refetchInterval: opts.refetchInterval,
  });
}

export function usePublicTimeseries(token: string, range: StatsRange) {
  return useQuery({
    queryKey: ["public", "timeseries", token, range.from, range.to],
    queryFn: () => publicFetch<Timeseries>(publicStatsPath(token, "timeseries", range)),
  });
}

export function usePublicSources(token: string, range: StatsRange) {
  return useQuery({
    queryKey: ["public", "sources", token, range.from, range.to],
    queryFn: () => publicFetch<Sources>(publicStatsPath(token, "sources", range)),
  });
}

export function usePublicAudience(token: string, range: StatsRange, dimension: AudienceDimension) {
  return useQuery({
    queryKey: ["public", "audience", token, range.from, range.to, dimension],
    queryFn: () => publicFetch<Breakdown>(publicStatsPath(token, "audience", range, { dimension })),
  });
}

export function usePublicPages(token: string, range: StatsRange, kind: PageKind) {
  return useQuery({
    queryKey: ["public", "pages", token, range.from, range.to, kind],
    queryFn: () => publicFetch<Pages>(publicStatsPath(token, "pages", range, { kind })),
  });
}
