# FLOWLY — PHASE 5 IMPLEMENTATION PLAN (FINAL)

## Dashboard metrics (historical)

> Planning-only deliverable — **no code is written in this task.**

---

## Short description

Phase 5 builds the **core reports a user logs in to see**: an overview (visitors, sessions,
pageviews, bounce rate, avg. duration) with period-over-period comparison, a time-series chart,
and breakdowns for **sources + UTM**, **audience** (geo / device / browser / os), and
**pages** (top / entry / exit). Everything reads from the ClickHouse `events` table populated in
Phase 3, filtered by `site_id` **and** ownership-verified against the authenticated account
(CLAUDE.md §9 — the #1 multi-tenant leak path). The live path (Phase 4) is untouched: **historical
reads never touch Redis; the live counter never touches ClickHouse.**

The central design fact: **there is no `session` column.** Sessions, bounce, and duration are
**derived at query time** from `visitor_hash` + `ts` gaps (30-min timeout, per the glossary).

---

## Tools & stack (all already in CLAUDE.md §5 — **one new frontend dep**, no new env var)

| Concern | Tool |
|---|---|
| Stats endpoints | FastAPI (thin routers → `services/stats.py`) |
| Query execution | `clickhouse-connect` async client (existing `db/clickhouse.py`) |
| Query safety | clickhouse-connect **server-side parameters** (`{site_id:String}`, `{from:DateTime}`) — never f-string user input |
| Ownership check | SQLAlchemy 2.0 async — reuse the Phase 4 `get_owned_site` (hoisted to `services/sites.py`, see D1) |
| Validation | Pydantic v2 request/response models in `models/schemas.py` |
| Frontend data | TanStack Query hooks in `hooks/` |
| Charts | **Recharts** — **`pnpm add recharts --filter web`** (named in §5; not yet installed) |
| Styling | Tailwind (match `components/live.tsx`, `components/form.tsx`) |
| Tests | pytest + a `MockClickHouse` (mirror `tests/test_batch_writer.py`) + pure query-builder unit tests |

No new backend dependency, no new env var. Recharts is the only new install and it is already the
sanctioned chart library in §5.

---

## Locked decisions

- **D1 — Hoist the ownership check into `services/sites.py`.** Phase 4 left `get_owned_site` /
  `list_account_sites` in `services/live.py`; Phase 5 is the second consumer, so move both into a
  shared `services/sites.py` and have `live.py` and `stats` import from there. One canonical
  ownership query, reused by every authed surface. (Closes the review's 🟡 item.)
- **D2 — Ownership is enforced in the router, before any ClickHouse query.** A shared
  `require_owned_site(site_id, account, session) -> Site` dependency/helper runs the Postgres
  ownership lookup and raises `AppError` (404/403) on miss. **No `/stats/*` handler ever passes an
  unverified `site_id` to `services/stats.py`.** Filtering ClickHouse by `site_id` alone is *not*
  ownership.
- **D3 — All ClickHouse queries are server-parameterized.** `site_id`, `path`, date bounds, limits
  go through clickhouse-connect `parameters=`. No user value is ever string-formatted into SQL
  (injection guard, §9). `db/clickhouse.py` gains a read helper `query_rows(client, sql, params)`;
  **no business rules there** (§3) — `services/stats.py` owns the SQL text.
- **D4 — Query-builders are pure; the service runs them.** Each metric has a builder returning
  `(sql: str, params: dict)`. Builders are pure and unit-testable with **no DB**. `services/stats.py`
  composes builder + `query_rows` + shaping into a Pydantic response. This is what makes the SQL
  testable without a live ClickHouse (D14).
- **D5 — Sessionization is derived in SQL via a 30-min gap.** `SESSION_TIMEOUT_SECONDS = 1800`
  (module constant). Within `PARTITION BY visitor_hash ORDER BY ts`, an event **starts a new
  session** when `ts - lagInFrame(ts) OVER w > 1800` **or** it is the visitor's first event in the
  range. `sessions = sum(is_session_start)`. This is a CTE/subquery reused by overview, bounce,
  duration, and entry/exit pages.
- **D6 — Metric definitions (documented, cookieless-honest):**
  - **pageviews** = `count(*)`.
  - **visitors** = `uniqExact(visitor_hash)`. **Caveat:** `visitor_hash` rotates daily (§2), so a
    visitor active across N days counts up to N times over a multi-day range. This is inherent to the
    cookieless design (same tradeoff Plausible makes); document it in the response/UI, don't "fix" it.
  - **sessions** = count of session-starts (D5).
  - **bounce rate** = `sessions with exactly 1 pageview / total sessions` (rounded, §4).
  - **avg. duration** = mean over sessions of `(last ts − first ts)` within the session (0 for
    single-pageview sessions).
- **D7 — Comparison = immediately-preceding equal-length window.** `overview` accepts an optional
  `compare=previous`; when set, it runs each metric for `[from, to]` and for the prior window of the
  same length `[from − (to−from), from]`, returning `{value, previous, change_pct}` per metric.
  `change_pct` rounded; `null` when previous is 0 (avoid divide-by-zero / infinity).
- **D8 — Time bucketing is chosen from range length, not hardcoded.** `timeseries` picks
  `toStartOfHour` (≤ 2 days), `toStartOfDay` (≤ ~90 days), else `toStartOfWeek`/`toStartOfMonth`;
  or accept an explicit `interval` param, validated against an allowlist. **Zero-fill gaps** so the
  chart has a continuous x-axis (ClickHouse `WITH FILL` on the bucket, stepped by the interval).
- **D9 — Endpoint set (lean, dimension-parameterized where semantics allow):**
  - `GET /stats/overview` — the metric cards (+ optional compare).
  - `GET /stats/timeseries` — one metric over time (default pageviews).
  - `GET /stats/sources` — grouped by `source`, plus a UTM breakdown (`utm_source/medium/campaign`).
  - `GET /stats/audience` — `dimension ∈ {country, device, browser, os}` (allowlisted), grouped
    count. One handler, four dimensions — avoids four near-identical endpoints.
  - `GET /stats/pages` — `kind ∈ {top, entry, exit}`. `top` = pageviews by path; `entry` = first
    path per session; `exit` = last path per session (both use the D5 session frame).
- **D10 — Shared query params, validated at the boundary.** A `StatsQuery` model: `site_id: str`,
  `from_: datetime`, `to: datetime` (aliased `from`/`to`), with validators: `from < to`, both UTC,
  and a **max span cap** (e.g. 372 days) to bound query cost. Default range = last 7 days when
  omitted. Breakdown endpoints add `limit` (default 10, capped e.g. 100). All times **UTC in, UTC
  in the query**; the frontend converts to local only at display (§4).
- **D11 — Read-only, no ClickHouse writes, no Redis.** Phase 5 only issues `SELECT`s. It does **not**
  add columns, does **not** change ingestion, and does **not** read `active:{site_id}` (that's the
  live counter's job). If a report needs "online now," it links to `/live`, it does not re-implement it.
- **D12 — Retention is not enforced here.** Per-plan retention deletion is Phase 9. Phase 5 queries
  whatever ClickHouse holds; the span cap (D10) is a cost guard, not a plan limit. (Open item O2.)
- **D13 — Frontend: URL-driven date range, one shared query key.** The `(dashboard)/dashboard` page
  owns range state (`from`/`to` + preset: 24h / 7d / 30d / custom) and the selected site; hooks key
  on `["stats", kind, siteId, from, to, compare]` so range/site changes refetch and cache cleanly.
  Reuse `useSites()` (Phase 4) for the site picker.
- **D14 — Testing without a live ClickHouse.** (a) **Builder unit tests** assert the `(sql, params)`
  a builder produces (site_id in params not SQL; correct bucket fn; session-gap literal). (b)
  **Service tests** inject a `MockClickHouse` (mirroring `tests/test_batch_writer.py::MockClickHouse`)
  that returns canned result rows, asserting the service shapes them correctly (bounce math, compare
  deltas, zero-fill). (c) **Router tests** (TestClient) assert **ownership**: a `site_id` the caller
  doesn't own → 404/403 **before** any query; unauthenticated → 401. An **optional**
  integration test behind a marker can run against a real ClickHouse in CI later.

---

## What already exists (reuse — do not rebuild)

- `db/clickhouse.py` — async client (`get_clickhouse` / `ClickHouseDep`), `EVENT_COLUMNS`, the
  `events` DDL. **Add only** a `query_rows` read helper here (raw execution, no business rules).
- `events` table schema (the exact fields available to every query):
  `event_id, site_id, ts (DateTime64(3,'UTC')), path, referrer, source, utm_source, utm_medium,
  utm_campaign, country, region, device, browser, os, visitor_hash, screen_w`. Ordered by
  `(site_id, ts)`, partitioned by `toYYYYMM(ts)` — so `site_id` + `ts`-range filters hit the
  primary key and partition pruning. **No `session`, no `path`-title, no raw IP** (privacy).
- `services/live.py::get_owned_site` / `list_account_sites` — **move to `services/sites.py`** (D1),
  keep signatures.
- `core/security.py::CurrentUser` (`require_user`) — the authed dependency for every `/stats/*` route.
- `core/exceptions.py::AppError` + `register_exception_handlers` — raise typed errors in the service/
  helper; the central handler maps them to HTTP (no scattered `HTTPException`, §4).
- `models/schemas.py::SiteOut` + `db/postgres.py::get_session` / `async_session_factory`.
- `main.py::create_app` — dashboard-locked CORS; register the new `stats.router` among the authed
  routers.
- Frontend: `hooks/useSites.ts`, `lib/api.ts::apiFetch`, `(dashboard)/layout.tsx` auth guard,
  `components/live.tsx` / `form.tsx` Tailwind conventions, TanStack Query setup.

---

## Step-by-step build order (each step testable before the next)

### Step 1 — `services/sites.py` (extract shared ownership) — D1
- Move `get_owned_site(session, site_id, account_id) -> Site | None` and
  `list_account_sites(session, account_id)` out of `services/live.py` into `services/sites.py`.
- Update `routers/live.py` to import from `services.sites`. **Run the Phase 4 suite green** to prove
  the move is behavior-preserving before adding anything new.
**Done:** existing 80 tests still pass; one canonical ownership query.

### Step 2 — `db/clickhouse.py::query_rows` (read helper) — D3
- `async query_rows(client, sql, params) -> list[dict]` (or column-named rows) wrapping
  `client.query(..., parameters=params)`. Raw execution only, no SQL text, no shaping.
**Done:** unit-callable with `MockClickHouse`.

### Step 3 — `services/stats.py` — query-builders (pure) — D4/D5/D6/D8
- Constants: `SESSION_TIMEOUT_SECONDS = 1800`, `DEFAULT_LIMIT`, `MAX_LIMIT`, `MAX_RANGE_DAYS`,
  interval allowlist.
- A private `_session_cte(...)` producing the sessionized subquery (D5), reused below.
- Pure builders, each `-> (sql, params)`:
  `build_overview`, `build_timeseries(metric, interval)`, `build_sources`, `build_utm`,
  `build_audience(dimension)`, `build_pages(kind)`. Every user value goes in `params` (D3);
  `dimension`/`kind`/`interval`/`metric` are **allowlisted** (mapped to fixed column/fn names, never
  interpolated raw).
**Done:** builder unit tests assert SQL shape + params (D14a).

### Step 4 — `services/stats.py` — service functions
- For each report: call the builder, `query_rows`, shape into the response model. `overview` also
  runs the previous-window pass and computes `change_pct` (D7). Bounce/duration math and zero-fill
  (D8) live here (business logic, §3), not in the router.
**Done:** service tests with `MockClickHouse` (D14b) — bounce ratio, compare deltas, gap-fill.

### Step 5 — `models/schemas.py` — request/response models — D10
- `StatsQuery` (site_id, from/to aliases, validators: `from<to`, UTC, span cap; default last-7d),
  and breakdown extras (`limit`, `dimension`, `kind`, `metric`, `interval`, `compare`).
- Response models: `OverviewOut` (per-metric `{value, previous, change_pct}`), `TimeseriesOut`
  (list of `{bucket, value}`), `BreakdownOut` (list of `{label, visitors, pageviews}`),
  `PagesOut`. Every number rounded/typed (§4).

### Step 6 — `routers/stats.py` (thin) — D2/D9
- `router = APIRouter(prefix="/stats", tags=["stats"])`.
- Shared dependency `require_owned_site(site_id, account: CurrentUser, session) -> Site` (D2) that
  runs `services.sites.get_owned_site` and raises on miss — **every** endpoint depends on it.
- Handlers: `/overview`, `/timeseries`, `/sources`, `/audience`, `/pages` — each parses `StatsQuery`,
  depends on `require_owned_site`, calls the matching `services/stats.py` function, returns the model.
  A handler is a few lines (§3).
**Done:** router tests — ownership rejection **before** query (D14c), unauth → 401, happy path shape.

### Step 7 — Wire `main.py`
- `from app.routers import ... stats`; `app.include_router(stats.router)` among the authed routers
  (dashboard CORS stays locked). No migration (ClickHouse DDL unchanged).

### Step 8 — Frontend deps + query hooks — D13
- `pnpm add recharts --filter web`.
- `hooks/useStats.ts`: TanStack Query wrappers — `useOverview`, `useTimeseries`, `useSources`,
  `useAudience`, `usePages` — over `apiFetch`, keyed by `["stats", kind, siteId, from, to, compare]`.

### Step 9 — Dashboard UI (`app/(dashboard)/dashboard/page.tsx` + components)
- Range control: presets (24h / 7d / 30d) + custom picker; site picker via `useSites()`; state drives
  the hooks. Convert UTC → local only at display (§4).
- Components (named exports, Tailwind, match `components/live.tsx`):
  - `MetricCards` — pageviews / visitors / sessions / bounce / duration, each with the compare delta
    (▲/▼ + rounded %).
  - `TrafficChart` (Recharts) — the time-series, metric toggle.
  - `SourcesTable`, `AudienceTables` (country/device/browser/os), `PagesTable` (top/entry/exit tabs).
- Empty/loading/error states per panel (no data in range → "No traffic in this range", link to
  `/live` and to install if the site has never received an event).

### Step 10 — Tests (`apps/api/tests`)
- `test_stats_builders.py` — pure builder tests (D14a): params carry user values, session-gap literal
  present, bucket fn matches interval, dimension/kind allowlisted.
- `test_stats_service.py` — `MockClickHouse` canned rows (D14b): overview compare math, bounce ratio,
  timeseries zero-fill, entry/exit derivation.
- `test_stats_router.py` — ownership (foreign `site_id` → 404/403 with **no** ClickHouse call),
  unauth → 401, valid → correct shape.
- Confirm the Phase 4 `test_live_ws.py` / `test_live.py` still pass after the D1 move.

### Step 11 — Docs + verification
- Tick CLAUDE.md Phase 5 boxes + refresh the footer note (services/routers added, `services/sites.py`
  extraction, recharts dep, session-derivation + visitor-rotation caveat documented).
- `uv run ruff check . && uv run ruff format .` and full `uv run pytest` green; `pnpm --filter web lint`.

---

## Verification (end-to-end, manual)

1. Postgres + Redis + **ClickHouse** running; `events` table initialized
   (`uv run python -m app.db.clickhouse --init`); no new migration.
2. Seed data: run the Phase 2 tracker harness (or `POST /collect`) against a site you own with the
   batch writer running, so real rows land in ClickHouse across a couple of paths/sources.
3. Run API + `pnpm --filter web dev`; sign in → dashboard, pick the site.
4. Confirm: metric cards populate; changing the range (24h/7d/30d/custom) refetches; the chart buckets
   sensibly and fills gaps; sources/audience/pages tables match the seeded data; the compare delta
   appears and is `null`-safe when the prior window is empty.
5. **Ownership:** hit `/stats/overview?site_id=<not-yours>` → 404/403 with no data leak; drop the
   token → 401.
6. `uv run pytest`, `uv run ruff ...`, and web lint all green.

---

## Definition of done (CLAUDE.md §10)

- [ ] Overview (visitors/sessions/pageviews/bounce/duration) + compare, time-series, sources+UTM,
      audience (geo/device/browser/os), pages (top/entry/exit) all return correct, rounded numbers.
- [ ] **Every** `/stats/*` route verifies **site ownership before any ClickHouse query** (§9);
      unauth → 401. No query filters by `site_id` alone.
- [ ] All ClickHouse SQL is **server-parameterized** — no user value string-formatted into SQL (§9).
- [ ] Sessions/bounce/duration derived in SQL via the 30-min gap; visitor-rotation caveat documented.
- [ ] Routers thin; SQL text + shaping in `services/stats.py`; raw execution in `db/clickhouse.py`
      (§3). Ownership query lives once in `services/sites.py`.
- [ ] Historical reads never touch Redis; live counter untouched.
- [ ] Recharts added to §5's install; no new env var; `.env.example` unchanged.
- [ ] Builder + service (`MockClickHouse`) + router (ownership) tests pass; lint + full suite green;
      Phase 5 boxes ticked + footer refreshed.

---

## Out of scope / open items

- **Out of scope:** add-site onboarding + install verification (Phase 6 — Phase 5 reuses the
  read-only `GET /sites`), billing/usage metering (Phase 7), retention-deletion job (Phase 9), CSV
  export (Phase 9), custom events/segments/funnels (Phase 10).
- **O1 — Sessionization cost.** The gap-based window function scans the range per query. Fine at MVP
  volume; if it becomes hot, consider a materialized per-session rollup (ClickHouse
  `AggregatingMergeTree`) later — do not pre-optimize now.
- **O2 — Retention vs. range cap.** The `MAX_RANGE_DAYS` cap (D10) is a cost guard, not a plan limit.
  Per-plan retention enforcement (and clamping the selectable range to it) is Phase 9; wire the UI cap
  to the plan then.
- **O3 — Unique-visitor accuracy (D6).** Daily `visitor_hash` rotation over-counts multi-day
  visitors. Documented as an accepted cookieless tradeoff; a longer-lived-but-still-anonymous scheme
  would change the privacy model (§9) and is deliberately not attempted here.
- **O4 — Interval/timezone display.** Buckets are computed in UTC; the frontend localizes at display.
  A per-account display-timezone setting (so "today" matches the user's day boundary) can come with
  account settings later — note it if bounce/day-boundary questions arise.
- **O5 — `uniqExact` vs `uniq`.** Start with exact counts for correctness at MVP scale; switch to the
  approximate `uniq`/HLL only if visitor cardinality makes exact counts slow.
```
