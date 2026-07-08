"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiFetch,
  type EventsData,
  type Goal,
  type GoalConversion,
  type GoalInput,
  type StatsRange,
} from "@/lib/api";

// Custom events + conversion goals (Phase 15, premium). Reports are keyed by
// (siteId, range) like the stats hooks; goal CRUD invalidates the goals list.
// Every request is authed + ownership-scoped server-side, and a free account
// gets a 402 the report components surface as an upgrade prompt.

function eventsPath(siteId: string, range: StatsRange): string {
  const q = new URLSearchParams({ site_id: siteId, from: range.from, to: range.to });
  return `/events?${q.toString()}`;
}

export function useEvents(siteId: string | null, range: StatsRange) {
  return useQuery({
    queryKey: ["events", siteId, range.from, range.to],
    queryFn: () => apiFetch<EventsData>(eventsPath(siteId!, range)),
    enabled: !!siteId,
  });
}

export function useGoals(siteId: string | null) {
  return useQuery({
    queryKey: ["goals", siteId],
    queryFn: () => apiFetch<Goal[]>(`/goals?site_id=${encodeURIComponent(siteId!)}`),
    enabled: !!siteId,
  });
}

export function useGoalConversion(siteId: string | null, goalId: string, range: StatsRange) {
  return useQuery({
    queryKey: ["goal-conversion", siteId, goalId, range.from, range.to],
    queryFn: () => {
      const q = new URLSearchParams({ site_id: siteId!, from: range.from, to: range.to });
      return apiFetch<GoalConversion>(`/goals/${encodeURIComponent(goalId)}/conversions?${q}`);
    },
    enabled: !!siteId,
  });
}

export function useCreateGoal(siteId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: GoalInput) =>
      apiFetch<Goal>(`/goals?site_id=${encodeURIComponent(siteId!)}`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals", siteId] }),
  });
}

export function useDeleteGoal(siteId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (goalId: string) =>
      apiFetch<void>(`/goals/${encodeURIComponent(goalId)}?site_id=${encodeURIComponent(siteId!)}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals", siteId] }),
  });
}
