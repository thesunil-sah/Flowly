"use client";

import { LiveDot } from "@/components/reports/live-dot";
import { CountryIcon } from "@/components/reports/row-icon";
import type { CountryCount, FeedRow, PageCount } from "@/hooks/useLiveTraffic";
import { formatTime } from "@/lib/format";

export function LiveCounter({ count, connected }: { count: number; connected: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-card">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {connected ? (
          <LiveDot />
        ) : (
          <span className="inline-block h-2 w-2 rounded-full bg-muted-foreground/40" aria-hidden />
        )}
        {connected ? "Live" : "Connecting…"}
      </div>
      <div className="mt-2 text-5xl font-semibold tabular-nums">{count}</div>
      <div className="text-sm text-muted-foreground">visitors online now</div>
    </div>
  );
}

export function LiveFeed({ feed }: { feed: FeedRow[] }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-card">
      <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Live feed</h2>
      {feed.length === 0 ? (
        <p className="text-sm text-muted-foreground">Waiting for live events…</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {feed.map((e) => (
            <li
              key={e.key}
              className="flex justify-between gap-3 duration-300 animate-in fade-in slide-in-from-top-2 motion-reduce:animate-none"
            >
              <span className="truncate font-mono">{e.path}</span>
              <span className="shrink-0 text-muted-foreground">
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
    <div className="rounded-lg border border-border bg-card p-4 shadow-card">
      <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Current pages</h2>
      {pages.length === 0 ? (
        <p className="text-sm text-muted-foreground">Waiting for live events…</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {pages.map((p) => (
            <li key={p.path} className="flex justify-between gap-3">
              <span className="truncate font-mono">{p.path}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">{p.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Live visitors by country (Phase 11) — a light country-level presence panel fed
// from the same live stream (a full geographic choropleth would need a bundled
// world-map asset; deferred). Each row shows the emoji flag + live count, with an
// indigo share bar like the historical breakdown cards.
export function LiveCountries({ countries }: { countries: CountryCount[] }) {
  const max = Math.max(1, ...countries.map((c) => c.count));
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-card">
      <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Live by country</h2>
      {countries.length === 0 ? (
        <p className="text-sm text-muted-foreground">Waiting for live events…</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {countries.map((c) => (
            <li
              key={c.country}
              className="relative flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm"
            >
              <span
                className="absolute inset-y-0 left-0 rounded-md bg-primary/10"
                style={{ width: `${Math.round((c.count / max) * 100)}%` }}
                aria-hidden
              />
              <span className="relative flex min-w-0 flex-1 items-center gap-2.5">
                <CountryIcon code={c.country} />
                <span className="truncate">{c.country}</span>
              </span>
              <span className="relative shrink-0 tabular-nums text-muted-foreground">{c.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
