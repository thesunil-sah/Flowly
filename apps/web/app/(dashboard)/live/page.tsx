"use client";

import { useState } from "react";

import { CurrentPages, LiveCounter, LiveFeed } from "@/components/live";
import { useLiveTraffic } from "@/hooks/useLiveTraffic";
import { useSites } from "@/hooks/useSites";

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
  const { data: sites, isLoading } = useSites();
  const [selected, setSelected] = useState<string | null>(null);

  if (isLoading) {
    return <main className="flex flex-1 items-center justify-center p-6">Loading…</main>;
  }

  if (!sites || sites.length === 0) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-2 p-6">
        <h1 className="text-2xl font-semibold">Live traffic</h1>
        <p className="text-gray-600">No sites yet. Add one to start seeing live visitors.</p>
      </main>
    );
  }

  // Derive the active site (default to the first) instead of syncing via effect.
  const activeSiteId = selected ?? sites[0].site_id;

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Live traffic</h1>
        {sites.length > 1 && (
          <select
            value={activeSiteId}
            onChange={(e) => setSelected(e.target.value)}
            className="rounded border border-gray-300 px-3 py-2"
          >
            {sites.map((s) => (
              <option key={s.id} value={s.site_id}>
                {s.domain}
              </option>
            ))}
          </select>
        )}
      </div>

      <LiveView key={activeSiteId} siteId={activeSiteId} />
    </main>
  );
}
