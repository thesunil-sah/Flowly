"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type ShareLink, type Site, type SiteStatus, type UptimeStatus } from "@/lib/api";

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

/** A site's current uptime status + recent incidents (Phase 12). */
export function useSiteUptime(siteId: string | null) {
  return useQuery({
    queryKey: ["site-uptime", siteId],
    queryFn: () => apiFetch<UptimeStatus>(`/sites/${encodeURIComponent(siteId!)}/uptime`),
    enabled: !!siteId,
  });
}

function sharePath(siteId: string): string {
  return `/sites/${encodeURIComponent(siteId)}/share`;
}

/** The site's current public share link (url null when none is active). */
export function useShareLink(siteId: string | null) {
  return useQuery({
    queryKey: ["share-link", siteId],
    queryFn: () => apiFetch<ShareLink>(sharePath(siteId!)),
    enabled: !!siteId,
  });
}

/** Create (or rotate) the site's public share link. */
export function useCreateShare(siteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<ShareLink>(sharePath(siteId), { method: "POST" }),
    onSuccess: (data) => qc.setQueryData(["share-link", siteId], data),
  });
}

/** Revoke the site's public share link. */
export function useRevokeShare(siteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<ShareLink>(sharePath(siteId), { method: "DELETE" }),
    onSuccess: (data) => qc.setQueryData(["share-link", siteId], data),
  });
}
