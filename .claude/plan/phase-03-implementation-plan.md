# Phase 3 — Ingestion Pipeline — Implementation Plan

> **Goal:** turn the pageviews the Phase 2 tracker already fires into durably-stored,
> anonymised analytics events. Build a public `POST /collect` that validates, anonymises,
> enriches, filters, rate-limits, and buffers each event to Redis — returning **202 in
> milliseconds** — plus a background worker that bulk-loads the buffer into ClickHouse.
>
> _Save location:_ `apps/api` (backend). This document lives at `.claude/plan/phase-03-implementation-plan.md`.

---

## 1. What we are implementing

Phase 2 shipped the **client half** of tracking (the JS tracker sends a `text/plain` JSON
pageview to `/collect` via `sendBeacon`). The **server half does not exist yet** — there is no
`/collect` endpoint, no ingest logic, no visitor hashing, no ClickHouse `events` table, no
batch writer. Events the tracker sends currently hit nothing.

Phase 3 builds that server half, as two deliberately separate request paths:

**A) Ingestion hot path — `POST /collect`** (public, open-CORS, no auth, must return in ms)
1. Read the raw `text/plain` body and validate it against a Pydantic model.
2. Derive the client IP (proxy-aware) and read the `Origin` header — **the IP is never logged or stored.**
3. Filter bots; drop over-rate-limit floods (per `site_id`+IP).
4. Compute the **cookieless, daily-rotating `visitor_hash`** = `hash(IP + UA + daily salt)`.
5. Enrich: `country`/`region` (GeoIP), `device`/`browser`/`os` (UA parse), `source` (referrer/UTM).
6. Push a **fully-enriched, IP-free** event onto the Redis Stream `stream:events` and return **202**.

**B) Batch writer worker** (separate process)
- Drains `stream:events` with a Redis **consumer group**, **bulk-inserts** into ClickHouse,
  acknowledges only on success, and **reclaims stale pending entries** so a crash can't lose data.

**Why enrichment happens on the hot path (not in the worker):** the raw IP is needed for both
the visitor hash and geo lookup, and CLAUDE.md forbids raw IPs "at rest." The Redis Stream is at
rest, so the IP must be consumed and discarded *before* buffering. GeoIP reads are memory-mapped
(µs) and UA parsing is a regex, so the millisecond budget still holds.

### Architecture

```
POST /collect  (public, open CORS, no auth) ── hot path, 202 in ms, Redis-only (no Postgres)
  routers/collect.py
    → read raw text/plain body → JSON parse (422 on bad) → validate (CollectEvent, extra="ignore")
    → client IP (X-Forwarded-For first hop | request.client.host)   [never logged/stored]
    → Origin header                                                 [for same-site source]
    → services/ingest.ingest_event(event, ip, ua, origin, redis):
         ├─ is_bot(ua)                         → drop, return 202
         ├─ is_rate_limited(redis, site, ip)   → True → drop, return 202   (non-raising)
         ├─ event_id = uuid4()
         ├─ salt = get_daily_salt(redis)       (in-process cache + SET NX EX)
         ├─ visitor_hash(ip, ua, site_id, salt)
         ├─ geo.lookup(ip)      → (country, region)   [fail-open ("","")]
         ├─ useragent.parse(ua) → (device, browser, os)
         ├─ source = derive(utm_source, referrer, origin)
         └─ XADD stream:events MAXLEN ~ N   { enriched, IP-free row, ts = now UTC }
    → 202 Accepted

workers/batch_writer.py   (`uv run python -m app.workers.batch_writer`)
  XGROUP CREATE stream:events cg (idempotent)
  startup + periodically: XAUTOCLAIM idle-pending → reprocess    (crash recovery)
  loop: XREADGROUP cg COUNT 500 BLOCK 5000 STREAMS stream:events >
        → coerce types (str → UUID/datetime/int) → clickhouse.insert_events(rows) (bulk)
        → XACK only on success
```

---

## 2. Tools & stack (all already chosen in CLAUDE.md §5)

| Concern | Tool |
|---|---|
| API framework | FastAPI |
| Validation | Pydantic v2 |
| Redis (stream, salt, rate limit) | redis-py (async) |
| ClickHouse (analytics store) | clickhouse-connect (async) |
| Background worker | plain module reading a Redis Stream (`uv run python -m ...`) — no Celery |
| Geo-IP enrichment | **geoip2 + MaxMind GeoLite2-City** *(new — see §3; add to CLAUDE.md §5)* |
| UA parsing / bot filter | **zero-dependency regex** (no new lib) |
| Hashing | stdlib `hashlib.sha256` (deterministic — **not** argon2) |
| Tooling / tests | uv, Ruff, pytest + pytest-asyncio, fakeredis, aiosqlite |

---

## 3. Dependencies to install

**One new runtime dependency:**
```bash
cd apps/api
uv add geoip2            # MaxMind GeoLite2 reader (country/region enrichment)
```
Everything else is already declared (`clickhouse-connect[async]`, `redis`, `pydantic`, `httpx`;
dev: `pytest`, `pytest-asyncio`, `fakeredis`, `aiosqlite`).

**MaxMind GeoLite2 database (data file, not a package):** download `GeoLite2-City.mmdb`
(free MaxMind account + license key) and point `GEOIP_DB_PATH` at it. **If the file is absent the
system runs fine** — geo enrichment fails open (`country`/`region` = `""`), so this is not a
blocker for local dev.

**No new JS/tracker dependencies** — Phase 2's wire contract is reused verbatim.

---

## 4. Environment variables to add

Add to both `.env.example` (placeholders) and `app/config.py` (typed settings, dev defaults so
imports never crash), and document in CLAUDE.md §6:

| Variable | Purpose | Dev default |
|---|---|---|
| `VISITOR_SALT_SECRET` | Pepper mixed into the visitor hash (**already in `.env.example`**; add to `config.py`). Must be overridden in prod. | `dev-insecure-visitor-salt` |
| `GEOIP_DB_PATH` | Path to `GeoLite2-City.mmdb`; blank → geo fail-open | *(blank)* |
| `STREAM_MAXLEN` | Approximate cap for `stream:events` (`XADD MAXLEN ~`) | `1000000` |
| `COLLECT_RATE_LIMIT` | Max events per window per `(site_id, IP)` | `600` |
| `COLLECT_RATE_WINDOW` | Rate-limit window (seconds) | `60` |

---

## 5. Key design decisions

- **Enrich on the hot path, buffer IP-free** (privacy: no raw IP at rest).
- **Full enrichment now, fail-open** — device/browser/os via zero-dep regex; country/region via
  GeoLite2; any failure yields `""`, never an error (ingestion must never break).
- **Rate limit** keyed by `(site_id, IP)`, generous configurable ceiling — an **abuse backstop**,
  not precise control (precise control = Phase 6 allowlist + Phase 7 usage caps). It is
  **non-raising**: over-limit hits are dropped silently with **202**, never a 429.
- **Silent drops** — bot hits and over-limit hits both return **202** so the filter isn't detectable.
- **Accept all well-formed `site_id`s** — no Postgres lookup on the hot path (site existence checks
  wait for Phase 6). `/collect` depends on Redis only.
- **Client IP = `X-Forwarded-For` first hop, else `request.client.host`** — correct behind a CDN.
  Known limitation: XFF is spoofable and feeds the hash; prod must trust XFF only from known proxies.
- **`event_id` (UUID) at ingest** — makes at-least-once redelivery dedupe-able; MVP keeps plain
  `MergeTree` (rare duplicates accepted); upgrade path is `ReplacingMergeTree` on `event_id`.
- **Same-site referrer stripping via `Origin`** — `source` = `utm_source` → else external referrer
  host → else `direct` (raw `referrer` still stored for Phase 5).
- **Crash-safe worker** — consumer group + `XAUTOCLAIM` reclaim + `XACK`-after-success; the stream
  is **bounded** with `MAXLEN ~` (`XACK` frees the pending list, not the stream itself).
- **`/collect` CORS is open** (its own `Access-Control-Allow-Origin: *` response header); the global
  dashboard CORS stays locked to `web_base_url` — the two are never merged.

---

## 6. Step-by-step build order

Each step is testable before the next. Steps 2–5, 7, 8 need **no infra** (pure unit / `fakeredis`);
steps 6, 11 and the final smoke need a **live ClickHouse + Redis**.

**Step 1 — Config & dependency scaffolding.**
`uv add geoip2`; add the 5 settings to `config.py`; add the vars to `.env.example`.
_Done when:_ `uv sync` resolves and `from app.config import settings` imports clean.

**Step 2 — `models/events.py` — `CollectEvent`.**
Pydantic model matching the locked wire contract; `extra="ignore"` (stray fields like the dropped
`language` are ignored, not rejected); `screen_w` bounded `0..65535`; UTM fields `str | None = None`.
_Done when:_ a sample payload validates and a payload with a stray field still validates.

**Step 3 — `services/useragent.py`.**
Zero-dep regex `parse(ua) -> (device, browser, os)` and `is_bot(ua) -> bool`.
_Done when:_ unit tests classify sample desktop/mobile/bot user-agents correctly.

**Step 4 — `services/geo.py`.**
`geoip2` reader loaded once from `GEOIP_DB_PATH`; `lookup(ip) -> (country, region)`; fail-open to `("","")`.
_Done when:_ a monkeypatched reader returns a known country and a `None` reader returns `("","")`.

**Step 5 — `services/visitor.py`.**
`visitor_hash(ip, ua, site_id, salt)` = SHA-256 of `pepper + salt + site_id + ip + ua`;
`get_daily_salt(redis)` keyed `salt:{YYYYMMDD}` with in-process cache + atomic `SET NX EX` (24h TTL).
_Done when (fakeredis):_ same inputs → same hash; different day/site → different hash; two concurrent
salt creators converge; **the raw IP never appears in the output**.

**Step 6 — `db/clickhouse.py` — table + helpers.**
`init_events_table()` (idempotent DDL, incl. `event_id`), `insert_events(client, rows)` bulk helper,
`ClickHouseDep` alias, a `--init` `__main__` entry, and a stub query helper for Phase 5.
_Done when (live ClickHouse):_ `uv run python -m app.db.clickhouse --init` then `DESCRIBE events` shows the schema.

**Step 7 — `core/ratelimit.py` — non-raising check.**
`COLLECT_*` constants + `is_rate_limited(redis, site_id, ip) -> bool` on the existing `INCR`+`EXPIRE`
primitive (must **not** raise — that would 429 and break the silent-drop rule).
_Done when (fakeredis):_ returns `False` under the limit, `True` over it.

**Step 8 — `core/exceptions.py`.**
Add `ValidationError(AppError, status_code=422)` for service-layer payload rejection.
_Done when:_ raising it yields a 422 via the existing central handler.

**Step 9 — `services/ingest.py` — orchestrator.**
`ingest_event(event, ip, ua, origin, redis)`: bot filter → rate limit → `event_id=uuid4()` → salt →
`visitor_hash` → `geo.lookup` → `useragent.parse` → `source` derivation → build an **IP-free** row
(`None`→`""`) → `XADD stream:events MAXLEN ~ N`. No HTTP objects; leaves the Phase 4 live-fanout seam.
_Done when (fakeredis):_ enrichment fields populated; `source` rules hold (utm wins / external referrer
host / same-site→`direct`); `event_id` unique; bot & over-limit dropped; **no IP in the stream row**.

**Step 10 — `routers/collect.py` + register in `main.py`.**
Thin handler: raw body → JSON parse (422 on bad) → validate → client IP (XFF|client.host) → `Origin`
→ call ingest → return **202** + `Access-Control-Allow-Origin: *`. Register the router; keep global CORS locked.
_Done when:_ `test_collect.py` passes — valid→202+stream, malformed→422, stray field ignored,
bot→202/no-enqueue, over-limit→202/no-enqueue.

**Step 11 — `workers/batch_writer.py`.**
`XGROUP CREATE` (idempotent); `XAUTOCLAIM` reclaim on startup + periodically; loop `XREADGROUP … >` →
**coerce types** (`event_id`→UUID, `ts`→datetime, `screen_w`→int) → `insert_events` (bulk) → `XACK`
only on success; graceful shutdown.
_Done when:_ `test_batch_writer.py` passes — mock ClickHouse receives the rows and `XACK` runs, plus a
reclaim test (delivered-but-unacked entry is reprocessed). If `fakeredis` lacks `XAUTOCLAIM`, use
`XPENDING`+`XCLAIM` or a real-Redis marker rather than a vacuous pass.

**Step 12 — Docs + full verification.**
CLAUDE.md: add the `geoip2`/Geo-IP row to §5, the new vars to §6, tick the Phase 3 boxes, refresh the
footer. Run `uv run ruff check . && uv run ruff format .` and the full `uv run pytest`. Then the
**mandatory live end-to-end smoke** (see §9) — the only real check on the Redis→ClickHouse type boundary.

---

## 7. Files created / changed

**Created**

| File | Purpose |
|---|---|
| `app/models/events.py` | `CollectEvent` request model (wire contract; `extra="ignore"`; bounded `screen_w`). |
| `app/services/useragent.py` | Regex `parse(ua)` + `is_bot(ua)`. |
| `app/services/geo.py` | GeoLite2 reader + `lookup(ip)`; fail-open. |
| `app/services/visitor.py` | `visitor_hash(...)` + `get_daily_salt(...)`. |
| `app/services/ingest.py` | Ingest orchestrator → `XADD`. |
| `app/routers/collect.py` | Public `POST /collect`, open CORS, 202. |
| `app/workers/batch_writer.py` | Consumer-group drain + reclaim → bulk insert → `XACK`. |
| `tests/test_collect.py` | Endpoint behaviour (202 / 422 / silent drops). |
| `tests/test_visitor.py` | Hash determinism, salt rotation, no-IP-leak. |
| `tests/test_ingest.py` | Enrichment + source derivation + row shape. |
| `tests/test_batch_writer.py` | Bulk insert + `XACK` + reclaim. |

**Changed**

| File | Change |
|---|---|
| `app/db/clickhouse.py` | `init_events_table()`, `insert_events()`, `ClickHouseDep`, `--init`, query stub. |
| `app/main.py` | `include_router(collect.router)`; keep global CORS locked. |
| `app/config.py` | Add the 5 Phase 3 settings. |
| `app/core/ratelimit.py` | `COLLECT_*` constants + non-raising `is_rate_limited(...)`. |
| `app/core/exceptions.py` | `ValidationError(AppError, 422)`. |
| `pyproject.toml` | Add `geoip2`. |
| `.env.example` | Add `GEOIP_DB_PATH`, `STREAM_MAXLEN`, `COLLECT_RATE_LIMIT`, `COLLECT_RATE_WINDOW`. |
| `CLAUDE.md` | §5 Geo-IP row; §6 env vars; tick Phase 3; footer. |

---

## 8. ClickHouse `events` table (DDL)

```sql
CREATE TABLE IF NOT EXISTS events (
    event_id      UUID,                              -- dedupe key / ReplacingMergeTree upgrade path
    site_id       String,
    ts            DateTime64(3, 'UTC') DEFAULT now64(3),
    path          String,
    referrer      String,                            -- raw; `source` derived at ingest
    source        LowCardinality(String),
    utm_source    String,
    utm_medium    String,
    utm_campaign  String,
    country       LowCardinality(String),
    region        String,
    device        LowCardinality(String),
    browser       LowCardinality(String),
    os            LowCardinality(String),
    visitor_hash  String,
    screen_w      UInt16
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (site_id, ts);
```
Empty-string defaults (not `Nullable`) for insert speed; `LowCardinality` on low-distinct columns;
`ORDER BY (site_id, ts)` matches the by-`site_id` access pattern. Per-plan retention TTL is Phase 9.

---

## 9. Verification (end-to-end)

```bash
# 1. Lint + unit tests (no infra needed for the unit suite)
cd apps/api && uv run ruff check . && uv run pytest

# 2. Live smoke — needs Redis + ClickHouse running (CLAUDE.md "Local services").
#    Leave GEOIP_DB_PATH blank to run geo fail-open.
uv run python -m app.db.clickhouse --init                 # create events table
uv run uvicorn app.main:app --reload
curl -X POST http://localhost:8000/collect \
  -H 'Content-Type: text/plain' -H 'Origin: https://demo.example' \
  --data '{"site_id":"demo","path":"/pricing","referrer":"https://google.com","screen_w":1440,"utm_source":"newsletter","utm_medium":null,"utm_campaign":null}'
# expect: HTTP 202
redis-cli XLEN stream:events                              # -> grows by 1 (IP-free enriched row)

# 3. Drain to ClickHouse
uv run python -m app.workers.batch_writer                 # drains + bulk-inserts, then XACK
clickhouse-client -q "SELECT site_id, path, source, country, device, browser, visitor_hash FROM events ORDER BY ts DESC LIMIT 5"
# expect: row present; source='newsletter'; enrichment populated;
#         visitor_hash 64-char hex; event_id present; NO ip column anywhere
```
Also confirm the real tracker path: `pnpm --filter tracker build`, open `apps/tracker/test/index.html`,
watch DevTools → Network for `POST /collect` → 202 with **no OPTIONS preflight**.

---

## 10. Checklist (Phase 3 — mirrors CLAUDE.md)

- [ ] `POST /collect` public, open CORS, returns **202** fast (`routers/collect.py` → `services/ingest.py`).
- [ ] Payload validated via a Pydantic model (`models/events.py`, `extra="ignore"`, bounded `screen_w`).
- [ ] Cookieless visitor ID (`services/visitor.py`): `hash(IP + UA + daily salt)`; salt rotates daily
      (`salt:{YYYYMMDD}`, 24h TTL, `SET NX`); **raw IP never logged.**
- [ ] Bot filtering (`services/useragent.py`), dropped before counting; over-limit dropped — both return 202.
- [ ] Per-`(site_id, IP)` rate limiting (`core/ratelimit.py`, non-raising).
- [ ] Event buffered to `stream:events` (bounded `MAXLEN ~`).
- [ ] Batch writer worker (`workers/batch_writer.py`): drains the stream, **bulk-inserts**, `XACK`s on
      success, **reclaims** stale pending entries.
- [ ] ClickHouse `events` table (`db/clickhouse.py` + `--init`).
- [ ] Tests: bad payload rejected, bot dropped, valid event lands in ClickHouse, no raw-IP leak.

---

## 11. Acceptance criteria (Definition of Done — CLAUDE.md §10)

- [ ] **Speed:** `/collect` returns 202 with **no synchronous ClickHouse write**; Redis-only dep.
- [ ] **Privacy:** `visitor_hash` daily-rotating; **raw IP never logged or stored** (asserted by a test);
      the buffered stream row contains no IP.
- [ ] **Accuracy:** bots filtered before counting; malformed payloads rejected (422); enrichment populated.
- [ ] **Durability:** events buffered to a **bounded** stream; batch writer bulk-inserts, `XACK`s only on
      success, and reclaims pending entries after a crash (at-least-once, no silent loss).
- [ ] **Security/isolation:** `site_id` treated as public (not auth); `/collect` open-CORS while the
      dashboard CORS stays locked; per-`(site,IP)` rate limiting in place.
- [ ] **Quality gates:** `ruff` clean; full `pytest` green; the **live end-to-end smoke passes**
      (beacon → stream → ClickHouse, `event_id` present, no `ip` column anywhere).
- [ ] **Docs:** `geoip2` in CLAUDE.md §5; new env vars in `.env.example` + §6; `VISITOR_SALT_SECRET`
      documented as a prod-override; Phase 3 boxes ticked; footer date refreshed.

---

## 12. Open items (defaults chosen; flip any before or during build)

- **Rate-limit numbers** — default 600/60s per `(site, IP)`; raise if a real site is busier (dropping = undercounting).
- **Duplicates** — default plain `MergeTree` (rare crash-duplicates accepted); switch to `ReplacingMergeTree` now if exactness matters.
- **UA parsing** — default zero-dep regex; upgrade to a maintained lib only if accuracy proves insufficient.
- **Deferred to later phases:** live pub/sub + active-users ZSET (P4), usage metering (P7), per-plan retention TTL/deletion (P9), trust-XFF-only-from-known-proxies hardening.
