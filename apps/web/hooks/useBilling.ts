"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import {
  apiFetch,
  type CheckoutResponse,
  type PortalResponse,
  type UsageSummary,
} from "@/lib/api";

/** Current-month usage vs the free monthly allotment (Phase 14 metered). */
export function useUsage() {
  return useQuery({
    queryKey: ["billing", "usage"],
    queryFn: () => apiFetch<UsageSummary>("/billing/usage"),
  });
}

/** Start Checkout for the single metered plan, then redirect the browser to Stripe. */
export function useCheckout() {
  return useMutation({
    mutationFn: () => apiFetch<CheckoutResponse>("/billing/checkout", { method: "POST" }),
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });
}

/** Open the Stripe Customer Portal (manage / cancel), redirecting the browser. */
export function usePortal() {
  return useMutation({
    mutationFn: () => apiFetch<PortalResponse>("/billing/portal", { method: "POST" }),
    onSuccess: (data) => {
      window.location.href = data.url;
    },
  });
}
