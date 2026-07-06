"use client";

import Link from "next/link";
import { Radio } from "lucide-react";

import { useActiveSite } from "@/components/layout/site-context";
import { CurrentPages, LiveCounter, LiveFeed } from "@/components/live";
import { PageSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useLiveTraffic } from "@/hooks/useLiveTraffic";

// Keyed by siteId so switching sites remounts the hook with fresh state.
function LiveView({ siteId }: { siteId: string }) {
  const { count, feed, currentPages, connected } = useLiveTraffic(siteId);
  return (
    <>
      <LiveCounter count={count} connected={connected} />
      <div className="grid gap-4 sm:grid-cols-2">
        <LiveFeed feed={feed} />
        <CurrentPages pages={currentPages} />
      </div>
    </>
  );
}

export default function LivePage() {
  const { activeSiteId, sites, isLoading } = useActiveSite();

  if (isLoading) {
    return <PageSkeleton />;
  }

  if (sites.length === 0 || !activeSiteId) {
    return (
      <EmptyState
        icon={Radio}
        title="No sites yet"
        description="Add a site and install the snippet to start seeing live visitors."
        action={
          <Button asChild>
            <Link href="/sites">Add a site</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <h1 className="text-2xl font-semibold">Live traffic</h1>
      <LiveView key={activeSiteId} siteId={activeSiteId} />
    </div>
  );
}
