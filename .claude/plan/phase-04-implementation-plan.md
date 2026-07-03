# FLOWLY — PHASE 4 IMPLEMENTATION PLAN (FINAL)

## Real-time / live traffic

> Planning-only deliverable — **no code is written in this task.**

---

## Short description

Flowly's headline feature is **"live visitors right now."** Phase 4 adds the real-time path on top
of the Phase 3 ingest pipeline: as each event is ingested, publish it to a per-site Redis pub/sub
channel and record the visitor in a per-site "active" sorted set (ZSET). A WebSocket streams the
live count + event feed to an **authed, ownership-verified** dashboard view. Per CLAUDE.md §9:
**Redis is the source of truth for "right now" — never hit ClickHouse for the live counter.**

---

## Tools & stack (all already in CLAUDE.md §5 — no new dependency, no new env var)

| Concern | Tool |
|---|---|
| WebSocket + HTTP | FastAPI (native WebSocket) |
| Pub/sub + presence ZSET | redis-py (async), `decode_responses=True` |
| WS auth (verify only) | reuse `core/security.py::decode_token(token, "access")` |
| Ownership check | SQLAlchemy 2.0 async (`Site` / `Account`) |
| Frontend live connection | Next.js **native `WebSocket`** in a client hook |
| Frontend site list | TanStack Query |
| Styling | Tailwind (match `components/form.tsx`) |
| Tests | pytest + fakeredis (shared `FakeServer`) + `TestClient.websocket_connect` |

`LIVE_WINDOW_SECONDS = 300` is a module constant (not env).

---

## Locked decisions

- **D1 — Presence ZSET bounded on write.** Keys `active:{site_id}` (ZSET scored by `datetime.now(UTC).timestamp()`) and `live:{site_id}` (channel). `mark_active` = **ZADD → ZREMRANGEBYSCORE(0, now-window) → EXPIRE(key, window+buffer)**, all in **one Redis pipeline** (§9 hot-path speed). Write-side eviction + key EXPIRE bound growth even with zero viewers and self-clean idle sites.
- **D2 — WS session is explicit and short-lived.** The WS route does **not** use `Depends(get_session)`. After `ws.accept()`, open a session via `async_session_factory()`, run the ownership query, and **close it before entering the forward loop** — the loop is Redis-only, so no Postgres connection is pinned for the socket's lifetime.
- **D3 — Origin check mandatory.** WS bypasses CORS middleware, so the handler compares `ws.headers.get("origin")` to `settings.web_base_url` and `close(1008)` on mismatch. Only origin guard on the socket.
- **D4 — Subscribe before snapshot.** Order: accept → origin → auth → ownership → **subscribe** → send `{"type":"snapshot","count":…}` → forward loop. No event lost in the gap.
- **D5 — WS token via `?token=` (accepted MVP risk).** Browser `WebSocket` can't set headers; the short-lived access JWT rides in the query string. Accepted risk: the URL (incl. token) may land in uvicorn/proxy access logs — mitigated by short TTL; if unacceptable, filter access logging for `/live` or move the token to a first WS message / `Sec-WebSocket-Protocol`. The handler never logs the token.
- **D6 — `count_active` evicts-then-counts** (ZREMRANGEBYSCORE then ZCARD) — documented as eviction-inclusive so no caller assumes a pure getter.
- **D7 — Reconnect policy.** Frontend reconnects with backoff on unexpected close; **stops on `1000`** (normal). On **`1008`** (auth/ownership) it attempts **one** `tryRefresh()` + reconnect with a freshly-read token, then stops (avoid hammering). Each reconnect re-reads `getAccessToken()` (never closes over a stale token).
- **D8 — Read-only `GET /sites` borrowed from Phase 6.** Minimal authed, ownership-scoped site list + picker so the live view is demoable. `SiteOut` shaped for Phase 6 reuse.
- **D9 — Client payload carries no anonymous id.** Forwarded event = `{path, source, country, region, device, browser, ts}` — no `visitor_hash`, no IP. The hash is server-side presence only.
- **D10 — Live fan-out is best-effort.** In `ingest_event`, `mark_active` + `publish_event` are wrapped in `try/except` (debug-log). The durable buffer already succeeded; ingestion must never fail/slow for the live path (§9).
- **D11 — Single Redis access path (testability).** Both the ingest fan-out and the WS pub/sub resolve to the **same** client. `count_active`/`mark_active`/`publish_event` take a `redis` arg; the WS passes `get_client()`; ingest passes its injected client. Tests back a `fakeredis.FakeServer` and set `app.db.redis._client` to a fake on that server **and** override `get_redis` to the same instance — so publisher and subscriber share one backend.
- **D12 — Pub/sub loop lives in the service, not the router (§3 layering).** `services/live.py` exposes `subscribe_events(site_id) -> AsyncIterator[dict]`; the router just auth → own → iterate → send, staying thin.

---

## What already exists (reuse — do not rebuild)

- `services/ingest.py::ingest_event` — hot path; ends by `XADD`-ing an IP-free row dict. **Single hook point** (right after the successful `XADD`, ~line 114).
- `db/redis.py::get_redis` / `get_client` — process-wide async client, `decode_responses=True` (pub/sub payloads arrive as `str`).
- `core/security.py::decode_token(token, "access") -> UUID` — pure JWT verify, no HTTP objects (the `CurrentUser` dependency needs an `Authorization` header a browser WebSocket can't send).
- `models/tables.py::Site` (site_id unique+indexed, account_id indexed) + `Account.sites`.
- `db/postgres.py::async_session_factory`; `core/exceptions.py::AppError`; `main.py::create_app` (router registration + dashboard-locked CORS).
- Frontend: `(dashboard)/layout.tsx` auth-guard (valid in-memory access token exists by render time); `lib/auth.ts::getAccessToken`; `lib/api.ts` (`NEXT_PUBLIC_API_URL`); `hooks/useAuth.ts` conventions; `components/form.tsx` Tailwind style.

---

## Step-by-step build order (each step testable before the next)

### Step 1 — `app/services/live.py` (Redis-only + ownership helper)
- `LIVE_WINDOW_SECONDS = 300`; `EXPIRE_BUFFER = 60`; `_active_key`, `_channel`.
- `async mark_active(redis, site_id, visitor_hash, now)` → **pipeline**: `ZADD` + `ZREMRANGEBYSCORE(key,0,now-window)` + `EXPIRE(key, window+buffer)` (D1).
- `async count_active(redis, site_id, now)` → `ZREMRANGEBYSCORE(key,0,now-window)` then `ZCARD` (D6).
- `async publish_event(redis, site_id, payload: dict)` → `PUBLISH _channel json.dumps(payload)`.
- `async subscribe_events(site_id) -> AsyncIterator[dict]` (D12) — creates `get_client().pubsub()`, `subscribe(_channel, ...)` with **`ignore_subscribe_messages=True`** (or filter `type=="message"`), yields decoded `json.loads(msg["data"])`; guarantees `unsubscribe()` + `aclose()` in `finally`.
- `async get_owned_site(session, site_id, account_id) -> Site | None` → `session.scalar(select(Site).where(Site.site_id==, Site.account_id==))`.
**Done:** service unit tests pass on fakeredis.

### Step 2 — Hook fan-out into `services/ingest.py::ingest_event`
After the successful `XADD`:
- payload = `{path, source, country, region, device, browser, ts}` (no `visitor_hash`, D9).
- `now = datetime.now(UTC).timestamp()`; then, in one `try/except Exception` (debug-log, D10): `await mark_active(redis, site_id, row["visitor_hash"], now)`; `await publish_event(redis, site_id, payload)`.
**Done:** `test_ingest.py` shows `active:{site_id}` populated + subscriber receives payload with no hash/IP.

### Step 3 — `app/routers/live.py`
- `router = APIRouter(tags=["live"])`.
- `GET /sites` (authed `CurrentUser`) → `list[SiteOut]` scoped to `account.id`.
- `WS /live/{site_id}`, exact order:
  1. `await ws.accept()`.
  2. **Origin (D3):** `origin != settings.web_base_url` → `close(1008)`, return.
  3. `token = ws.query_params.get("token")`; `decode_token(token,"access")` in `try`; any `AppError` → `close(1008)`, return. Never log token (D5).
  4. **Ownership (D2):** `async with async_session_factory() as session: site = await get_owned_site(session, site_id, account_id)` — session closes here; `if site is None: close(1008)`, return.
  5. Subscribe FIRST (D4/D12): iterate `subscribe_events(site_id)`.
  6. Send `{"type":"snapshot","count": await count_active(get_client(), site_id, now)}`.
  7. Run tasks with `asyncio.wait(FIRST_COMPLETED)` then cancel the losers (no leak):
     - **forward:** `async for ev in subscribe_events(...): await ws.send_json({"type":"event", **ev})`
     - **heartbeat (~10s):** `await ws.send_json({"type":"count","count": await count_active(...)})`
     - **receiver:** `await ws.receive_text()` loop — completes on `WebSocketDisconnect` for prompt teardown.
  8. `finally`: subscribe_events cleans its own pubsub; ensure tasks cancelled.
**Done:** `test_live_ws.py` passes (owned→snapshot+event; wrong owner/bad token/bad origin→1008).

### Step 4 — `SiteOut` in `app/models/schemas.py`
`SiteOut(id, site_id, domain)` — shaped for Phase 6 reuse (D8).

### Step 5 — Wire `app/main.py`
`from app.routers import ... live`; `app.include_router(live.router)` among the authed routers (dashboard CORS stays locked). No new migration.

### Step 6 — `hooks/useLiveTraffic.ts` (`"use client"`, named export)
`useLiveTraffic(siteId)` → `{ count, feed, currentPages, connected }`.
- WS URL: `NEXT_PUBLIC_API_URL.replace(/^http/,"ws") + "/live/" + siteId + "?token=" + getAccessToken()` (re-read token each (re)connect, D7).
- Native `WebSocket` in `useEffect` (cleanup on unmount / siteId change). Parse: `snapshot`/`count` → count; `event` → prepend to a **capped feed (≤50)**, recompute `currentPages` (top paths among recent events).
- Reconnect w/ backoff on unexpected close; stop on `1000`; on `1008` do one `tryRefresh()` + reconnect, else stop (D7). Gate opening on `getAccessToken()` non-null.

### Step 7 — `useSites()` hook
TanStack Query wrapper over `apiFetch<SiteOut[]>("/sites")`, matching `hooks/useAuth.ts`.

### Step 8 — `app/(dashboard)/live/page.tsx` (`"use client"`)
- `useSites()` → `<select>` picker (auto-select if one; empty-state message + "seed a site / Phase 6" hint if none).
- Tailwind (match `components/form.tsx`): big live-counter card; live-feed list (`path · country · device · browser · source · time`); current-pages list (`path → count`). Panels labeled "waiting for live events…" until first event. No chart. Inherits `(dashboard)` auth guard.

### Step 9 — (Optional) `components/live/` — `LiveCounter`, `LiveFeed`, `CurrentPages`
Named exports, `"use client"`; inline if small.

### Step 10 — Tests (`apps/api/tests`, pytest + fakeredis)
- **Shared backend (D11):** fixture builds `fakeredis.FakeServer`, one `FakeRedis(server=…)`; sets `app.db.redis._client` to it **and** overrides `get_redis` to return it — so ingest publish and WS subscribe share data.
- `test_live.py` (service): `mark_active`+`count_active` evict past window; 2 distinct hashes→2, same twice→1; **write-side eviction bounds ZSET with no reader** (D1); key gets a TTL; `publish_event`→subscriber; `subscribe_events` skips the subscribe-confirmation; `get_owned_site` None for foreign account.
- Extend `test_ingest.py`: after `ingest_event`, `active:{site_id}` has the visitor + subscriber receives payload; assert **no `visitor_hash`/IP**.
- `test_live_ws.py` (`TestClient.websocket_connect`, shared fake + seeded Account+Site): owned+valid→snapshot then forwarded event; wrong owner→1008; missing/invalid token→closed; **bad Origin→1008** (D3). Exercises the #1 multi-tenant leak rule.
- `GET /sites`: only caller's sites; unauthenticated→401.

### Step 11 — Docs + verification
Tick CLAUDE.md Phase 4 boxes + refresh footer; `ruff` + full `pytest`; then manual smoke below.

---

## Verification (end-to-end, manual)

1. Postgres + Redis running (`alembic upgrade head` — no new migration).
2. Seed a `Site` row for your account (manual insert, as Phase 2/3 dev testing did) until Phase 6.
3. Run API (`uv run uvicorn app.main:app --reload`), batch writer optional, `pnpm --filter web dev`.
4. Sign in → `/live`, pick the site. Another tab: load the Phase 2 tracker harness (`apps/tracker/test/index.html`) with that `site_id`.
5. Confirm: counter increments; pageview appears in feed within ~1s; current-pages updates; count decays after 5 min idle; a `site_id` you don't own → socket closes.
6. `uv run pytest` and `uv run ruff check . && uv run ruff format .` green.

---

## Definition of done (CLAUDE.md §10)

- [ ] Live counter/feed/pages work end-to-end from a real tracker beacon.
- [ ] WS verifies token **and** site ownership **and** Origin; unowned → closed (no data leak).
- [ ] Presence ZSET bounded on write (evict + EXPIRE); can't grow with no viewer.
- [ ] WS uses an explicit, **short-lived** session (closed before the forward loop) — no pinned pool connection.
- [ ] Subscribe before snapshot; subscribe-confirmation filtered; prompt disconnect via receiver task.
- [ ] Ingest fan-out best-effort; never breaks/slows `/collect`; live counter reads only Redis.
- [ ] No PII/token/raw-IP logged; forwarded payload carries no `visitor_hash`.
- [ ] Single shared Redis backend in tests (publisher == subscriber); lint + tests pass; Phase 4 boxes ticked + footer refreshed.

---

## Out of scope / open items

- **Out of scope:** historical stats/charts (Phase 5), full add-site onboarding + install verification (Phase 6 — only read-only `GET /sites` borrowed here), billing/metering (Phase 7).
- **O1 — Live window (D1).** 300 s constant; to make configurable add `live_window_seconds: int = 300` to `config.py` + `.env.example` in the same change (§6).
- **O2 — WS token transport (D5).** `?token=` with short TTL; flip to first-message / `Sec-WebSocket-Protocol` (and/or filter uvicorn access logs for `/live`) if URL-in-logs is unacceptable.
- **O3 — Current-pages fidelity.** Derived client-side from the ≤50-event feed (approximate; rebuilds on reconnect). Acceptable for the live view; a server-side per-page presence count can come later if needed.
- **O4 — Multiple API workers.** Pub/sub fan-out and the shared `active:{site_id}` ZSET are cross-process-correct via Redis; revisit heartbeat/presence behavior only under real multi-instance load.
