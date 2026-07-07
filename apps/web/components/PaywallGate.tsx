"use client";

import { PaywallModal } from "@/components/PaywallModal";
import { useUsage } from "@/hooks/useBilling";

// Dashboard-wide hard paywall (Phase 14): when a free account passes the free
// monthly-view limit, usage_summary reports status "locked" and this mounts a
// NON-dismissible upgrade modal over the whole dashboard. The server also 402s
// stats/live, so the gate isn't UI-only. Ingestion keeps running regardless —
// the wall is on the dashboard, never the pipeline (§9).
export function PaywallGate() {
  const { data } = useUsage();
  const locked = data?.status === "locked";
  if (!locked) return null;
  return <PaywallModal open onOpenChange={() => {}} dismissible={false} />;
}
