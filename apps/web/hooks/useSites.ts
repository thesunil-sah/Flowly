"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type Site, type SiteStatus } from "@/lib/api";

/** The authenticated account's sites (used to pick which view to show). */
export function useSites() {
  return useQuery({
    queryKey: ["sites"],
    queryFn: () => apiFetch<Site[]>("/sites"),
  });
}

/** Add a site; on success refresh the sites list so pickers update. */
export function useCreateSite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { domain: string }) =>
      apiFetch<Site>("/sites", { method: "POST", body: JSON.stringify(v) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });
}

// Stop auto-polling this long after mounting even if still disconnected, so an
// abandoned install tab can't poll the API forever (a manual re-check remains).
const STATUS_POLL_TIMEOUT_MS = 3 * 60 * 1000;
const STATUS_POLL_INTERVAL_MS = 4000;

/**
 * Poll a site's install status, flipping waiting -> connected. Stops polling
 * once connected AND after a ~3-min cap; `refetch` drives the manual re-check.
 */
export function useSiteStatus(siteId: string | null, startedAt: number) {
  return useQuery({
    queryKey: ["site-status", siteId],
    queryFn: () => apiFetch<SiteStatus>(`/sites/${encodeURIComponent(siteId!)}/status`),
    enabled: !!siteId,
    refetchInterval: (query) => {
      if (query.state.data?.connected) return false; // done — stop polling
      if (Date.now() - startedAt > STATUS_POLL_TIMEOUT_MS) return false; // give up auto-poll
      return STATUS_POLL_INTERVAL_MS;
    },
  });
}
