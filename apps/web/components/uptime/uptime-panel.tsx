"use client";

import { Activity, CheckCircle2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useSiteUptime } from "@/hooks/useSites";
import type { UptimeIncident, UptimeStatus } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

// Uptime status + recent incidents for one site (Phase 12). Green/red are the
// F0-reserved up/down semantic colors, so the badge maps cleanly onto them.

const CAUSE_LABEL: Record<string, string> = {
  timeout: "Timed out",
  connect: "Unreachable",
  dns: "DNS failure",
  http_5xx: "Server error (5xx)",
  blocked: "Not checkable",
};

function StatusBadge({ status }: { status: UptimeStatus["status"] }) {
  if (status === "up") {
    return (
      <Badge className="bg-success/10 text-success">
        <CheckCircle2 /> Up
      </Badge>
    );
  }
  if (status === "down") {
    return (
      <Badge variant="destructive">
        <XCircle /> Down
      </Badge>
    );
  }
  return (
    <Badge variant="secondary">
      <Activity /> Not checked yet
    </Badge>
  );
}

function IncidentRow({ incident }: { incident: UptimeIncident }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
      <span className="flex items-center gap-2">
        <span
          className={incident.ongoing ? "text-destructive" : "text-muted-foreground"}
          aria-hidden
        >
          ●
        </span>
        <span className="font-medium">{CAUSE_LABEL[incident.cause] ?? "Down"}</span>
      </span>
      <span className="text-muted-foreground">
        {formatDateTime(incident.started_at)}
        {incident.ongoing ? (
          <span className="ml-2 text-destructive">ongoing</span>
        ) : incident.resolved_at ? (
          <span className="ml-2">→ {formatDateTime(incident.resolved_at)}</span>
        ) : null}
      </span>
    </li>
  );
}

export function UptimePanel({ siteId }: { siteId: string }) {
  const { data, isLoading } = useSiteUptime(siteId);

  if (isLoading) return <Skeleton className="h-24 w-full rounded-lg" />;
  if (!data) return null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Uptime</h2>
          <StatusBadge status={data.status} />
        </div>
        {data.last_checked_at ? (
          <span className="text-xs text-muted-foreground">
            Last checked {formatDateTime(data.last_checked_at)}
          </span>
        ) : null}
      </div>

      {data.incidents.length > 0 ? (
        <ul className="divide-y divide-border">
          {data.incidents.map((incident, i) => (
            <IncidentRow key={`${incident.started_at}-${i}`} incident={incident} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          No downtime recorded. We&apos;ll email you if your site goes down.
        </p>
      )}
    </div>
  );
}
