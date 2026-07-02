# Phase 3 — Ingestion Pipeline ✅ COMPLETE

**Goal:** events from the tracking script are validated, anonymised, enriched, and stored durably.
**Outcome:** a public, open-CORS `POST /collect` that returns **202 in milliseconds** — validating
the payload, computing a cookieless daily-rotating `visitor_hash`, enriching with geo + device,
filtering bots, rate-limiting per `(site_id, IP)`, and buffering an **IP-free** row to a Redis
Stream — plus a crash-safe batch writer that bulk-loads the buffer into ClickHouse. All Phase 3
checklist items done; verified live end-to-end (beacon → stream → ClickHouse).
**Date:** 2026-07-02
**Branch:** `phase-3-ingestion` (commit `e023750`) → merged to `main` via PR #3 (`607ed74`)

> Scope note: this delivers the **server half** of tracking — the Phase 2 tracker was the client
> half. Live pub/sub + WebSocket (Phase 4), usage metering (Phase 7), and retention deletion
> (Phase 9) are deliberately deferred; a seam for the live fan-out is left in `services/ingest.py`.

---

## Tools & versions used
| Tool | For |
|---|---|
| FastAPI | the `POST /collect` router |
| Pydantic v2 | `CollectEvent` payload validation at the boundary |
| redis-py (async) | ingest stream (`stream:events`), daily salt, rate-limit counters |
| clickhouse-connect (async) | the `events` table + bulk insert |
| **geoip2** (MaxMind GeoLite2-City) | country/region enrichment — **new dependency**, fail-open |
| stdlib `hashlib` / `secrets` | deterministic visitor hash + random daily salt |
| pytest + pytest-asyncio, fakeredis | the 25 new tests (55 total) |

The **one new runtime dependency** is `geoip2`; everything else was already declared.

---

## The two request paths (kept separate)

```
POST /collect  (public, open CORS, no auth) ── hot path, 202 in ms, Redis-only
  routers/collect.py
    → read raw text/plain body → JSON parse (422 on bad) → validate CollectEvent
    → client IP (X-Forwarded-For first hop | request.client.host)   [never logged/stored]
    → Origin header (for same-site source)
    → services/ingest.ingest_event():
         ├─ is_bot(ua)                      → drop, 202
         ├─ is_rate_limited(site_id, ip)    → over → drop, 202   (non-raising)
         ├─ event_id = uuid4()
         ├─ visitor_hash(ip, ua, site_id, daily_salt)
         ├─ geo.lookup(ip)      → (country, region)   [fail-open]
         ├─ useragent.parse(ua) → (device, browser, os)
         ├─ source = derive(utm_source, referrer, origin)
         └─ XADD stream:events MAXLEN ~ N   { enriched, IP-free row, ts = now UTC }
    → 202 Accepted

workers/batch_writer.py   (`uv run python -m app.workers.batch_writer`)
  XGROUP CREATE (idempotent) → XAUTOCLAIM reclaim (crash recovery)
  loop: XREADGROUP … > → coerce types (str→UUID/datetime/int) → insert_events (bulk) → XACK
```

---

## What we built (by area)

### Ingestion (`apps/api/app`)
1. **`models/events.py`** — `CollectEvent` Pydantic model matching the Phase 2 wire contract
   (`site_id, path, referrer, screen_w, utm_*`). `extra="ignore"` so a stray field (e.g. the
   dropped `language`) never 422s; `screen_w` clamped to `0..65535` (UInt16) rather than rejected.
2. **`services/useragent.py`** — zero-dependency regex `parse(ua) → (device, browser, os)` and
   `is_bot(ua)` (marker list + empty-UA). Drops crawlers/monitors before they're counted.
3. **`services/geo.py`** — `geoip2` reader loaded once from `GEOIP_DB_PATH`; `lookup(ip) → (country,
   region)`. **Fail-open**: missing/unreadable `.mmdb` or unknown IP → `("", "")`, never raises.
4. **`services/visitor.py`** — cookieless `visitor_hash` = SHA-256 of `pepper + salt + site_id + ip
   + ua` (deterministic, per-site, per-day); `get_daily_salt()` keyed `salt:{YYYYMMDD}` with an
   in-process cache + atomic `SET NX EX` (24h TTL) so concurrent creators converge. Raw IP is an
   input only — never stored or logged.
5. **`services/ingest.py`** — the orchestrator: bot filter → rate limit → `event_id` → hash →
   enrich → `source` derivation → `XADD`. Builds an **IP-free** row (`None`→`""`) onto a bounded
   `stream:events`. `source` = UTM if present → else external referrer host → else `direct`
   (same-site referrer stripped by comparing against the `Origin` host).
6. **`routers/collect.py`** — thin public endpoint: raw-body parse, XFF-aware client IP, `Origin`
   read, returns **202** with `Access-Control-Allow-Origin: *`. Bot / over-limit drops still return
   202 so the filter isn't detectable.
7. **`core/ratelimit.py`** — added a **non-raising** `is_rate_limited(redis, site_id, ip)` (over
   the shared `INCR`+`EXPIRE` primitive) so `/collect` drops silently instead of 429-ing.
8. **`core/exceptions.py`** — added `ValidationError(AppError, 422)` for service-layer rejection.

### Storage (`apps/api/app/db`)
9. **`db/clickhouse.py`** — the `events` DDL (`MergeTree`, `PARTITION BY toYYYYMM(ts)`,
   `ORDER BY (site_id, ts)`, adds an `event_id UUID` for dedupe-ability), `init_events_table()`
   (idempotent), a bulk `insert_events()`, a `ClickHouseDep` alias, and a `--init` entry point.

### Worker (`apps/api/app/workers`)
10. **`workers/batch_writer.py`** — consumer-group drain (`XREADGROUP`), **`XAUTOCLAIM` reclaim** of
    stale pending entries on startup + periodically (crash-safe at-least-once), type coercion off
    the string-only stream, one bulk insert per batch, `XACK` only after a successful insert.
    Malformed entries are dropped (acked) so they can't wedge the stream.

### Config, deps, docs
11. **`config.py` + `.env.example`** — 5 settings: `visitor_salt_secret` (pepper), `geoip_db_path`,
    `stream_maxlen`, `collect_rate_limit`, `collect_rate_window`. **`pyproject.toml`** gains `geoip2`.
12. **`CLAUDE.md`** — §5 Geo-IP row (`geoip2`), §6 env vars, all Phase 3 boxes ticked, footer refreshed.

---

## Steps we followed (build order)

The plan (`.claude/plan/phase-03-implementation-plan.md`) was built in a dependency-correct order,
each step tested before the next:

1. **Config & deps** — `uv add geoip2`; 5 new settings; `.env.example`.
2. **`CollectEvent` model** — wire contract, `extra="ignore"`, clamped `screen_w`.
3. **UA parser + bot filter** (`services/useragent.py`).
4. **Geo lookup** (`services/geo.py`, fail-open).
5. **Visitor hashing + daily salt** (`services/visitor.py`).
6. **ClickHouse table + helpers** (`db/clickhouse.py`, `--init`).
7. **Non-raising rate limiter** (`core/ratelimit.py`).
8. **`ValidationError`** (`core/exceptions.py`).
9. **Ingest orchestrator** (`services/ingest.py`).
10. **`/collect` router + `main.py` wiring**.
11. **Batch writer worker** (`workers/batch_writer.py`).
12. **Tests, docs, and the live end-to-end smoke.**

Steps 2–5, 7, 8 were verified with pure unit tests / `fakeredis` (no infra); 6, 11 and the final
smoke needed live ClickHouse + Redis.

---

## Features completed (Phase 3 checklist)
- [x] `POST /collect` public, open CORS, returns `202` fast (`routers/collect.py` → `services/ingest.py`)
- [x] Payload validated via a Pydantic model (`models/events.py`)
- [x] Cookieless visitor ID (`services/visitor.py`): `hash(IP + UA + daily salt)`, salt rotates daily
- [x] Bot filtering (`services/useragent.py`) — dropped before counting
- [x] Per-`(site_id, IP)` rate limiting (`core/ratelimit.py`, non-raising, silent 202 drop)
- [x] Buffer the validated, IP-free event to `stream:events` (bounded `MAXLEN ~`)
- [x] Batch writer worker (`workers/batch_writer.py`): consumer group + `XAUTOCLAIM` reclaim, bulk insert, `XACK`
- [x] ClickHouse `events` table (`db/clickhouse.py` + `--init`) — adds `event_id`
- [x] Hot-path enrichment: geo (fail-open), device/browser/os, `source` from UTM/referrer vs `Origin`
- [x] Tests: bad payload rejected, bot dropped, valid event enqueued (IP-free) and lands in ClickHouse

---

## Verified
- **Lint + tests:** `uv run ruff check .` clean; `uv run pytest` → **55 passed** (25 new Phase 3 tests).
- **Live end-to-end smoke** (real Redis + ClickHouse `flowly` DB):
  1. `uv run python -m app.db.clickhouse --init` → table created in `flowly` (16 columns, correct types).
  2. Beacon-shaped `curl` POST to `/collect` → **HTTP 202**, `ACAO: *`.
  3. `XLEN stream:events` → **1**.
  4. `batch_writer` drained → **1 inserted, 0 pending, no type/DDL error**.
  5. `SELECT FROM flowly.events` → row landed with `event_id` UUID, `ts` DateTime64, `visitor_hash`
     64-char hex, `source='newsletter'`, `device/browser/os = desktop/Chrome/Windows`,
     `country/region = ""` (expected — `GEOIP_DB_PATH` blank), `screen_w=1440`, **no `ip` column**.
- **Privacy checks:** the stream row and stored event contain no raw IP (asserted in tests + smoke).

---

## Decisions (as built; flippable)
- **Enrich on the hot path**, buffer IP-free — the raw IP is needed for hash + geo, and it must
  never reach the stream (no raw IP at rest). GeoIP mmdb reads are µs-scale, so the ms budget holds.
- **Full enrichment now** — device/browser/os via zero-dep regex; country/region via GeoLite2 (fail-open).
- **Rate limit** keyed by `(site_id, IP)` — a generous configurable **abuse backstop**, not precise
  metering (that's Phase 7). Over-limit drops silently with 202.
- **Accept all well-formed `site_id`s** — no Postgres lookup on the hot path (site existence checks
  are Phase 6). `/collect` depends on Redis only.
- **`event_id` (UUID) at ingest** — makes at-least-once redelivery dedupe-able; MVP keeps plain
  `MergeTree` (rare crash-duplicates accepted); upgrade path is `ReplacingMergeTree` on `event_id`.
- **Client IP = XFF first hop else socket** — correct behind a CDN (known limitation: XFF is
  spoofable; prod should trust it only from known proxy ranges).

## Open / follow-ups
- Live pub/sub + active-users ZSET + `WS /live/{site_id}` → **Phase 4** (seam left in `ingest.py`).
- Usage metering counter → Phase 7; per-plan retention TTL/deletion → Phase 9.
- Populate `GEOIP_DB_PATH` with a real `GeoLite2-City.mmdb` to enable country/region (currently fail-open).
- Trust `X-Forwarded-For` only from known proxy ranges (prod hardening).
- Upgrade UA parsing to a maintained library if regex accuracy proves insufficient.

---

## Key commands
```bash
# create the ClickHouse events table (once)
uv run python -m app.db.clickhouse --init

# run the API (dev) and the batch writer (separate process)
uv run uvicorn app.main:app --reload
uv run python -m app.workers.batch_writer

# lint + tests
uv run ruff check . && uv run pytest
```

### Live smoke (needs Redis + ClickHouse running)
```bash
curl -X POST http://localhost:8000/collect \
  -H 'Content-Type: text/plain' -H 'Origin: https://demo.example' \
  --data '{"site_id":"demo","path":"/pricing","referrer":"https://google.com","screen_w":1440,"utm_source":"newsletter"}'
redis-cli XLEN stream:events            # -> grows by 1
uv run python -m app.workers.batch_writer
clickhouse-client -q "SELECT site_id, source, device, visitor_hash FROM flowly.events LIMIT 5"
```
