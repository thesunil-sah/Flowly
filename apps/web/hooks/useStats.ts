"use client";

import { useQuery } from "@tanstack/react-query";

import {
  apiFetch,
  statsPath,
  type Breakdown,
  type Overview,
  type Pages,
  type Sources,
  type StatsRange,
  type Timeseries,
} from "@/lib/api";

// Every stats query is keyed by (endpoint, siteId, range, …variant) so changing
// the site or the date range refetches and caches independently. `enabled` gates
// on a chosen site so hooks are safe to call before one is selected.

export function useOverview(siteId: string | null, range: StatsRange, compare = true) {
  return useQuery({
    queryKey: ["stats", "overview", siteId, range.from, range.to, compare],
    queryFn: () =>
      apiFetch<Overview>(
        statsPath("overview", siteId!, range, compare ? { compare: "previous" } : {}),
      ),
    enabled: !!siteId,
  });
}

export function useTimeseries(siteId: string | null, range: StatsRange) {
  return useQuery({
    queryKey: ["stats", "timeseries", siteId, range.from, range.to],
    queryFn: () => apiFetch<Timeseries>(statsPath("timeseries", siteId!, range)),
    enabled: !!siteId,
  });
}

export function useSources(siteId: string | null, range: StatsRange) {
  return useQuery({
    queryKey: ["stats", "sources", siteId, range.from, range.to],
    queryFn: () => apiFetch<Sources>(statsPath("sources", siteId!, range)),
    enabled: !!siteId,
  });
}

export type AudienceDimension = "country" | "device" | "browser" | "os";

export function useAudience(siteId: string | null, range: StatsRange, dimension: AudienceDimension) {
  return useQuery({
    queryKey: ["stats", "audience", siteId, range.from, range.to, dimension],
    queryFn: () => apiFetch<Breakdown>(statsPath("audience", siteId!, range, { dimension })),
    enabled: !!siteId,
  });
}

export type PageKind = "top" | "entry" | "exit";

export function usePages(siteId: string | null, range: StatsRange, kind: PageKind) {
  return useQuery({
    queryKey: ["stats", "pages", siteId, range.from, range.to, kind],
    queryFn: () => apiFetch<Pages>(statsPath("pages", siteId!, range, { kind })),
    enabled: !!siteId,
  });
}
