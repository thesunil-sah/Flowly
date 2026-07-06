"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { apiFetch, liveSocketUrl } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

// One live pageview as forwarded by the API (no visitor_hash, no IP).
export type LiveEvent = {
  path: string;
  source: string;
  country: string;
  region: string;
  device: string;
  browser: string;
  ts: string;
};

// A feed row is a LiveEvent plus a stable client-side key for React lists.
export type FeedRow = LiveEvent & { key: number };

export type PageCount = { path: string; count: number };
export type CountryCount = { country: string; count: number };

type ServerMessage =
  | { type: "snapshot"; count: number }
  | { type: "count"; count: number }
  | ({ type: "event" } & LiveEvent);

const FEED_CAP = 50;
const TOP_PAGES = 10;
const MAX_BACKOFF_MS = 15_000;
// WS close codes.
const NORMAL_CLOSURE = 1000;
const POLICY_VIOLATION = 1008; // auth/ownership rejection from the API.

/**
 * Subscribe to a site's live traffic over a WebSocket. Returns the current
 * online count, a capped recent-event feed, the busiest current pages, and the
 * connection state. Reconnects with backoff on unexpected drops; on a policy
 * close (1008) it refreshes the token once and retries, else it stops.
 */
export function useLiveTraffic(siteId: string | null) {
  const [count, setCount] = useState(0);
  const [feed, setFeed] = useState<FeedRow[]>([]);
  const [connected, setConnected] = useState(false);
  const keySeq = useRef(0);

  // The consumer remounts this hook per site (React key), so state starts fresh
  // for each siteId and the effect only ever connects one site per lifetime.
  useEffect(() => {
    if (!siteId) return;

    let ws: WebSocket | null = null;
    let disposed = false;
    let attempts = 0;
    let refreshedOnce = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const scheduleReconnect = () => {
      if (disposed) return;
      const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** attempts);
      attempts += 1;
      timer = setTimeout(connect, delay);
    };

    const handle = (msg: ServerMessage) => {
      if (msg.type === "snapshot" || msg.type === "count") {
        setCount(msg.count);
        return;
      }
      if (msg.type !== "event" || typeof msg.path !== "string") {
        return; // unknown/malformed frame — don't push a blank feed row
      }
      const row: FeedRow = {
        path: msg.path,
        source: msg.source,
        country: msg.country,
        region: msg.region,
        device: msg.device,
        browser: msg.browser,
        ts: msg.ts,
        key: keySeq.current++,
      };
      setFeed((prev) => [row, ...prev].slice(0, FEED_CAP));
    };

    function connect() {
      if (disposed) return;
      const token = getAccessToken();
      if (!token) {
        // Session not established yet (token re-mints on load); retry shortly.
        scheduleReconnect();
        return;
      }
      ws = new WebSocket(liveSocketUrl(siteId!, token));
      ws.onopen = () => {
        attempts = 0;
        // A fresh connection means auth is good again, so re-arm the one-shot
        // token refresh — otherwise a later 1008 would never recover.
        refreshedOnce = false;
        setConnected(true);
      };
      ws.onmessage = (e) => {
        let msg: ServerMessage;
        try {
          msg = JSON.parse(e.data) as ServerMessage;
        } catch {
          return; // ignore non-JSON frames (pings, proxy noise)
        }
        handle(msg);
      };
      ws.onclose = (e) => {
        setConnected(false);
        if (disposed || e.code === NORMAL_CLOSURE) return;
        if (e.code === POLICY_VIOLATION) {
          // Likely an expired access token — refresh once, then retry. If the
          // refresh fails or it's really an ownership issue, give up.
          if (refreshedOnce) return;
          refreshedOnce = true;
          apiFetch("/auth/me")
            .then(() => connect())
            .catch(() => undefined);
          return;
        }
        scheduleReconnect();
      };
    }

    connect();

    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      ws?.close(NORMAL_CLOSURE);
    };
  }, [siteId]);

  const currentPages = useMemo<PageCount[]>(() => {
    const counts = new Map<string, number>();
    for (const e of feed) counts.set(e.path, (counts.get(e.path) ?? 0) + 1);
    return [...counts.entries()]
      .map(([path, n]) => ({ path, count: n }))
      .sort((a, b) => b.count - a.count)
      .slice(0, TOP_PAGES);
  }, [feed]);

  // Live visitors by country (Phase 11), aggregated from the same capped feed —
  // the live payload already carries `country` (no visitor_hash). Blank country
  // (geo failed open) is dropped so the panel doesn't show an "Unknown" bar.
  const currentCountries = useMemo<CountryCount[]>(() => {
    const counts = new Map<string, number>();
    for (const e of feed) {
      if (e.country) counts.set(e.country, (counts.get(e.country) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([country, n]) => ({ country, count: n }))
      .sort((a, b) => b.count - a.count)
      .slice(0, TOP_PAGES);
  }, [feed]);

  return { count, feed, currentPages, currentCountries, connected };
}
