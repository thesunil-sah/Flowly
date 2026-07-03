# Phase 4 — Real-time / Live Traffic ✅ COMPLETE

**Goal:** the dashboard shows visitors live (the headline feature).
**Outcome:** each ingested pageview is fanned out in real time — recorded in a per-site presence
ZSET and published to a per-site Redis channel — and a `WS /live/{site_id}` streams a live count
snapshot, per-event pushes, and a periodic count heartbeat to an **authed, ownership-verified**
dashboard view. All Phase 4 checklist items done; 69 tests pass, ruff + format clean.
**Date:** 2026-07-03
**Branch:** `main` (implementation from the approved `phase-04-implementation-plan.md`)

> Redis is the source of truth for "right now" — the live counter never touches ClickHouse
> (CLAUDE.md §9). The live fan-out reuses the seam left in `services/ingest.py` in Phase 3.

---

## Tools & versions used
| Tool | For |
|---|---|
| FastAPI (native WebSocket) | `WS /live/{site_id}` + `GET /sites` |
| redis-py (async) | presence ZSET (`active:{site_id}`) + pub/sub channel (`live:{site_id}`) |
| PyJWT (via `decode_token`) | WS token verification (token in `?token=`, browser WS can't set headers) |
| SQLAlchemy 2.0 (async) | site-ownership lookup (`get_owned_site`) |
| Next.js native `WebSocket` | `hooks/useLiveTraffic.ts` (no ws library added) |
| TanStack Query | `hooks/useSites.ts` |
| pytest + pytest-asyncio, fakeredis | 14 new tests (69 total) |

**No new runtime dependency. No new env var** (`LIVE_WINDOW_SECONDS = 300` is a module constant).

---

## Backend

### `services/live.py` (Redis-only + one ownership query)
- `mark_active` — one pipeline: `ZADD active:{site_id}` + `ZREMRANGEBYSCORE` (evict stale) +
  `EXPIRE` (key TTL). Write-side eviction + TTL bound the set even with **no viewer** and
  self-clean idle sites — the correctness fix over the first draft.
- `count_active` — evicts-then-`ZCARD` (eviction-inclusive; documented, not a pure getter).
- `publish_event` — `PUBLISH live:{site_id} {json}`.
- `subscribe_events(site_id, on_ready=…)` — owns a per-connection `pubsub()` off the shared
  client, `ignore_subscribe_messages=True` + defensive `type=="message"` filter, always tears
  down. `on_ready` fires **after subscribe, before the first read** so the WS can send its count
  snapshot with no gap where an event is missed.
- `get_owned_site` — `select(Site).where(site_id==, account_id==)`; the account predicate is the
  tenant-isolation guard (the #1 leak path).

### `services/ingest.py` hook
Right after the durable `XADD`, a **best-effort** (`try/except`, debug-log) block calls
`mark_active` + `publish_event`. Ingestion never fails or slows because the live path hiccupped.
The forwarded payload is `{path, source, country, region, device, browser, ts}` — **IP-free and
carries no `visitor_hash`**.

### `routers/live.py`
- `WS /live/{site_id}`: `accept` → **Origin** check (WS bypasses CORS) → `?token=` `decode_token`
  → **ownership** on a short-lived session (released before the Redis-only stream loop) →
  subscribe → snapshot → three tasks: **forward** (per-event), **heartbeat** (~10 s count),
  **receiver** (`ws.receive_text` for prompt disconnect). Any rejection → `close(1008)` (opaque:
  a client can't tell "bad token" from "not your site").
- `GET /sites`: authed, ownership-scoped list for the picker (a thin read-only borrow from Phase 6).
- `SiteOut` schema added to `models/schemas.py`; router wired in `main.py` under the locked CORS.

---

## Frontend (`apps/web`)
- `hooks/useLiveTraffic.ts` — native `WebSocket`; parses `snapshot`/`count`/`event`; capped feed
  (≤50) and derived current-pages; backoff reconnect; on `1008` one `/auth/me` refresh + retry,
  else stop; stops on `1000`. Token read fresh from `getAccessToken()` each connect.
- `lib/api.ts` — `Site` type + `liveSocketUrl()` (derives `ws(s)://…/live/{id}?token=` from
  `NEXT_PUBLIC_API_URL`).
- `hooks/useSites.ts` — TanStack Query wrapper over `GET /sites`.
- `components/live.tsx` — `LiveCounter`, `LiveFeed`, `CurrentPages` (named exports, Tailwind).
- `app/(dashboard)/live/page.tsx` — inherits the `(dashboard)` auth guard; site picker; remounts
  the live view per site via React `key` (clean per-site state, no effect-driven resets).

---

## Tests (14 new, 69 total)
- `test_live.py` — count/eviction/window, same-visitor dedupe, **write-side bound with no reader**,
  key TTL, publish→subscribe (subscribe-confirmation filtered), `get_owned_site` ownership scope.
- `test_ingest.py` (extended) — after `ingest_event`: presence set populated + subscriber receives
  an **IP-free, hash-free** payload.
- `test_live_ws.py` — bad origin / missing token / invalid token / **unowned site** → `1008`;
  owned site → snapshot then a `/collect`-published event forwarded. Runs DB-free (ownership
  patched) on a shared fakeredis wired into both the injected client and the module client, over
  one TestClient portal loop so publish reaches the subscriber.
- `test_sites.py` — `GET /sites` ownership-scoped; unauthenticated → 401.

---

## Deviations from the plan
- `count_active` uses `ZCARD` after eviction (equivalent to the plan's `ZCOUNT`-last-5-min, since
  stale members are already removed).
- The WS route obtains the session via `postgres.async_session_factory()` and Redis via
  `get_client()` (module singletons) — tests monkeypatch those directly, per the plan's D11 seam.

## Deferred (unchanged)
Historical stats/charts (Phase 5), full add-site onboarding + install verification (Phase 6 — only
read-only `GET /sites` borrowed here), billing/metering (Phase 7).
