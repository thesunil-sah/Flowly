// Shared display formatters (CLAUDE.md §4: every displayed number is
// rounded/formatted — never leak float artifacts).

const numberFmt = new Intl.NumberFormat();
const compactFmt = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatNumber(n: number): string {
  return numberFmt.format(Math.round(n));
}

/** Compact form for tight spots like chart axes: 12345 -> "12.3K". */
export function formatCompact(n: number): string {
  return compactFmt.format(Math.round(n));
}

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export function formatPercent(n: number): string {
  return `${Math.round(n * 10) / 10}%`;
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString();
}

/** Local date + time for incident timestamps (UTC stored, localized at display). */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
}
