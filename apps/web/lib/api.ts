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

export type PageRow = { label: string; count: number; visitors: number };
export type Pages = { kind: string; metric: "pageviews" | "sessions"; rows: PageRow[] };

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

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
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
    try {
      const body = (await resp.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
