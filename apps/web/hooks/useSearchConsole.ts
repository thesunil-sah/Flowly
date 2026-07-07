"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiFetch,
  gscPath,
  type GscAuthorize,
  type GscConnection,
  type GscSync,
  type SearchReportData,
  type StatsRange,
} from "@/lib/api";

// Search Console data hooks (Phase 13). The connection query gates the reports:
// a report is only fetched once a site is connected. Connect kicks the browser
// to Google's consent screen; the callback redirects back to /search-console.

function base(siteId: string): string {
  return `/searchconsole/${encodeURIComponent(siteId)}`;
}

/** Whether this site is linked to a GSC property (and when it last synced). */
export function useGscConnection(siteId: string | null) {
  return useQuery({
    queryKey: ["gsc", "connection", siteId],
    queryFn: () => apiFetch<GscConnection>(`${base(siteId!)}/connection`),
    enabled: !!siteId,
  });
}

/** Start the connect flow: navigate the browser to Google's consent screen. */
export function useConnectGsc(siteId: string) {
  return useMutation({
    mutationFn: () => apiFetch<GscAuthorize>(`${base(siteId)}/connect`, { method: "POST" }),
    onSuccess: (data) => {
      window.location.href = data.authorize_url;
    },
  });
}

/** Pull the latest Search Analytics now (also runs daily via the worker). */
export function useSyncGsc(siteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<GscSync>(`${base(siteId)}/sync`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["gsc"] }),
  });
}

/** Disconnect: removes the link + its synced metrics. */
export function useDisconnectGsc(siteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<GscConnection>(`${base(siteId)}/connection`, { method: "DELETE" }),
    onSuccess: (data) => {
      qc.setQueryData(["gsc", "connection", siteId], data);
      qc.invalidateQueries({ queryKey: ["gsc"] });
    },
  });
}

/** One SEO report (keywords / pages / opportunities), date-ranged. */
export function useGscReport(
  siteId: string | null,
  report: string,
  range: StatsRange,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["gsc", report, siteId, range.from, range.to],
    queryFn: () => apiFetch<SearchReportData>(gscPath(report, siteId!, range, { limit: "25" })),
    enabled: !!siteId && enabled,
  });
}
