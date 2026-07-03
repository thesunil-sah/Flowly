"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch, type Site } from "@/lib/api";

/** The authenticated account's sites (used to pick which live view to show). */
export function useSites() {
  return useQuery({
    queryKey: ["sites"],
    queryFn: () => apiFetch<Site[]>("/sites"),
  });
}
