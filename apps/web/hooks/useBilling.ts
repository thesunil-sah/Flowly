"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import {
  apiFetch,
  type BillingInterval,
  type BillingTier,
  type CheckoutResponse,
  type PortalResponse,
  type UsageSummary,
} from "@/lib/api";

/** Current-month usage vs the account's effective plan quota. */
export function useUsage() {
  return useQuery({
    queryKey: ["billing", "usage"],
    queryFn: () => apiFetch<UsageSummary>("/billing/usage"),
  });
}

/** Start Checkout for a tier + interval, then redirect the browser to Stripe. */
export function useCheckout() {
  return useMutation({
    mutationFn: (v: { tier: BillingTier; interval: BillingInterval }) =>
      apiFetch<CheckoutResponse>("/billing/checkout", {
        method: "POST",
        body: JSON.stringify(v),
      }),
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
