// Typed fetch wrapper for the Flowly API. Attaches the Bearer access token,
// and on a 401 tries a single /auth/refresh then retries the request. No
// component calls fetch directly (CLAUDE.md §4).

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "@/lib/auth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type OAuthProvider = "google" | "github";

/** Full-page navigation target that begins the provider's OAuth flow. */
export function oauthStartUrl(provider: OAuthProvider): string {
  return `${BASE}/auth/oauth/${provider}/start`;
}

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type Account = {
  id: string;
  username: string;
  email: string;
  plan: string;
  status: string;
  email_verified_at: string | null;
  trial_ends_at: string | null;
  email_opt_out: boolean;
  // Derived server-side: false for OAuth-only accounts (no password to change).
  has_password: boolean;
};

/** A linked social login shown in settings (Phase F3). */
export type Identity = {
  id: string;
  provider: string;
  created_at: string;
};

export type MessageResponse = {
  status: string;
  dev_code: string | null;
};

export type Site = {
  id: string;
  site_id: string;
  domain: string;
  snippet: string; // ready-to-paste install tag, built server-side
};

export type SiteStatus = { connected: boolean };

// --- Uptime monitoring (Phase 12) ------------------------------------------
export type UptimeIncident = {
  started_at: string;
  resolved_at: string | null; // null while ongoing
  cause: string; // timeout | connect | dns | http_5xx | blocked
  ongoing: boolean;
};

export type UptimeStatus = {
  status: "up" | "down" | "unknown";
  last_checked_at: string | null;
  last_status_code: number | null;
  incidents: UptimeIncident[];
};

// --- Search Console (Phase 13) ---------------------------------------------
export type GscReport = "keywords" | "pages" | "opportunities";
export type GscConnection = {
  connected: boolean;
  property_url: string | null; // the linked GSC siteUrl; never the refresh token
  last_synced_at: string | null;
};
export type SearchRow = {
  label: string; // query or page URL
  clicks: number;
  impressions: number;
  ctr: number; // 0..1
  position: number; // average rank (lower is better)
};
export type SearchReportData = { rows: SearchRow[] };
export type GscAuthorize = { authorize_url: string };
export type GscSync = { rows_written: number; last_synced_at: string | null };

/** Build a `/searchconsole/{site_id}/{report}` path with the shared range params. */
export function gscPath(
  report: string,
  siteId: string,
  range: StatsRange,
  extra: Record<string, string> = {},
): string {
  const q = new URLSearchParams({ from: range.from, to: range.to, ...extra });
  return `/searchconsole/${encodeURIComponent(siteId)}/${report}?${q.toString()}`;
}

// --- Billing (Phase 14 — metered) ------------------------------------------
export type UsageSummary = {
  plan: string; // "free" | "metered"
  quota: number; // the free monthly allotment (what `pct` is measured against)
  used: number;
  pct: number;
  // "locked" is the free-over-limit state (dashboard paywall + server 402).
  status: "ok" | "warning" | "locked";
};

export type CheckoutResponse = { url: string };
export type PortalResponse = { url: string };

// --- Sharing (Phase 8) -----------------------------------------------------
/** A site's public share link (`url` is null when no live link exists). */
export type ShareLink = { url: string | null };

/** Metadata for a public (shared) dashboard — no account info. */
export type PublicSite = { domain: string; show_badge: boolean };

/**
 * WebSocket URL for the live stream of a site. A browser WebSocket can't send
 * an Authorization header, so the short-lived access token rides in the query
 * string (see the API's WS auth). Built here so no component assembles URLs.
 */
export function liveSocketUrl(siteId: string, token: string): string {
  const wsBase = BASE.replace(/^http/, "ws");
  return `${wsBase}/live/${encodeURIComponent(siteId)}?token=${encodeURIComponent(token)}`;
}

export type ResetTokenResponse = {
  reset_token: string;
};

// --- Stats (Phase 5) -------------------------------------------------------
export type MetricDelta = {
  value: number;
  previous: number | null;
  change_pct: number | null;
};

export type Overview = {
  pageviews: MetricDelta;
  visitors: MetricDelta;
  sessions: MetricDelta;
  bounce_rate: MetricDelta;
  avg_duration: MetricDelta;
};

export type TimeseriesPoint = { bucket: string; pageviews: number; visitors: number };
export type Timeseries = { interval: "hour" | "day"; points: TimeseriesPoint[] };

export type BreakdownRow = { label: string; pageviews: number; visitors: number };
export type Breakdown = { dimension: string; rows: BreakdownRow[] };

export type UtmRow = {
  utm_source: string;
  utm_medium: string;
  utm_campaign: string;
  pageviews: number;
  visitors: number;
};
export type Sources = { sources: BreakdownRow[]; utm: UtmRow[] };

export type PageRow = {
  label: string;
  count: number;
  visitors: number;
  // Present only on the engagement ranking (sort=engagement); null otherwise.
  avg_duration?: number | null;
  bounce_rate?: number | null;
};
export type Pages = { kind: string; metric: "pageviews" | "sessions"; rows: PageRow[] };

// --- Phase 10: channels + heatmap ------------------------------------------
export type ChannelRow = { channel: string; pageviews: number; visitors: number };
export type Channels = { channels: ChannelRow[] };

export type HeatmapCell = { dow: number; hour: number; pageviews: number; visitors: number };
export type Heatmap = { timezone: string; cells: HeatmapCell[] };

// --- Custom events + conversion goals (Phase 15, premium) ----------------
export type EventRow = { name: string; count: number; visitors: number };
export type EventsData = { rows: EventRow[] };
export type GoalKind = "pageview" | "custom";
export type Goal = { id: string; name: string; kind: GoalKind; target: string };
export type GoalInput = { name: string; kind: GoalKind; target: string };
export type GoalConversion = {
  goal: Goal;
  conversions: number;
  visitors: number;
  conversion_rate: number;
};

/**
 * Active dashboard filters (Phase 10) — exact-match slices on allowlisted
 * columns (country/device/browser/os/source/path). Threaded verbatim into every
 * stats request as query params; the server binds each value as a param (§9).
 */
export type StatsFilters = Record<string, string>;

/** A [from, to) window as ISO-8601 UTC strings (the stats API is UTC-only). */
export type StatsRange = { from: string; to: string };

/** Build a `/stats/*` path with the shared site_id + range query params. */
export function statsPath(
  endpoint: string,
  siteId: string,
  range: StatsRange,
  extra: Record<string, string> = {},
): string {
  const q = new URLSearchParams({ site_id: siteId, from: range.from, to: range.to, ...extra });
  return `/stats/${endpoint}?${q.toString()}`;
}

/**
 * Build a `/public/{token}/*` path with range params. The public shared
 * dashboard is unauthenticated and scoped to one site by the token.
 */
export function publicStatsPath(
  token: string,
  endpoint: string,
  range: StatsRange,
  extra: Record<string, string> = {},
): string {
  const q = new URLSearchParams({ from: range.from, to: range.to, ...extra });
  return `/public/${encodeURIComponent(token)}/${endpoint}?${q.toString()}`;
}

export class ApiError extends Error {
  status: number;
  /** Stable machine code from the error body (e.g. "account_locked"), if any. */
  code: string | null;
  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = "ApiError";
  }
}

function request(path: string, init: RequestInit, token: string | null): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${BASE}${path}`, { ...init, headers });
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const resp = await request(
    "/auth/refresh",
    { method: "POST", body: JSON.stringify({ refresh_token: refresh }) },
    null,
  );
  if (!resp.ok) {
    clearTokens();
    return false;
  }
  const data = (await resp.json()) as TokenResponse;
  setTokens(data.access_token, data.refresh_token);
  return true;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let resp = await request(path, init, getAccessToken());

  if (resp.status === 401 && (await tryRefresh())) {
    resp = await request(path, init, getAccessToken());
  }

  if (!resp.ok) {
    if (resp.status === 401) clearTokens();
    let detail = resp.statusText;
    let code: string | null = null;
    try {
      const body = (await resp.json()) as { detail?: string; code?: string };
      if (body.detail) detail = body.detail;
      if (body.code) code = body.code;
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(resp.status, detail, code);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/**
 * Fetch a public (share-token) endpoint with NO auth header. Used only by the
 * `/share/{token}` dashboard, whose data is served by the token-scoped
 * `/public/*` routes (the token is the credential, not a bearer JWT).
 */
export async function publicFetch<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new ApiError(resp.status, resp.statusText);
  return (await resp.json()) as T;
}

/**
 * Download an aggregated report as a CSV file (authed). The browser can't read
 * the server's Content-Disposition across CORS, so the filename is rebuilt
 * client-side. Triggers a save via a temporary object URL.
 */
export async function downloadExportCsv(
  siteId: string,
  range: StatsRange,
  dataset = "overview",
  filters: StatsFilters = {},
): Promise<void> {
  const q = new URLSearchParams({
    site_id: siteId,
    from: range.from,
    to: range.to,
    dataset,
    ...filters,
  });
  const path = `/stats/export?${q.toString()}`;
  let resp = await request(path, {}, getAccessToken());
  if (resp.status === 401 && (await tryRefresh())) {
    resp = await request(path, {}, getAccessToken());
  }
  if (!resp.ok) throw new ApiError(resp.status, resp.statusText);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const stamp = range.to.slice(0, 10);
  const a = document.createElement("a");
  a.href = url;
  a.download = `flowly-${dataset}-${stamp}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
