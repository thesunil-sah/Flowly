"use client";

import { RefreshCw, Search } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { useRange } from "@/components/layout/range-context";
import { TableSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  useConnectGsc,
  useDisconnectGsc,
  useGscConnection,
  useGscReport,
  useSyncGsc,
} from "@/hooks/useSearchConsole";
import type { GscConnection, GscReport, SearchRow } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";

// The label column header per report (opportunities are keyword rows too).
const LABEL_HEADER: Record<GscReport, string> = {
  keywords: "Keyword",
  pages: "Page",
  opportunities: "Keyword",
};

// Surfaces the ?gsc=connected|error message the OAuth callback redirects with.
function useConnectToast() {
  const params = useSearchParams();
  const shown = useRef(false);
  useEffect(() => {
    if (shown.current) return;
    const status = params.get("gsc");
    if (status === "connected") {
      toast.success("Search Console connected");
      shown.current = true;
    } else if (status === "error") {
      toast.error(params.get("message") ?? "Couldn't connect Search Console");
      shown.current = true;
    }
  }, [params]);
}

function ConnectCard({ siteId }: { siteId: string }) {
  const params = useSearchParams();
  const connect = useConnectGsc(siteId);
  const errored = params.get("gsc") === "error";
  return (
    <EmptyState
      icon={Search}
      title="Connect Google Search Console"
      description={
        errored
          ? (params.get("message") ?? "Couldn't connect. Make sure the site is verified in Search Console.")
          : "Search engines strip keywords from referrers, so this data comes straight from your own Search Console — the queries you rank for, your average position, and pages that perform in Google."
      }
      action={
        <Button onClick={() => connect.mutate()} disabled={connect.isPending}>
          {connect.isPending ? "Redirecting…" : "Connect Search Console"}
        </Button>
      }
    />
  );
}

function formatCtr(ctr: number): string {
  return `${(ctr * 100).toFixed(1)}%`;
}

function ReportTable({ rows, header }: { rows: SearchRow[]; header: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-card">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-4 py-3 font-medium">{header}</th>
            <th className="px-4 py-3 text-right font-medium">Clicks</th>
            <th className="px-4 py-3 text-right font-medium">Impressions</th>
            <th className="px-4 py-3 text-right font-medium">CTR</th>
            <th className="px-4 py-3 text-right font-medium">Position</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.label}-${i}`} className="border-b border-border/60 last:border-0">
              <td className="max-w-xs truncate px-4 py-2.5 font-medium" title={r.label}>
                {r.label || "—"}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatNumber(r.clicks)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">
                {formatNumber(r.impressions)}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums">{formatCtr(r.ctr)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums">{r.position.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReportBody({
  siteId,
  report,
  connection,
}: {
  siteId: string;
  report: GscReport;
  connection: GscConnection;
}) {
  const { range } = useRange();
  const query = useGscReport(siteId, report, range, true);
  const sync = useSyncGsc(siteId);
  const disconnect = useDisconnectGsc(siteId);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="truncate">
          {connection.property_url}
          {connection.last_synced_at
            ? ` · synced ${formatDateTime(connection.last_synced_at)}`
            : " · not synced yet"}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="xs"
            onClick={() => sync.mutate(undefined, { onSuccess: () => toast.success("Synced") })}
            disabled={sync.isPending}
          >
            <RefreshCw className={sync.isPending ? "animate-spin" : ""} />
            {sync.isPending ? "Syncing…" : "Sync now"}
          </Button>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => disconnect.mutate()}
            disabled={disconnect.isPending}
          >
            Disconnect
          </Button>
        </div>
      </div>

      {query.isError ? (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          Couldn&apos;t load this report.
        </div>
      ) : !query.data ? (
        <TableSkeleton rows={10} />
      ) : query.data.rows.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No search data yet"
          description="Search Console data lags a couple of days. Try “Sync now”, or widen the date range."
        />
      ) : (
        <ReportTable rows={query.data.rows} header={LABEL_HEADER[report]} />
      )}
    </div>
  );
}

export function SearchReport({ siteId, report }: { siteId: string; report: GscReport }) {
  useConnectToast();
  const conn = useGscConnection(siteId);

  if (conn.isLoading) return <TableSkeleton rows={8} />;
  if (!conn.data?.connected) return <ConnectCard siteId={siteId} />;
  return <ReportBody siteId={siteId} report={report} connection={conn.data} />;
}
