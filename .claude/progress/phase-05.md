# Phase 5 — Dashboard metrics (historical) — progress log

**Status:** built. 102 backend tests pass; web lint + tsc + production build green.
No new backend dep, no new env var; one new frontend dep (**recharts**, already
sanctioned in CLAUDE.md §5).

## What shipped

### Backend
- **`services/sites.py` (new)** — `get_owned_site` + `list_account_sites` extracted
  from `services/live.py` so live and stats share one ownership query (§9). `live.py`
  and the Phase 4 tests updated to import from it; behavior-preserving.
- **`db/clickhouse.py::query_rows`** — raw read helper (`client.query(..., parameters=)`
  → column-keyed dicts). No SQL text or business rules here (§3).
- **`services/stats.py` (new)** — two layers:
  - Pure `build_*` builders returning `(sql, params)`. Every user value is a
    clickhouse-connect **server-side parameter** (`{site_id:String}`, `{from:DateTime}`,
    `{limit:UInt32}`); the only SQL-interpolated values are allowlisted internal
    identifiers (bucket fn, audience column) and the integer session-timeout literal.
  - Service fns run a builder via `query_rows` and shape results: bounce ratio +
    avg-duration arithmetic, prior-period `change_pct` (null vs a zero baseline),
    and Python-side zero-fill of time-series gaps.
  - **Sessionization (`_SESSIONIZED_CTE`)** — no `session` column exists, so sessions
    are derived: `lagInFrame(ts)` per `visitor_hash`, a gap > 1800s (or the first
    event) starts a session, a running `sum(is_start)` numbers them. Shared by
    overview (bounce/duration), entry pages (`is_start`), and exit pages (`argMax`).
- **`routers/stats.py` (new)** — `/stats/{overview,timeseries,sources,audience,pages}`,
  each depending on `owned_site` which verifies ownership and raises **404 before any
  ClickHouse query**. `stats_range` parses/validates `from`/`to` (default last 7d, UTC,
  `from<to`, ≤ `MAX_RANGE_DAYS`). `NotFoundError` (404) added to `core/exceptions.py`.
  Registered in `main.py` among the authed routers.

### Frontend
- **`hooks/useStats.ts`** — TanStack Query wrappers (`useOverview/useTimeseries/
  useSources/useAudience/usePages`), keyed by endpoint + siteId + range (+ variant),
  `enabled` on a selected site.
- **`components/stats.tsx`** — formatters (counts / `m:ss` duration / `%`), metric
  cards with compare badges (bounce inverted — lower is better), a Recharts line chart
  (visitors + pageviews), and sources / audience / pages / UTM tables with empty states.
- **`app/(dashboard)/dashboard/page.tsx`** — replaces the placeholder: site picker,
  24h/7d/30d presets (window frozen per preset to avoid query-key churn), audience +
  pages tabs, all sections. Inherits the `(dashboard)` auth guard.

## Tests
- `test_stats_builders.py` — SQL shape + params: site_id bound not interpolated,
  timeout literal + `lagInFrame` present, limit clamped, entry=`is_start`, exit=`argMax`.
- `test_stats_service.py` — `MockClickHouse` canned rows: bounce/duration math, compare
  deltas (incl. null-vs-zero), time-series zero-fill, dimension/kind guards.
- `test_stats_router.py` — owned site → 200; **foreign/unknown site → 404 with the
  ClickHouse mock never called**; unauth → 401; inverted range → 422.

## Known tradeoffs / deferred (see plan open items)
- **O3** — daily `visitor_hash` rotation over-counts multi-day unique visitors
  (inherent to the cookieless model; documented, not "fixed").
- **O2** — per-plan retention enforcement is Phase 9; the range cap is a cost guard only.
- Time-series intervals are hour/day (auto-picked); week/month buckets deferred.
- Sessionization scans the range per query — fine at MVP volume; materialize later if hot.

## Verify manually
Init ClickHouse (`uv run python -m app.db.clickhouse --init`), seed events via the tracker
harness with the batch writer running, then sign in → `/dashboard`: metric cards + chart +
tables populate, range presets refetch, and `?site_id=<not-yours>` → 404.
