"use client";

import Link from "next/link";
import { LayoutGrid } from "lucide-react";
import type { ReactNode } from "react";

import { useActiveSite } from "@/components/layout/site-context";
import { useRange } from "@/components/layout/range-context";
import { SegmentedTabs } from "@/components/segmented-tabs";
import { PageSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { RANGE_PRESETS } from "@/lib/range";

// Shared chrome for every authed report page (F4): the active-site + range
// gating, the title row, and the dashboard-wide date-range tabs. Report bodies
// receive the resolved (non-null) siteId via a render prop and read the range
// themselves through `useRange()`.

export function RangeTabs() {
  const { presetKey, setPresetDays } = useRange();
  return (
    <SegmentedTabs
      tabs={RANGE_PRESETS.map((p) => ({ key: p.key, label: p.label }))}
      active={presetKey}
      onChange={(key) => setPresetDays(RANGE_PRESETS.find((p) => p.key === key)!.days)}
    />
  );
}

export function ReportShell({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: (siteId: string) => ReactNode;
  children: (siteId: string) => ReactNode;
}) {
  const { activeSiteId, sites, isLoading } = useActiveSite();

  if (isLoading) {
    return <PageSkeleton />;
  }

  if (sites.length === 0 || !activeSiteId) {
    return (
      <EmptyState
        icon={LayoutGrid}
        title="No sites yet"
        description="Add a site and install the snippet to start seeing your traffic."
        action={
          <Button asChild>
            <Link href="/sites">Add a site</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{title}</h1>
          {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
        </div>
        <div className="flex items-center gap-2">
          <RangeTabs />
          {actions?.(activeSiteId)}
        </div>
      </div>
      {/* Remount the body per site so any per-site local state resets cleanly. */}
      <div key={activeSiteId}>{children(activeSiteId)}</div>
    </div>
  );
}
