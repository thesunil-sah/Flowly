# Flowly — Phase 6 Implementation Plan (Final)

## Site onboarding

Planning-only deliverable. This revision folds in the review fixes (see **Review fixes** below).

---

## Short description

Phases 1–5 built auth, the tracker, ingestion, live traffic, and historical dashboards — but every
`sites` row so far has been hand-seeded. Phase 6 delivers the **self-serve onboarding loop**: a user
adds their site → gets a public `site_id` and a ready-to-paste install snippet → and watches a live
status flip **"Waiting" → "Connected"** the moment the first pageview arrives. No schema change, no
migration. It also relocates the read-only `GET /sites` that Phase 4 borrowed into its permanent home.

**Verification is a stateless hybrid:** check the Redis active-set first (instant, sub-second after
the first event) and fall back to a ClickHouse existence query (durable, survives the 5-min Redis
window) — no `first_event_at` column needed.

---

## Review fixes folded into this revision (read first)

These are the issues that would pass a naive test and break on real input — addressed at the point
they matter in the steps below.

- **F1 (🔴) — `normalize_host` must stay non-raising.** `ingest._host()` is deliberately fail-open
  (returns `""`, never raises) because `/collect` must never fail (§9). The shared helper keeps that
  contract: **pure normalization, returns `""`/`None`, never raises.** `create_site` — not the helper —
  raises `ValidationError` when the normalized domain is empty.
- **F2 (🔴) — bare-domain input breaks `urlparse`.** Users type `example.com` (no scheme), and
  `urlparse("example.com").netloc == ""`. A straight extraction of `_host` returns `""` for the most
  common input. `normalize_host` must handle scheme-less input (prepend `//` before parsing, or fall
  back to `.path` when `.netloc` is empty) **and stay green against the Phase 3 ingest tests** (which
  pass full URLs). Tests must cover `"EXAMPLE.com/"`, `"https://www.example.com"`, `"example.com:8080"`
  → all `example.com`.
- **F3 (🟡) — ownership dependency: query-param vs path-param.** The Phase 5 `owned_site`
  (`stats.py:33-42`) reads `site_id` from the **query string**. `/sites/{site_id}/status` has it in the
  **path**. Add a path-param variant and hoist a shared dependency (small `core/deps.py` or in
  `services/sites.py`) rather than reimplementing the pattern per router.
- **F4 (🟡) — duplicate-domain is a pre-check only.** Only `site_id` is `UNIQUE`; there is no
  `(account_id, domain)` constraint and (per D10) no migration, so "catch `IntegrityError`" for a
  domain dup can never fire. Rely on an account-scoped pre-check; accept the tiny double-submit race.
  Drop the misleading "or catch IntegrityError".
- **F5 (✅ verified) — reuse the existing fake-Redis fixture.** `fakeredis.aioredis.FakeRedis` is
  already a dep and already the conftest fixture — `conftest.py:59` overrides `get_redis` with a shared
  `FakeRedis(decode_responses=True)`, wired via the `client` fixture. Sites router tests reuse that
  `client` fixture (fake Redis for free) + a `MockClickHouse` override exactly like
  `test_stats_router.py`. No new test dep.

---

## Tools & stack (all already in CLAUDE.md §5 — no new dependency, no new env var)

| Concern | Tool |
|---|---|
| Endpoints | FastAPI (thin routers → `services/sites.py`) |
| `site_id` generation | stdlib `secrets.token_hex(8)` (matches `visitor.py` / `oauth.py` precedent) |
| Ownership | SQLAlchemy async — the shared `get_owned_site` (already in `services/sites.py`) |
| Durable verify | `clickhouse-connect` existence query via `db/clickhouse.query_rows` (server-parameterized) |
| Instant verify | Redis active-set via `services/live.count_active` |
| Validation | Pydantic v2 models in `models/schemas.py` |
| Frontend data | TanStack Query (`hooks/useSites.ts`) |
| Styling | Tailwind (match `components/stats.tsx` / `form.tsx`) |
| Tests | pytest + `MockClickHouse` + the **existing** Redis test fixture (F5); frontend lint/tsc/build parity with Phase 5 |

`TRACKER_SCRIPT_URL` already exists in `.env.example` and CLAUDE.md — Phase 6 just wires it into
`Settings` (currently dropped by `extra="ignore"`). **No `.env.example` change.**

---

## Locked decisions

- **D1 — Server builds the snippet (single source of truth for the URL).** `config.py` adds
  `tracker_script_url: str = "http://localhost:8000/script.js"  # TRACKER_SCRIPT_URL`. The API returns
  the full snippet; the frontend never needs a `NEXT_PUBLIC_*` copy.
- **D2 — One canonical `SiteOut` constructor; `snippet` is always explicit.** `SiteOut` gains a
  **required** `snippet: str`. **Never** build it via `model_validate(site_orm)` (the ORM has no
  `snippet` attr). Add one helper — `to_site_out(site: Site) -> SiteOut` — returning
  `SiteOut(id=site.id, site_id=site.site_id, domain=site.domain, snippet=build_snippet(site.site_id))`.
  List maps it over rows; create/detail call it on one → no "works in list, breaks in create" drift.
- **D3 — `normalize_host` is a shared, non-raising helper (see F1/F2).** Factor host derivation out of
  `ingest._host()` into `core/urls.py::normalize_host(raw) -> str` (lowercase, strip scheme/path, drop
  port + leading `www.`, **handle scheme-less input**). Both `ingest.py` and `sites.py` import it. This
  guarantees the domain a user registers matches the host ingestion derives. The helper never raises;
  `create_site` raises `ValidationError` on an empty result.
- **D4 — `site_id`: `secrets.token_hex(8)` (16 hex chars), collision-safe.** URL/HTML/Redis-key safe
  (no `-_/+`), fits `String(64)`. A bounded 3-try retry handles the astronomically rare collision;
  **the `sites.site_id` `UNIQUE` index (confirmed at `tables.py:71`) is the real guarantee**, the loop
  is belt-and-suspenders.
- **D5 — Verification is a stateless hybrid with a polling stop condition.**
  `first_event_seen(redis, ch_client, site_id) -> bool`: (a) `live.count_active(...) > 0` → instant
  True (note: `count_active` also evicts stale members — a mutating "read", harmless here); (b) else
  ClickHouse `SELECT 1 FROM events WHERE site_id = {site_id:String} LIMIT 1` — durable, index-aligned,
  server-parameterized (never string-format `site_id`, §9). **Frontend:** `useSiteStatus` polls every
  ~3–5 s but **stops on `connected`** *and* **after a ~3-min cap**, then shows a "Still waiting?
  Re-check" button. Prevents an abandoned tab from polling ClickHouse indefinitely.
- **D6 — `domain` is cosmetic, not enforced.** A human-readable dashboard label. Events are scoped
  **only** by `site_id`; the tracker fires wherever the snippet is pasted. **Deferred (not built):** an
  ingest-time `Origin`-vs-registered-domain check.
- **D7 — Duplicate-domain check is account-scoped, pre-check only (see F4).** Two accounts may track
  the same domain; the same account may not register it twice. Account-scoped query before insert →
  `ConflictError` (409). Small double-submit race accepted (no composite DB constraint, no migration).
- **D8 — Relocate `GET /sites` into its permanent router.** Phase 4 borrowed it in `live.py`; move it
  to `routers/sites.py`. Keep `live.py`'s `sites` import for `_authorize`. **Re-run the Phase 4 WS
  suite** after the move.
- **D9 — Ownership before any query (§9).** `GET /sites/{id}` and `/status` use a shared
  path-param ownership dependency (F3) → **404** on miss (never 403; never reveal a foreign site),
  *before* touching Redis/ClickHouse.
- **D10 — No new column, no migration; `first_event_at` deliberately not persisted.** The hybrid check
  needs no stored state. Tradeoff accepted: no "connected since" / silent-site detection.

---

## What already exists (reuse — do not rebuild)

- `services/sites.py` — `get_owned_site` / `list_account_sites` (Phase 5). Extend with
  create/generate/snippet/verify.
- `services/live.py::count_active` — the instant verification path.
- `db/clickhouse.py::query_rows` — the durable existence query (add a small builder, mirroring `stats.build_*`).
- `services/ingest.py::_host()` — the host logic to **extract into `core/urls.py`** (D3/F1/F2).
- `core/security.py::CurrentUser`; `core/exceptions.py` (`NotFoundError`/`ConflictError`/`ValidationError`, wired).
- `models/schemas.py::SiteOut` (`id`/`site_id`/`domain`) + the `_normalize_*` validator pattern.
- Frontend: `hooks/useSites.ts`, `lib/api.ts::apiFetch`, `(dashboard)/layout.tsx` guard,
  `components/stats.tsx`/`form.tsx`, the `Tabs` pattern in `dashboard/page.tsx`, the sign-up two-step
  `"form" | "code"` pattern.

---

## Step-by-step build order (each step testable before the next)

### Step 1 — `core/urls.py::normalize_host` (shared, non-raising) — D3 / F1 / F2
Extract host logic from `ingest._host()` into `core/urls.py`; enhance it to handle scheme-less input
(prepend `//` or fall back to `.path` when `.netloc` is empty). Keep it **non-raising** (returns `""`).
Update `ingest.py` to import it. **Run the Phase 3 ingest tests** (behavior-preserving for URL inputs)
**plus** new cases: `"example.com"`, `"EXAMPLE.com/"`, `"https://www.example.com"`, `"example.com:8080"`
→ all `example.com`.
**Done:** ingest suite green; one canonical, bare-domain-safe host normalizer.

### Step 2 — `config.py`: expose the tracker URL — D1
Add `tracker_script_url` to `Settings` (dev default as above). No `.env.example` change.

### Step 3 — `services/sites.py`: create + generate + snippet + verify
- `_generate_site_id()` → `secrets.token_hex(8)`.
- `create_site(session, account_id, domain)` → `normalize_host` the domain; **raise `ValidationError`
  if empty** (F1); account-scoped dup pre-check (D7/F4 → `ConflictError`); generate `site_id` with
  3-try collision retry (D4); insert; commit; return.
- `first_event_seen(redis, ch_client, site_id)` → Redis-first, ClickHouse-fallback (D5); add the
  parameterized existence builder.
- `build_snippet(site_id)` → `<script defer src="{tracker_script_url}" data-site="{site_id}"></script>`.
**Done:** service tests (below) green.

### Step 4 — `models/schemas.py`: request/response shapes — D2
- `SiteCreate { domain: str }` with a `field_validator` calling `normalize_host` (mirrors
  `_normalize_email`), length-bound 255. (Empty-after-normalize is caught in `create_site`, not here,
  to keep one error path — F1.)
- `SiteOut` gains **required** `snippet: str`; add the `to_site_out(site) -> SiteOut` constructor (D2).
- `SiteStatus { connected: bool }`.

### Step 5 — Shared ownership dependency + `routers/sites.py` (new) — D8 / D9 / F3
Add a **path-param** ownership dependency (`require_owned_site`) in a shared spot (e.g. `core/deps.py`
or `services/sites.py`); keep the existing query-param `owned_site` for stats. Then
`APIRouter(prefix="/sites", tags=["sites"])`:
- `GET /sites` → `list[SiteOut]` (via `to_site_out`) — **moved from `live.py`**.
- `POST /sites` (201) → `SiteOut` — parse `SiteCreate`, `create_site`, return `to_site_out`.
- `GET /sites/{site_id}` → `SiteOut` — path-param ownership gate. *(Keep only if deep-linking to a
  site is supported; the `POST` response already carries the snippet.)*
- `GET /sites/{site_id}/status` → `SiteStatus` — ownership gate, then `first_event_seen`
  (`RedisDep` + `ClickHouseDep`).
**Done:** router tests — ownership 404 *before* any Redis/CH call; 401 unauth; happy paths.

### Step 6 — `routers/live.py`: remove the borrowed `GET /sites` — D8
Delete `list_sites` + now-unused `SiteOut` import; keep the `sites` import for `_authorize`.
**Run the Phase 4 WS tests** — the live ownership check must still pass.

### Step 7 — `main.py`: register the router
Add `sites` to the router import + `app.include_router(sites.router)` among the authed routers.

### Step 8 — Frontend types + hooks — D5
- `lib/api.ts`: extend `Site` with `snippet: string`; add `SiteStatus = { connected: boolean }`.
- `hooks/useSites.ts`: `useCreateSite()` (mutation → `POST /sites`, invalidates `["sites"]`);
  `useSiteStatus(siteId, enabled)` — `refetchInterval` returns `false` when `connected` or after the
  ~3-min cap (D5), exposing a `recheck()` for the manual button.

### Step 9 — `app/(dashboard)/sites/page.tsx` (new)
Two-step flow (sign-up `"form" | "code"` pattern), auth-guarded by the existing layout:
1. **Add domain** — `Field(domain)` + submit via `useCreateSite`, `ErrorText` on failure.
2. **Install** — snippet in a copy box **with the status pill right beside it** (the "it worked!"
   moment must be co-located), plus `<InstallGuide>` and the `useSiteStatus`-driven
   "Waiting… → Connected ✓" flip with the re-check button on timeout.

### Step 10 — `components/install.tsx` (new)
Named exports, `"use client"`, Tailwind monochrome (match `components/stats.tsx`):
- `SnippetBox({ snippet })` — `<pre>` + copy-to-clipboard.
- `InstallGuide({ snippet })` — `Tabs` over Universal / Next.js / WordPress / Shopify / Webflow / GTM,
  each = snippet + 2–3 lines of where-to-paste.
- `StatusPill({ connected })` — waiting / connected states.

### Step 11 — Wire "Add site" CTAs
- Empty states in `dashboard/page.tsx` and `live/page.tsx` → add `<Link href="/sites">Add a site</Link>`.
- A small "Add site" link near the site picker in the dashboard header.
- If `ENVIRONMENT != "local"` and `tracker_script_url` still points at localhost, warn on the install
  screen (O3).

### Step 12 — Docs + verification
Tick CLAUDE.md Phase 6 boxes + refresh the footer (note: `routers/sites.py` new, `GET /sites` moved,
`core/urls.py` extraction, hybrid verification, `domain` cosmetic). Run `ruff` + full `pytest`;
`pnpm --filter web lint && tsc --noEmit && build`.

---

## Critical rules to uphold (§9)

- **Ownership before any query** — `/sites/{id}` and `/status` gate on the path-param ownership dep →
  404, never 403, never confirm a foreign site exists.
- **`site_id` is public, not a secret** — fine in HTML; never used for auth.
- **No PII / no raw IP** — verification reads only counts/existence, never visitor data.
- **ClickHouse SQL server-parameterized** — the existence query binds `{site_id:String}`.
- **`/collect` never fails** — `normalize_host` stays non-raising so the extraction can't break
  ingestion (F1).
- **`/collect` and dashboard CORS stay separate** — no CORS changes this phase.

---

## Tests

**Backend** (`tests/test_sites.py`, existing style; `MockClickHouse` + the existing Redis fixture — F5):
- `normalize_host`: bare/scheme/www/port cases all → canonical host; empty/junk → `""` (never raises). (F2)
- `create_site` generates a valid `site_id` and stores the **normalized** domain; empty-after-normalize → 422. (F1)
- Duplicate domain, **same** account → 409; same domain, **different** account → allowed. (D7)
- `POST /sites` without a token → 401.
- `GET /sites/{id}/status`: owned → 200 `{connected}`; foreign/unknown → **404 before Redis/ClickHouse
  is touched** (assert no calls, like `test_stats_router.py:88`). (D9)
- `first_event_seen`: Redis-active True short-circuits (no CH call); Redis empty → CH fallback; both empty → False. (D5)
- Snippet contains the `site_id` and the configured tracker URL; `to_site_out` yields identical shape
  from list and single paths. (D2)
- **Regression:** Phase 4 `test_live_ws.py` / `test_live.py` still pass after the `GET /sites` move. (D8)

**Frontend:** `pnpm --filter web lint` + `tsc --noEmit` + `build` green (Phase 5 parity).

---

## Verification (end-to-end, manual)

1. `alembic upgrade head` (no new migration); Postgres/Redis/ClickHouse running; `uv run uvicorn app.main:app --reload`.
2. `uv run pytest` — all green (existing 102 + new sites tests).
3. `pnpm --filter web dev`; sign in → `/sites` → add a **bare** domain (`example.com`) → confirm it
   normalizes, and a `site_id` + snippet render.
4. Drop the snippet on a local page (or `apps/tracker/test/index.html` with the new `site_id`), load it
   → the pill flips **Waiting → Connected** within seconds (Redis path) and **stays connected after
   5 min** (ClickHouse path).
5. Leave the install tab open **without** loading the site → polling stops after ~3 min and shows the
   re-check button. (D5)
6. A second account cannot fetch `/sites/{id}/status` for the first account's site → **404**. (D9)
7. `ruff` / web lint / build all green.

---

## Definition of done (CLAUDE.md §10)

- [ ] User can add a site → gets a `site_id` + copy-paste snippet; snippet built server-side from `tracker_script_url`.
- [ ] Install screen shows the snippet **with the status pill beside it**; pill flips Waiting → Connected via the Redis-first / ClickHouse-fallback hybrid.
- [ ] `SiteOut.snippet` built via one canonical `to_site_out` constructor — identical in list and create paths. (D2)
- [ ] `normalize_host` lives once in `core/urls.py`, is **non-raising**, and handles **bare-domain** input; `ingest.py` and `sites.py` both import it; ingest tests still green. (F1/F2)
- [ ] Path-param ownership dependency used by `/sites/{id}*` → 404 before any Redis/CH query; unauth → 401. (F3/D9)
- [ ] Duplicate domain scoped by account (409, pre-check); different account allowed; no `IntegrityError` path claimed. (F4/D7)
- [ ] Status polling stops on `connected` and after a ~3-min timeout (+ manual re-check). (D5)
- [ ] `domain` documented as cosmetic (not origin-enforced). (D6)
- [ ] Existence query server-parameterized; `site_id` UNIQUE index confirmed backing the retry. (D4)
- [ ] `GET /sites` moved out of `live.py`; Phase 4 WS tests still green. (D8)
- [ ] Redis tests reuse the existing fixture (no new test dep). (F5)
- [ ] No new migration, no new env var; Phase 6 boxes ticked + footer refreshed; lint + full suite green.

---

## Out of scope / open items

- **Out of scope:** per-plan retention + usage limits (Phase 7/9), deep screenshot platform guides
  (kept lean), site editing/deletion (add only if asked), persisting `first_event_at` (D10).
- **O1 — `domain` authoritative (D6).** Deferred ingest-time `Origin`-vs-registered-domain check.
- **O2 — "Connected since" / silent-site detection (D10).** Needs a persisted `first_event_at` column.
- **O3 — Snippet URL in production.** `tracker_script_url` defaults to localhost; set the real CDN/host
  value in prod, and warn on the install screen if it's still localhost outside `local` (Step 11).
