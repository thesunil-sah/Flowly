"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  BreakdownRow,
  MetricDelta,
  Overview,
  PageRow,
  Timeseries,
  UtmRow,
} from "@/lib/api";

// --- Formatting (never leak float artifacts; CLAUDE.md §4) -----------------
const numberFmt = new Intl.NumberFormat();

function formatNumber(n: number): string {
  return numberFmt.format(Math.round(n));
}

function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

function formatPercent(n: number): string {
  return `${Math.round(n * 10) / 10}%`;
}

// --- Metric cards ----------------------------------------------------------
function DeltaBadge({ delta, invert }: { delta: MetricDelta; invert?: boolean }) {
  if (delta.change_pct === null) return null;
  const up = delta.change_pct > 0;
  // For most metrics up is good; for bounce rate lower is better, so invert.
  const good = invert ? !up : up;
  const flat = delta.change_pct === 0;
  const color = flat ? "text-gray-400" : good ? "text-green-600" : "text-red-600";
  const arrow = flat ? "" : up ? "▲" : "▼";
  return (
    <span className={`text-xs ${color}`}>
      {arrow} {Math.abs(delta.change_pct)}%
    </span>
  );
}

function MetricCard({
  label,
  value,
  delta,
  invert,
}: {
  label: string;
  value: string;
  delta: MetricDelta;
  invert?: boolean;
}) {
  return (
    <div className="rounded border border-gray-300 p-4">
      <div className="text-sm text-gray-600">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums">{value}</span>
        <DeltaBadge delta={delta} invert={invert} />
      </div>
    </div>
  );
}

export function MetricCards({ data }: { data: Overview }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <MetricCard label="Visitors" value={formatNumber(data.visitors.value)} delta={data.visitors} />
      <MetricCard
        label="Pageviews"
        value={formatNumber(data.pageviews.value)}
        delta={data.pageviews}
      />
      <MetricCard label="Sessions" value={formatNumber(data.sessions.value)} delta={data.sessions} />
      <MetricCard
        label="Bounce rate"
        value={formatPercent(data.bounce_rate.value)}
        delta={data.bounce_rate}
        invert
      />
      <MetricCard
        label="Avg. duration"
        value={formatDuration(data.avg_duration.value)}
        delta={data.avg_duration}
      />
    </div>
  );
}

// --- Time-series chart -----------------------------------------------------
export function TrafficChart({ data }: { data: Timeseries }) {
  const isHour = data.interval === "hour";
  const tick = (iso: string) => {
    const d = new Date(iso);
    return isHour
      ? d.toLocaleTimeString([], { hour: "2-digit" })
      : d.toLocaleDateString([], { month: "short", day: "numeric" });
  };
  const points = data.points.map((p) => ({ ...p, label: tick(p.bucket) }));

  return (
    <div className="rounded border border-gray-300 p-4">
      <h2 className="mb-3 text-sm font-semibold text-gray-600">Traffic over time</h2>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={points} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} minTickGap={24} />
          <YAxis tick={{ fontSize: 12 }} allowDecimals={false} width={40} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="visitors"
            stroke="#000"
            strokeWidth={2}
            dot={false}
            name="Visitors"
          />
          <Line
            type="monotone"
            dataKey="pageviews"
            stroke="#9ca3af"
            strokeWidth={2}
            dot={false}
            name="Pageviews"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// --- Tables ----------------------------------------------------------------
function EmptyRow({ span }: { span: number }) {
  return (
    <tr>
      <td colSpan={span} className="py-3 text-center text-sm text-gray-400">
        No data in this range
      </td>
    </tr>
  );
}

export function BreakdownTable({
  title,
  rows,
  labelFallback = "(none)",
}: {
  title: string;
  rows: BreakdownRow[];
  labelFallback?: string;
}) {
  return (
    <div className="rounded border border-gray-300 p-4">
      <h2 className="mb-2 text-sm font-semibold text-gray-600">{title}</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-400">
            <th className="font-normal">Source</th>
            <th className="w-20 text-right font-normal">Visitors</th>
            <th className="w-24 text-right font-normal">Pageviews</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <EmptyRow span={3} />
          ) : (
            rows.map((r) => (
              <tr key={r.label} className="border-t border-gray-100">
                <td className="truncate py-1">{r.label || labelFallback}</td>
                <td className="py-1 text-right tabular-nums">{formatNumber(r.visitors)}</td>
                <td className="py-1 text-right tabular-nums text-gray-500">
                  {formatNumber(r.pageviews)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function PagesTable({
  rows,
  metric,
  labelFallback = "(none)",
}: {
  rows: PageRow[];
  metric: string;
  labelFallback?: string;
}) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-gray-400">
          <th className="font-normal">Path</th>
          <th className="w-20 text-right font-normal capitalize">{metric}</th>
          <th className="w-20 text-right font-normal">Visitors</th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <EmptyRow span={3} />
        ) : (
          rows.map((r) => (
            <tr key={r.label} className="border-t border-gray-100">
              <td className="truncate py-1 font-mono">{r.label || labelFallback}</td>
              <td className="py-1 text-right tabular-nums">{formatNumber(r.count)}</td>
              <td className="py-1 text-right tabular-nums text-gray-500">
                {formatNumber(r.visitors)}
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}

export function UtmTable({ rows }: { rows: UtmRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="rounded border border-gray-300 p-4">
      <h2 className="mb-2 text-sm font-semibold text-gray-600">UTM campaigns</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-gray-400">
            <th className="font-normal">Source</th>
            <th className="font-normal">Medium</th>
            <th className="font-normal">Campaign</th>
            <th className="w-20 text-right font-normal">Visitors</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-gray-100">
              <td className="truncate py-1">{r.utm_source}</td>
              <td className="truncate py-1 text-gray-500">{r.utm_medium || "—"}</td>
              <td className="truncate py-1 text-gray-500">{r.utm_campaign || "—"}</td>
              <td className="py-1 text-right tabular-nums">{formatNumber(r.visitors)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
