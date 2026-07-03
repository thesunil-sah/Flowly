"use client";

import type { FeedRow, PageCount } from "@/hooks/useLiveTraffic";

function formatTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString();
}

export function LiveCounter({ count, connected }: { count: number; connected: boolean }) {
  return (
    <div className="rounded border border-gray-300 p-6">
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <span
          className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-gray-300"}`}
          aria-hidden
        />
        {connected ? "Live" : "Connecting…"}
      </div>
      <div className="mt-2 text-5xl font-semibold tabular-nums">{count}</div>
      <div className="text-sm text-gray-600">visitors online now</div>
    </div>
  );
}

export function LiveFeed({ feed }: { feed: FeedRow[] }) {
  return (
    <div className="rounded border border-gray-300 p-4">
      <h2 className="mb-2 text-sm font-semibold text-gray-600">Live feed</h2>
      {feed.length === 0 ? (
        <p className="text-sm text-gray-400">Waiting for live events…</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {feed.map((e) => (
            <li key={e.key} className="flex justify-between gap-3">
              <span className="truncate font-mono">{e.path}</span>
              <span className="shrink-0 text-gray-500">
                {[e.country, e.device, e.browser, e.source].filter(Boolean).join(" · ")}
                {" · "}
                {formatTime(e.ts)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function CurrentPages({ pages }: { pages: PageCount[] }) {
  return (
    <div className="rounded border border-gray-300 p-4">
      <h2 className="mb-2 text-sm font-semibold text-gray-600">Current pages</h2>
      {pages.length === 0 ? (
        <p className="text-sm text-gray-400">Waiting for live events…</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {pages.map((p) => (
            <li key={p.path} className="flex justify-between gap-3">
              <span className="truncate font-mono">{p.path}</span>
              <span className="shrink-0 tabular-nums text-gray-500">{p.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
