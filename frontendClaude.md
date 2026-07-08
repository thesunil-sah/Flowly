# CLAUDE.md

> Single source of truth for how **Flowly** is built. Read this fully before working in the repo.
> If anything here becomes wrong or outdated, update it as part of your change.

---

## How Claude should work in this repo

1. **Read this file first.** It overrides any default assumptions about stack, structure, or conventions.
2. **Plan before coding.** State the approach and which files you'll touch before writing code.
3. **Respect the layering:** `routers -> services -> db`. Never put business logic in a router or a query in a service's caller.
4. **Stay within the chosen tools** (section 5). Don't add a new library without updating that section in the same change.
5. **Before calling a task done:** run lint + tests (section 7) and confirm they pass. See *Definition of done* (section 10).
6. **Never commit secrets and never log PII or credentials** (raw IPs, emails, passwords, tokens). See *Critical rules* (section 9).
7. **Explain destructive or schema-changing actions** (migrations, data deletion, bulk updates) before running them.
8. **Keep changes small** and scoped to one feature/checklist item; tick its box here when done.
9. **Ask when uncertain** about a tradeoff that affects privacy, auth, billing, or tenant isolation — those are unforgiving.

---

## 1. Project context

**Flowly** is a privacy-first, cookieless **web traffic analytics SaaS**.

A user adds their website, installs a tiny JavaScript snippet, and then sees their
traffic — **live visitors right now** plus historical reports (visitors, sources,
pages, geography, devices). Real-time/live traffic is the headline feature.

Key facts that shape every decision:

- **Pricing is usage-based** — billed by monthly pageviews, with a **7-day free trial**, via Stripe.
- **Cookieless by design** — no cookies, no personal data stored, no consent banner needed. This is a selling point, not an afterthought.
- **Micro-SaaS** — ship lean and focused. Prefer a small, excellent core over a broad, half-finished feature set. Do not build deferred features (see checklist) until paying users ask.
- **The tracking script and the `/collect` endpoint are the product.** Everything else reads from data they produce.

---

## 2. Glossary

| Term | Meaning |
|---|---|
| **site_id** | Public unique ID per registered website. Ships inside the script, tags every event. **Not a secret** — never used for auth. |
| **visitor_hash** | Anonymous, **daily-rotating** visitor identifier = `hash(IP + user-agent + daily salt)`. Cannot link a visitor across days. |
| **event** | One tracked action sent to `/collect` (today: a pageview). |
| **pageview** | A single page load. |
| **session** | A visitor's continuous activity — events grouped within a timeout window (e.g. 30 min). |
| **bounce** | A session with a single pageview and no further interaction. |
| **account / site** | An **account** (one logged-in user) owns one or more **sites**. All data is scoped to an account. |

---

## 3. Architecture

Monorepo with three apps.

```
/
├── apps/
│   ├── web/                 # Next.js dashboard + marketing (App Router) — custom auth
│   ├── api/                 # FastAPI backend (auth, ingestion, dashboard API, websockets, billing)
│   └── tracker/             # Vanilla JS tracking script customers install (script.js)
├── .env.example             # every env var, with placeholder values
├── .gitignore
├── package.json             # root — pnpm workspaces
├── pnpm-workspace.yaml       # workspaces: apps/*
├── pnpm-lock.yaml
└── CLAUDE.md
```

### Backend (`apps/api`) — where things belong

```
apps/api/
├── pyproject.toml         # Python deps + tool config (managed by uv)
├── uv.lock                # locked dependency versions (committed)
├── .python-version        # pins Python 3.12
├── .venv/                 # virtualenv created by `uv sync` (gitignored)
├── tests/                 # pytest suite, mirrors app/ structure
└── app/
    ├── main.py            # FastAPI app factory, router registration, middleware
    ├── config.py          # settings loaded from env (pydantic-settings)
    ├── routers/           # HTTP/WS endpoints ONLY — thin, no business logic
    │   ├── auth.py        #   POST /auth/signup, /auth/login, /auth/refresh (public)
    │   ├── collect.py     #   POST /collect          (public, no auth)
    │   ├── live.py        #   WS   /live/{site_id}    (authed)
    │   ├── stats.py       #   GET  /stats/...         (authed dashboard queries)
    │   ├── sites.py       #   CRUD for a user's sites (authed)
    │   └── billing.py     #   Stripe checkout + webhooks
    ├── services/          # ALL business logic lives here
    │   ├── auth.py        #   signup, login, token issue/verify, password hashing
    │   ├── ingest.py      #   validate event, bot-filter, fan out to Redis + buffer
    │   ├── live.py        #   active-users set + pub/sub helpers
    │   ├── stats.py       #   build + run ClickHouse queries
    │   ├── sites.py       #   site creation, site_id generation
    │   ├── billing.py     #   plans, usage metering, Stripe logic
    │   └── visitor.py     #   cookieless visitor hashing (IP+UA+daily salt)
    ├── db/                # client setup + raw queries, no business rules
    │   ├── postgres.py    #   SQLAlchemy async engine / session
    │   ├── clickhouse.py  #   ClickHouse client + insert/query helpers
    │   └── redis.py       #   Redis async client
    ├── models/            # Pydantic schemas (request/response) + DB models
    ├── core/              # cross-cutting: security (JWT + password hashing), deps, rate limiting
    ├── workers/           # background tasks (batch writer: Redis Stream -> ClickHouse)
    └── migrations/        # Alembic (Postgres schema only)
```

**The rule:** `routers` parse the request and call a `service`. `services` hold the logic
and call `db`. A router should be a few lines. Never put a ClickHouse query or Stripe call
directly in a router.

### Frontend (`apps/web`)

```
apps/web/
├── package.json           # JS deps (managed by pnpm)
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts
└── app/
    ├── (marketing)/       # public landing, pricing
    ├── (dashboard)/       # authed app (auth-guarded)
    ├── sign-in/ sign-up/  # custom auth pages (call /auth/* on the API)
    └── api/               # Next route handlers (only if a thin BFF is needed)
    components/            # reusable UI (charts, cards, layout)
    lib/                   # api client (attaches auth token), formatting, constants
    hooks/                 # data hooks (TanStack Query wrappers)
```

### Tracking script (`apps/tracker`)

```
apps/tracker/
├── package.json
├── src/script.js          # the source (vanilla JS, zero deps)
└── dist/script.js         # built + minified output served from your CDN
```

### Dependencies, requirements & environments — where they live

| App | Manifest | Lockfile | Environment |
|---|---|---|---|
| `apps/api` | `pyproject.toml` | `uv.lock` | `.venv/` from `uv sync` (gitignored) |
| `apps/web` | `package.json` | `pnpm-lock.yaml` | `node_modules/` (gitignored) |
| `apps/tracker` | `package.json` | (shares root lock) | `node_modules/` |
| root | `package.json` + `pnpm-workspace.yaml` | `pnpm-lock.yaml` | — |

- **Python:** uv manages the venv automatically — never make one by hand or run bare `pip`. Add deps with `uv add <pkg>`.
- **JavaScript:** pnpm workspaces. Add deps with `pnpm add <pkg> --filter web` (or `--filter tracker`).
- **Env vars:** every variable goes in `.env.example` (placeholder) and the real `.env` (gitignored), loaded via `pydantic-settings` in `app/config.py`.
- **Node:** pinned to 24 via `.nvmrc` + `engines`; `engine-strict=true` in `.npmrc` enforces it. pnpm is activated with corepack (pinned in `packageManager`).

### Local services (Postgres, ClickHouse, Redis)

These three must be **running and reachable** for the API to work — run them however you prefer
(installed locally, or a hosted/managed instance). The API connects only through the connection
strings in the env vars (`DATABASE_URL`, `CLICKHOUSE_*`, `REDIS_URL`); it never assumes how they're hosted.

### Core data model (the shape everything depends on)

**Postgres (metadata):**
```
accounts        id, email (unique), username (unique), password_hash (nullable —
                null for OAuth-only accounts), email_verified_at, plan (tier),
                status (lifecycle), trial_ends_at, created_at
identities      id, account_id (FK), provider ("google"|"github"),
                provider_user_id, created_at   (unique(provider, provider_user_id))
sites           id, account_id (FK), site_id (public, unique), domain, created_at
subscriptions   id, account_id (FK), stripe_customer_id, stripe_subscription_id,
                status, plan, current_period_end
```

**ClickHouse (analytics — append-only, queried by `site_id`):**
```
events          site_id, ts (UTC), event_type ("pageview"|"custom"), name, path,
                referrer, source, utm_source, utm_medium, utm_campaign, country,
                region, city, device, browser, os, language, visitor_hash, screen_w
```
`event_type`/`name` (Phase 15 — first premium feature) tag a custom event from
`flowly('event', name)`; custom events are stored but never metered/live (§1),
and their reports are paid-only (free → 402). Conversion goals live in a Postgres
`goals` table (id, site_id FK, name, kind, target, unique(site_id, kind, target)).

**Redis (live + metering — ephemeral):**
```
active:{site_id}            ZSET   visitor_hash scored by timestamp  (who's online now)
live:{site_id}              CHANNEL pub/sub feed of live events
usage:{account_id}:{YYYYMM} COUNTER monthly pageviews for billing
salt:{YYYYMMDD}             STRING  daily salt for visitor hashing (24h TTL)
stream:events               STREAM  ingest buffer drained by the batch writer
```

### Three request paths (keep them separate)

1. **Ingestion** — `POST /collect`. Public, no auth, high volume. Must return in milliseconds.
2. **Dashboard API** — `GET /stats/...`. Requires auth. Queries ClickHouse.
3. **Live** — WebSocket. Requires auth. Subscribes to Redis pub/sub.

---

## 4. Code style

### Python
- **Python 3.12+, fully type-hinted.** Every function has typed args and return type.
- **Async everywhere.** All I/O (DB, Redis, HTTP) uses `async`/`await`. No blocking calls in request handlers.
- **Pydantic v2** for all request/response models and config. Validate at the boundary.
- `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE` constants.
- **Routers stay thin** — no business logic, no raw queries. Push logic into `services`.
- Functions do one thing. If a file exceeds ~300 lines or a function ~50, split it.
- Raise typed exceptions; a central handler converts them to HTTP responses. Don't scatter `HTTPException` through services.
- Format + lint with **Ruff**. No unused imports, no commented-out code committed.

### TypeScript / React
- **Strict mode on.** No `any` — use `unknown` + narrowing.
- **Server Components by default**; add `"use client"` only when interactivity needs it.
- Functional components, **named exports** (no default exports for components).
- Data fetching via **TanStack Query** hooks in `hooks/`, never raw `fetch` in components.
- `PascalCase` components, `camelCase` everything else.
- Tailwind for styling; no inline style objects except dynamic values.

### General
- Comments explain **why**, not what.
- All timestamps are **UTC** in storage; convert to the user's timezone only at display time.
- Every displayed number is rounded/formatted — never leak float artifacts.

---

## 5. Preferred libraries (constraints — don't substitute without updating this file)

| Concern | Use | Do **not** use |
|---|---|---|
| API framework | **FastAPI** | Flask, Django |
| Validation / settings | **Pydantic v2** + pydantic-settings | manual dict parsing |
| Auth tokens | **PyJWT** — short-lived access token + refresh token | home-grown token schemes |
| Password hashing | **argon2-cffi** (or bcrypt via passlib) | plaintext, MD5/SHA, custom crypto |
| Postgres access | **SQLAlchemy 2.0 (async)** + asyncpg | raw sync psycopg |
| Postgres migrations | **Alembic** | hand-written SQL migrations |
| ClickHouse | **clickhouse-connect** (async) | an ORM over ClickHouse |
| Redis | **redis-py** (async client) | aioredis (deprecated) |
| Geo-IP | **geoip2** (MaxMind GeoLite2-City `.mmdb`) — fail-open | a paid geo API on the hot path |
| Background work | FastAPI tasks / a worker reading **Redis Streams** | Celery (overkill now) |
| Billing | **Stripe** (Checkout + Customer Portal + webhooks) | manual invoicing |
| Email | a transactional provider (Resend / Postmark) | your own SMTP |
| Python tooling | **uv**, **Ruff**, **pytest** | pip + venv by hand |
| Frontend | **Next.js (App Router)**, **TanStack Query**, **Recharts**, **Tailwind** | CRA, Redux for server state |
| UI components / theming | **shadcn/ui** (copied into `components/ui/`, restyled on the F0 tokens) + **next-themes** (light/dark) | Material UI, Chakra, Bootstrap, ad-hoc per-page styling |
| Animation | **Framer Motion via the `motion` package** (import from `motion/react`; wrappers in `components/motion.tsx` — subtle, `prefers-reduced-motion`-safe, see F-track motion rule) | GSAP, AOS, CSS keyframe soup, scroll-jacking libs |
| JS package manager | **pnpm** (workspaces) | npm, yarn |
| Tracking script | **Vanilla JS, zero dependencies** | any bundle/framework |

The tracking script has **zero dependencies** and must stay under ~2 KB minified.

---

## 6. Environment variables

All listed in `.env.example`. Real values live in `.env` (gitignored).

| Group | Variables |
|---|---|
| App | `ENVIRONMENT`, `API_BASE_URL`, `WEB_BASE_URL` |
| Auth | `JWT_SECRET`, `JWT_ALGORITHM` (e.g. HS256), `ACCESS_TOKEN_TTL`, `REFRESH_TOKEN_TTL` |
| Postgres | `DATABASE_URL` |
| ClickHouse | `CLICKHOUSE_HOST`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DB` |
| Redis | `REDIS_URL` |
| Social OAuth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` (a provider is enabled only when both its id + secret are set) |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_BUSINESS`, `STRIPE_PRICE_PRO_ANNUAL`, `STRIPE_PRICE_BUSINESS_ANNUAL` |
| Email | `EMAIL_API_KEY` |
| Tracking / Ingestion | `VISITOR_SALT_SECRET` (pepper for the daily visitor hash — prod must override), `TRACKER_SCRIPT_URL`, `GEOIP_DB_PATH` (MaxMind GeoLite2-City `.mmdb`; blank → geo fails open), `STREAM_MAXLEN`, `COLLECT_RATE_LIMIT`, `COLLECT_RATE_WINDOW` |

**Rule:** add a variable here and to `.env.example` in the same change that introduces it.
`JWT_SECRET` must be a long random value and must never be committed.

---

## 7. Commands

> Backend commands run from `apps/api`, frontend from `apps/web`.
> Make sure Postgres, ClickHouse, and Redis are running first (see *Local services*).

### Backend (`apps/api`)
```bash
uv sync                                   # install deps + create .venv
uv add <package>                          # add a dependency
uv run uvicorn app.main:app --reload      # run API (dev, hot reload)
uv run python -m app.workers.batch_writer # run the ClickHouse batch writer
uv run python -m app.workers.digest       # weekly email digest (cron: weekly)
uv run python -m app.workers.onboarding   # onboarding email sequence (cron: hourly)
uv run python -m app.workers.retention    # per-plan retention deletion (cron: daily)
uv run alembic upgrade head               # apply Postgres migrations
uv run alembic revision --autogenerate -m "msg"   # create a migration
uv run pytest                             # run tests
uv run pytest -k name -x                  # run one test, stop on first fail
uv run ruff check . && uv run ruff format .   # lint + format
```

### Frontend (`apps/web`)
```bash
pnpm install                  # install all workspace deps
pnpm add <pkg> --filter web   # add a dep to the web app
pnpm --filter web dev         # run dashboard (dev)
pnpm --filter web build       # production build
pnpm --filter web lint
pnpm --filter web test
```

### Tracking script (`apps/tracker`)
```bash
pnpm --filter tracker build   # bundle + minify src/script.js -> dist/script.js
```

### Stripe (local webhook testing)
```bash
stripe listen --forward-to localhost:8000/billing/webhook
```

---

## 8. Testing

- **Backend tests live in `apps/api/tests/`**, mirroring the `app/` structure. Use `pytest` + `pytest-asyncio`.
- **Always cover the unforgiving paths:** signup/login + token verification, `/collect` ingestion, visitor hashing (no raw IP leaks), **site-ownership checks**, Stripe webhook **idempotency**, and usage metering / limit enforcement.
- **Frontend:** Vitest for units; a Playwright test for the full flow (sign up -> install -> first data -> upgrade) is worth it once onboarding + billing land (Phases 6–7).
- **Every bug fix adds a regression test.** Run the full suite before committing.

---

## 9. Critical rules (read before touching ingestion, auth, or billing)

### Ingestion & the tracking script
- **`/collect` must return in milliseconds.** Don't write to ClickHouse synchronously — validate, push to Redis (live) + Redis Stream (buffer), return `202`. The batch writer drains the stream.
- **Insert into ClickHouse in batches**, never one row at a time.
- **The tracking script must never throw and never break the host site.** Wrap everything; fail silently.
- **`/collect` CORS is open to all origins** (public tracker). The dashboard API CORS is locked to your own domain. Never confuse the two.

### Auth (you own this security surface — do it right)
- **Hash passwords with argon2 (or bcrypt).** Never store or log plaintext passwords. Never invent your own crypto.
- **Sign JWTs with a strong secret** (`JWT_SECRET`). Access tokens are **short-lived**; use a refresh token for renewal.
- **Verify the token on every authed route** (dashboard + websocket). `/collect` and `/auth/*` are the only unauthenticated routes.
- **Never log tokens, password hashes, or credentials.**

### Security & multi-tenant isolation
- **`site_id` is public.** Never treat it as a secret or use it for auth.
- **Every dashboard/live query MUST verify the site belongs to the authenticated user.** Filtering by `site_id` alone is not enough — confirm ownership. This is the #1 way to leak one customer's data to another.
- **Rate-limit `/collect` per site_id** and **rate-limit `/auth/login`** to blunt abuse/brute-force.

### Privacy (the product's promise — do not break it)
- **Never store or log PII.** No raw IPs at rest, no cookies, no persistent fingerprints.
- Visitor ID = `hash(IP + UA + daily salt)`; **salt rotates every 24h.** Never log the raw IP.
- **Enforce per-plan data retention** (e.g. 30 days free, 1 year Pro); delete expired events on a schedule.

### Accuracy
- **Filter bots before counting.** Wrong numbers cause instant churn.
- Store UTC; never mix timezones in aggregation.

### Billing
- **Stripe webhooks must verify the signature and be idempotent** (same event can arrive twice — process once).
- **Meter usage in real time** (Redis) and **enforce plan limits.** Prefer a soft cap + upgrade nudge over dropping data — but never silently exceed a paid tier's cost.
- The 7-day trial is a Stripe trial period; handle `trial_will_end` and failed-payment events.

### Live path
- **Redis is the source of truth for "right now."** Never hit ClickHouse for the live counter.

---

## 10. Definition of done

A checklist item is done only when **all** of these are true:

- [ ] Code follows sections 4–5 (style + chosen libraries).
- [ ] Lint passes and tests pass locally.
- [ ] Any new env var is in `.env.example`; any new dependency updated in section 5.
- [ ] Relevant *Critical rules* upheld (auth token verified, ownership check, no PII/credentials logged, batched inserts, idempotent webhook — whichever apply).
- [ ] This file updated if a convention changed, **and the checklist box ticked**.

---

## Features — build checklist

One focused theme per phase. Build them in order — finish a phase before starting the next.
Each phase has a **Goal** (what "done" looks like) and lists **where** each piece is built.

### Phase 0 — Project setup, dependencies & first push
**Goal:** a skeleton that installs, runs, lints clean, has one passing test, and is on GitHub.
- [x] Monorepo scaffold: root `package.json` + `pnpm-workspace.yaml` (`apps/*`), `.gitignore`, `.env.example`, `README.md`
- [x] Create the three app folders: `apps/web`, `apps/api`, `apps/tracker`
- [x] Backend deps: `apps/api/pyproject.toml` + `.python-version` (3.12); `uv sync` creates `.venv/`
- [x] Frontend deps: Next.js app in `apps/web`; `pnpm install`
- [x] Minimal API: app factory `app/main.py`, settings `app/config.py`, `GET /health`
- [x] Minimal web: Next.js runs and shows a placeholder page
- [x] One passing test (`apps/api/tests/test_health.py`) and `ruff` clean
- [x] Verify locally: `uv run uvicorn ...`, `pnpm --filter web dev`, `uv run pytest` all work
- [x] Init git, create the GitHub repo, and push

### Phase 1 — Database & auth system
**Goal:** a user can sign up, log in, and reach a protected dashboard.
- [x] Local services reachable (Postgres + Redis) via their env-var connection strings — verified live; ClickHouse client present, connectivity used from P3
- [x] DB clients: `db/postgres.py`, `db/clickhouse.py`, `db/redis.py`
- [x] Postgres schema + Alembic baseline: `accounts`, `sites`, `subscriptions` (see Core data model) — migration applied to Postgres (`alembic upgrade head`)
- [x] Password hashing util (argon2/bcrypt) in `core/security.py`
- [x] `POST /auth/signup` (`routers/auth.py` -> `services/auth.py`): create account, store `password_hash`
- [x] `POST /auth/login`: verify password, issue access + refresh JWT
- [x] `POST /auth/refresh`: rotate the access token
- [x] JWT verification dependency `require_user` in `core/security.py`; tenant scoping (`user_id -> account`)
- [x] Rate-limit `/auth/login`
- [x] Frontend: custom `sign-in/` + `sign-up/` pages calling `/auth/*`; store token in `lib/` api client; guard `(dashboard)` routes
- [x] Tests: signup, login, token verify, protected route rejects missing/invalid token

### Phase 2 — Tracking script (core)
**Goal:** a tiny script that, dropped on a page, fires a pageview to the API.
- [x] `apps/tracker/src/script.js`: read `data-site` (site_id) from the script tag
- [x] Send pageview via `navigator.sendBeacon` to `/collect` (endpoint derived from the script's own origin, `data-api` override; `text/plain` body → no CORS preflight, with a `fetch` keepalive fallback)
- [x] Payload: site_id, path (no query string), referrer, screen width, utm_source/medium/campaign (`language` dropped — no `events` column to store it)
- [x] SPA support: wrap `history.pushState`/`replaceState` + listen for `popstate`; same-path dedupe
- [x] Wrap everything in try/catch; fail silently; never break the host page
- [x] Build + minify -> `apps/tracker/dist/script.js` (~1.0 KB, < 2 KB) via esbuild; serve from CDN
- [x] Manual test: `apps/tracker/test/index.html` harness (drop-in with a hand-made `sites` row); verified the beacon fires with the right payload

### Phase 3 — Ingestion pipeline
**Goal:** events from the script are validated, anonymised, and stored durably.
- [x] `POST /collect` (`routers/collect.py` -> `services/ingest.py`): public, open CORS, returns `202` fast
- [x] Validate payload via a Pydantic model in `models/` (`models/events.py`, `extra="ignore"`, `screen_w` clamped)
- [x] Cookieless visitor ID (`services/visitor.py`): hash `IP + UA + daily salt`; rotate salt daily (Redis `salt:{date}`, 24h TTL, `SET NX`); never log raw IP
- [x] Bot filtering (`services/useragent.py`): UA marker list + empty-UA; drop before counting
- [x] Per-site_id rate limiting (`core/ratelimit.py`): non-raising `is_rate_limited` keyed by `(site_id, IP)`; over-limit dropped with `202`
- [x] Buffer: push the validated, **IP-free** event to `stream:events` (bounded `MAXLEN ~`)
- [x] Batch writer worker (`workers/batch_writer.py`): consumer group + `XAUTOCLAIM` reclaim, bulk-insert to ClickHouse, `XACK` after success
- [x] ClickHouse `events` table (`db/clickhouse.py` + `--init`) — see Core data model; adds `event_id` (UUID) for dedupe
- [x] Enrichment on the hot path: geo (`services/geo.py`, fail-open), device/browser/os (`services/useragent.py`), `source` from UTM/referrer vs `Origin`
- [x] Tests: bad payload rejected, bot dropped, valid event enqueued (IP-free), visitor-hash determinism/no-leak, batch-writer insert + reclaim

### Phase 4 — Real-time / live traffic (headline feature)
**Goal:** the dashboard shows visitors live.
- [x] Active users (`services/live.py`): `ZADD active:{site_id} {ts} {visitor_hash}`; count online (last 5 min) via `ZCARD` after `ZREMRANGEBYSCORE` eviction; `mark_active` evicts + `EXPIRE`s the key in one pipeline so the set is bounded even with no viewer
- [x] Pub/sub publish (`services/ingest.py`): `PUBLISH live:{site_id} {event_json}` per event — best-effort after the durable `XADD`, payload IP-free and carries no `visitor_hash`
- [x] WebSocket (`routers/live.py`): `WS /live/{site_id}` — token via `?token=` (browser WS can't set headers) + Origin check + site-ownership verify; subscribes via `services/live.py::subscribe_events` and forwards to the client. Plus read-only `GET /sites` (borrowed from Phase 6) for the site picker
- [x] Live dashboard view (`apps/web/app/(dashboard)/live`): live counter, live feed, current pages (`hooks/useLiveTraffic.ts` native WebSocket, `hooks/useSites.ts`, `components/live.tsx`)

### Phase 5 — Dashboard metrics (historical)
**Goal:** the core reports users log in to see.
- [x] Stats queries (`services/stats.py`): overview (visitors/sessions/pageviews/bounce/duration), time-series, sources + UTM, audience (geo/device/browser/os), top/entry/exit pages — sessions/bounce/duration derived in SQL from a 30-min `visitor_hash`+`ts` gap (`_SESSIONIZED_CTE`); pure `(sql, params)` builders + shaping service
- [x] Stats endpoints (`routers/stats.py`): `/stats/overview`, `/stats/timeseries`, `/stats/sources`, `/stats/audience`, `/stats/pages` — authed + ownership check (`owned_site` dep → 404 before any query); ownership query lives in `services/sites.py` (extracted from `services/live.py`)
- [x] Dashboard UI (`apps/web/app/(dashboard)/dashboard`, `components/stats.tsx`, `hooks/useStats.ts`): date-range presets (24h/7d/30d) + period comparison, Recharts line chart, metric cards, sources/audience/pages/UTM tables

### Phase 6 — Site onboarding
**Goal:** a user can add their own site and confirm it's connected.
- [x] Add-site flow (`routers/sites.py`, `services/sites.py`, web): `POST /sites` → `create_site` normalizes the domain (shared `core/urls.py::normalize_host`), mints a `secrets.token_hex(8)` `site_id`, stores it; response carries the server-built install snippet (`build_snippet` from `TRACKER_SCRIPT_URL`). `GET /sites` moved here from `live.py`.
- [x] Install verification: `GET /sites/{site_id}/status` → `first_event_seen` — Redis presence first (instant), ClickHouse existence probe as durable fallback; frontend `useSiteStatus` polls waiting→connected, stopping on connected and after a ~3-min cap (+ manual re-check). No new DB column.
- [x] Install guides: universal snippet + brief per-platform tabs (Next.js, WordPress, Shopify, Webflow, GTM) in `components/install.tsx`; add-site + install route at `app/(dashboard)/sites`.

### Phase 7 — Billing & usage metering
**Goal:** trial converts to paid, metered by pageviews.
- [x] Usage metering (`services/billing.py`, Redis): per-account monthly counter (`usage:{account_id}:{YYYYMM}`); soft cap + 80% warning + over-limit nudge (hard-ceiling backstop bounds cost)
- [x] Stripe (`routers/billing.py`, `services/billing.py`): Checkout with 7-day trial pass-through; Customer Portal link; monthly + annual plan prices
- [x] Webhooks (signed + idempotent): subscription created/updated/deleted, `trial_will_end`, payment failed; link Stripe customer -> `subscriptions`
- [x] Tests: webhook idempotency + signature, entitlement-not-from-redirect, metering flags, trial handling

### Phase 8 — Growth & retention
**Goal:** the micro-SaaS acquisition + retention loop.
- [x] Weekly email digest (`services/digest.py` + `workers/digest.py`, Resend via `services/email.py`; per-ISO-week Redis idempotency marker; reuses Phase 5 stats builders)
- [x] Public / shareable dashboard (`services/sharing.py`, authed create/rotate/revoke in `routers/sites.py`, public token-scoped `routers/public.py`; web `app/share/[token]`) — open link, revocable
- [x] "Powered by Flowly" badge on free tier (`show_badge` flag on the public payload from `effective_plan`; `components/PoweredByBadge.tsx`)
- [x] Onboarding email sequence (`services/onboarding.py` + `workers/onboarding.py`; `onboarding_emails` ledger; welcome/install/live steps + `trial_will_end` wired in billing)

### Phase 9 — Privacy & trust
**Goal:** deliver on the privacy promise, publicly.
- [x] Retention deletion job (`services/retention.py` + `workers/retention.py`, per-plan window `config.RETENTION_DAYS` free 30 / pro 365 / business 730; site-scoped `ALTER TABLE ... DELETE`)
- [x] CSV export endpoint (`services/export.py`, `GET /stats/export` — authed, ownership-checked, aggregated reports only, no PII)
- [x] Privacy / GDPR page documenting the cookieless approach (`app/privacy`)

---

## Frontend redesign track — Phases F0–F7 (build BEFORE Phase 10's UI)

Premium UI overhaul. Rules: every phase builds ON the F0 design system — no ad-hoc styling ever again.
**Design direction (decided):** layout reference = the phpAnalytics public-demo structure (grouped sidebar, delta stat cards, icon-rich table cards with "View all", header date-picker, light/dark). **Primary = Indigo `#6366F1`** (hover `#4F46E5`; dark-mode primary `#818CF8`). Neutrals: slate (`#FAFAFA` page / `#FFFFFF` card / `#E5E7EB` border light; `#0B0F1A` / `#111827` / `#1F2937` dark). Semantic: success/live `#10B981`, warning `#F59E0B`, danger/down `#EF4444` — **green/red are reserved for live/up/down states, never decorative.** Chart series: `#6366F1 #22D3EE #A78BFA #F472B6 #FBBF24`. All as tokens in `tailwind.config.ts` — never raw hex in components.
**Landing-page reference (from the demo video, reviewed 2026-07-04):** dark-first modern-SaaS layout — sticky nav (logo / links / theme toggle / CTA); hero = badge pill → large headline with ONE accent-highlighted word → one-line subcopy → dual CTA (primary filled + secondary outline) → dominant framed dashboard visual; then icon-card features grid (icons in small tinted containers), alternating product-detail sections, pricing cards, multi-column footer. Accent used sparingly (headline highlight, primary buttons, icon tints only); premium feel comes from generous section whitespace and clearly stepped-down muted secondary text. **Copy structure only — not the template's placeholder words or its fixed pricing tiers.**
**Theming rule: the ENTIRE site is dual-theme** — marketing pages AND dashboard both fully support light + dark (toggle in the marketing nav and the app header). Default = system preference, falling back to **dark**. Every component built on tokens from day one; a component that breaks in either theme is not done (§10).
**Motion/animation rule (landing + dashboard):** library = **Framer Motion** (add to §5). Purposeful and subtle — never decorative noise: hero elements stagger-fade-up on load; sections scroll-reveal ONCE (fade + ~16px rise, 300–500ms ease-out, no re-trigger); stat-card numbers count up when entering view; charts draw in on first render; cards get a slight hover lift; live elements pulse (`#10B981` dot, feed items slide in). Hard limits: **respect `prefers-reduced-motion` everywhere** (all non-essential motion off), zero layout shift from animations, no scroll-jacking, nothing longer than 500ms, no continuous looping animation except the live pulse.

### Phase F0 — Design system foundation
**Goal:** tokens + component kit + app shell that every later page inherits.
- [x] Color tokens (table above) + radius/shadow scale — **in `app/globals.css` `@theme inline` (Tailwind v4 is CSS-first; there is NO `tailwind.config.ts` and none must be created)**; semantic vars on `:root`/`.dark`, shadcn variable names kept (+ Flowly `--primary-hover`, `--success`, `--warning`, `--chart-1..5`, `--shadow-card`); **light/dark via `next-themes`** — class strategy needs `@custom-variant dark (&:is(.dark *))` or `dark:` silently keys off the media query; `ThemeProvider` in `app/providers.tsx`, `suppressHydrationWarning` on `<html>`, no-flash via next-themes' pre-paint script; `components/theme-toggle.tsx` (CSS-swapped icons, never render `useTheme().theme`) — app header now, **marketing nav gets it in F1**
- [x] Typeface: Geist was already wired via `next/font` but defeated by a `font-family: Arial…` rule in globals.css — rule removed, `--font-sans: var(--font-geist-sans)` mapped in `@theme`
- [x] **shadcn/ui** adopted (new CLI: `shadcn init -b radix -p nova`, style `radix-nova`, deps `radix-ui`/`cva`/`clsx`/`tailwind-merge`/`lucide-react`/`tw-animate-css` + `shadcn` runtime for its base css import); kit in `components/ui/`: Button (default hover → `bg-primary-hover`), Card, Input, Select, Table, Dialog, Tabs, Badge, Skeleton, DropdownMenu, Sheet + **Toast = sonner** (shadcn's `toast` is deprecated; `<Toaster>` mounted in providers, auto-syncs theme) + custom `EmptyState` (`components/ui/empty-state.tsx`); duplicated pill-Tabs killed → `components/segmented-tabs.tsx` (thin generic adapter over shadcn Tabs)
- [x] App shell: `lib/navigation.ts` holds the FULL grouped IA (Realtime / Overview / Behavior / Acquisitions incl. **AI platforms** / Geographic / Technology / Workspace) as data with `ready` flags — unbuilt reports ship by flipping the flag in F4/Phases 10–11; `components/layout/{app-sidebar,app-header,site-switcher,site-context}.tsx`; `SiteProvider`+`useActiveSite()` (localStorage-persisted via the repo's `useSyncExternalStore` pattern — the new `react-hooks/set-state-in-effect` lint rule forbids setState-in-effect) replaced every per-page `<select>`; header has the date-range-picker **slot** (real picker lands F1) + theme toggle + user menu; mobile nav = shadcn Sheet below `lg`
- [x] Recharts theme module `components/charts/chart-theme.tsx`: colors are `var(--chart-N)` CSS vars passed straight to SVG props (auto theme flip, zero JS), `gridProps`/`axisProps`/`ChartGradient`/`ChartTooltip`; TrafficChart → indigo Area + gradient fill, `--chart-2` line, compact axes; shared formatters centralized in `lib/format.ts`
- [x] Loading skeletons (`components/skeletons.tsx`: MetricCards/Chart/Table/Page) + `EmptyState` wired wherever "Loading…" text existed; grep gate holds: no raw hex / `gray-*` / `bg-black` utilities outside `globals.css` (sole exception: the vendored dialog/sheet overlay scrim `bg-black/10` in `components/ui/`)

### Phase F1 — Landing page
**Goal:** a marketing page that sells the product in one scroll — built to the demo-video layout reference above, in both themes.
- [x] Sticky marketing nav (`components/marketing/nav.tsx`, CSS-only sticky + backdrop-blur; links in shared `nav-links.ts`, mobile Sheet nav): logo, Features, Pricing, Live demo (all `/#anchor`), theme toggle, Sign in, "Start for free" CTA — new `app/(marketing)/` route group (layout = nav + placeholder footer; `/` and `/privacy` moved in, URLs unchanged)
- [x] Hero (`components/marketing/hero.tsx`): badge pill → headline with one indigo word → subcopy → dual CTA → **embedded LIVE demo dashboard** (`components/public-dashboard/demo-embed.tsx`, token from new `NEXT_PUBLIC_DEMO_SHARE_TOKEN`; fixed 7d window, 60s overview refetch, fixed-height glow frame → zero CLS; **unset/failed token → same composition fed labeled sample data** from `components/reports/sample-data.ts` — the marketing page never depends on a running backend). **Share page restyled to the phpAnalytics reference**: presentational kit in `components/reports/` (delta `StatCards` with count-up, `TrafficChartCard`, icon-rich `BreakdownCard`/`PagesCard` with indigo share bars + "View all", `row-icon.tsx` = DDG favicons for domain-looking sources / emoji flags from ISO-2 / lucide device-browser-OS maps, `UtmCard`, `LiveDot`) composed by `components/public-dashboard/{public-dashboard,report-sidebar}.tsx` — grouped in-page-state sidebar (Overview / Behavior / Acquisitions / Audience, scoped to the public API; mobile = pill row); hero embed + share page are compositions of the SAME kit (F4 reuses it for the authed dashboard; `components/stats.tsx` stays for the old dashboard until F4)
- [x] Animations (`components/motion.tsx` on the `motion` package): hero `Stagger` on load, `Reveal` scroll-reveal once (16px rise, ≤400ms), `CountUp` (final value in initial markup, animates via ref textContent — no setState-in-effect), hover lifts + live pulse pure CSS — all `useReducedMotion`/`motion-reduce` gated, content never stranded at opacity 0
- [x] Sections in order (`components/marketing/`): claims strip (honest social-proof substitute — no fake logos) → features grid (6 shipped-feature icon cards, indigo-tinted containers) → how it works (3 steps + illustrative snippet) → privacy USP block → **metered pricing** (`pricing.tsx` free-vs-paying cards + graduated rate table server-rendered from `lib/pricing.ts` `PRICING_TIERS` + client `pricing-slider.tsx` snap-point slider; **`lib/pricing.ts` = ONE source of pricing truth** — integer-cents graduated math, boundaries pinned by `lib/pricing.test.ts` via the new minimal **Vitest** setup (`pnpm --filter web test`); F5 billing UI + Phase 14 must consume it) → FAQ (shadcn Accordion over **`content/faq.ts`** — plain-string single source the F7 chatbot reuses) → final CTA banner
- [x] Both themes + reduced-motion verified; Server Components except the client shells (slider, demo embed, theme toggle, FAQ accordion, mobile Sheet — content stays server-defined data); new shadcn adds: accordion, slider; new env vars `NEXT_PUBLIC_API_URL` (was consumed but undocumented) + `NEXT_PUBLIC_DEMO_SHARE_TOKEN` in `.env.example`/§6 (real values live in `apps/web/.env.local` — Next doesn't read the repo-root `.env`)

### Phase F2 — Auth pages (register system)
**Goal:** polished sign-in / sign-up + the missing loop pages.
- [x] Redesign `sign-in/` + `sign-up/` **pixel-faithful to `desgin/demo-registersystem.png`** (user call: reference-exact, so the auth pages are a FIXED dark-violet "cosmic" scene in both themes — the one deliberate exception to dual-theme; no theme toggle on auth pages): all scene colors live in `globals.css` scoped to `.auth-scene` (re-maps the F0 token vars to the reference palette so every token-based component inside re-themes automatically — no raw hex in components; plus `.auth-card` glass, `.auth-tab-active`/CTA purple gradients, `.auth-badge`, `.auth-gradient-text`, unlayered so overrides beat utilities). Scene decorations: **the reference's own 3D art cropped into `public/auth/{cube,gem,corner}.png`** (opaque near-black crops rendered via `.auth-art` — `mix-blend-mode: screen` + single-radial/soft-linear `mask-image` fades so the crop rectangles melt into the scene; multi-layer `mask-composite: intersect` proved unreliable in Chromium, keep masks single-layer) plus pure-CSS star field / planet arc / orbit ring / sphere, animated by `auth-float` floats, `auth-glow-pulse` cube glow, and `auth-twinkle` star shimmer — **all disabled under `prefers-reduced-motion`**. `components/auth/auth-shell.tsx` (split `AuthLayout` — brand panel with WELCOME badge/gradient-word headline/3 feature tiles, entrance `Stagger`/`Reveal` from `components/motion`; `AuthCard`; gradient `AuthTabs`) + `components/auth/fields.tsx` (icon-inset `Field`, `PasswordField` show/hide, `SubmitButton` arrow/spinner, `FormError`/`SuccessNote`/`DevCodeHint`) — replaced and deleted `components/form.tsx` (its one non-auth consumer, `(dashboard)/sites`, migrated). `SocialButtons` restyled: "or continue with" divider + Google (brand-color SVG — brand assets exempt from no-raw-hex; GitHub mark `currentColor`) / GitHub. Inline validation on sign-up (blur + submit, `aria-invalid` + per-field errors, `noValidate`). Responsive: brand panel/heavy decor hidden below lg/xl, card full-width `max-w-[30rem]`, trust strip wraps
- [x] **Verify-email + reset-password pages** — already existed as code-based flows (sign-up's 6-digit code step, `forgot-password/` two-step, `reset-password/`); all restyled onto the F2 shell (OTP-style centered code inputs, `autoComplete="one-time-code"`). Forgot-password entry was already on sign-in, kept on the password label row
- [x] Post-signup redirect → add-first-site flow: `lib/post-auth.ts::postAuthPath()` — after password login AND OAuth callback, zero-site accounts land on `/sites`, everyone else `/dashboard`; fails open to `/dashboard` (routing never blocks a sign-in)

### Phase F3 — User profile / settings
**Goal:** the settings area that never existed.
- [x] `app/(dashboard)/settings`: profile (username/email), change password, email preferences (surface the existing `email_opt_out` flag as a toggle), linked OAuth identities (`identities` table), danger zone → **delete account**
- [x] Backend endpoints needed (new): change-password, change-email (re-verify), delete-account (Postgres rows + site-scoped ClickHouse delete via the existing retention machinery) — service layer per §3, tests for auth-required + ownership

### Phase F4 — Dashboard redesign
**Goal:** the existing reports re-rendered premium — no new data work.
- [x] Migrate dashboard + live + sites pages into the F0 shell; each Phase 5 report becomes a sidebar destination
- [x] Stat cards with delta badges (prior-period compare already computed in Phase 5)
- [x] Icon-rich tables: country flags, browser/OS icons, referrer favicons via `icons.duckduckgo.com/ip3/{domain}.ico`, "View all" per card
- [x] Live page polish: pulsing live dot (`#10B981`), feed items animating in, current-pages list
- [x] Skeletons + empty states ("No data yet — install your snippet" → install CTA) everywhere

### Phase F5 — Billing UI
**Goal:** billing surfaces ready for the Phase 14 model.
- [x] Redesign `billing` page: current usage meter, **month-to-date bill estimate** (graduated math over the usage counter), invoice/Portal links
- [x] Build `PaywallModal` + reworked `UsageBanner` (80% warning / locked / bill-estimate states) as components now — **full lock wiring (402 gating) lands with Phase 14 backend**; until then they render from `usage_summary` flags
- [x] Pricing page (marketing) shares the F1 slider component — one source of pricing truth

### Phase F6 — Footer + static pages
**Goal:** the trust layer.
- [x] Footer component (marketing + app): product links, legal (Privacy, Terms), About, Contact, social icons (X/GitHub/LinkedIn), "Powered by Flowly" self-promo
- [x] **Terms of Service** page (new — charging money without terms is a gap), restyle existing Privacy page, About page, Contact page (form → existing Resend `services/email.py`, transactional path + honeypot/rate-limit)
- [x] Custom 404 page

### Phase F7 — Polish + support chatbot (last)
**Goal:** finishing pass + a cheap, safe info bot.
- [x] Responsiveness pass (mobile dashboard), accessibility pass (focus states, contrast on the token palette), toast feedback on all mutations
- [x] **Chatbot (hybrid — hardcoded first, AI fallback):** floating widget on marketing pages (`components/ChatWidget.tsx`); `services/assistant.py` matches the five known intents — what is Flowly / pricing / features / policy / contact — against **hardcoded canonical answers** (single source: a `content/faq.ts` also feeding the F1 FAQ section); only unmatched questions call the Anthropic API (small/cheap model, e.g. Claude Haiku) with a system prompt of site facts
- [x] Chatbot guardrails (**non-negotiable — public AI endpoint = abuse magnet**): public `POST /assistant/chat` rate-limited per IP (reuse `core/ratelimit.py` pattern) + low `max_tokens` + short context; **zero access to user/analytics data**; system prompt instructs: answer only about Flowly, never invent pricing, unknown → "contact us" link; new env var `ANTHROPIC_API_KEY` (→ `.env.example` + §6); tests: intent matching, rate limit, refuses off-topic
- [x] Sequencing note: chatbot is deliberately LAST — it must describe the finished product and final pricing

---

### Phase 10 — claude (existing data — no schema or tracker changes)
**Goal:** richer breakdowns + drill-down, built purely on data already in `events`.
- [x] Channel classifier (`services/channels.py`): bucket `referrer` host → direct / search / social / **AI platforms (chatgpt.com, perplexity.ai, claude.ai, gemini.google.com…)** / referral; `/stats/channels` (5-way split) + `/stats/channels/{channel}` per-host drill-down (Search/Social/AI sidebar pages). Host lists shared by `classify()` + the SQL `multiIf`; AI checked before search
- [x] Screen-size / viewport breakdown: `multiIf` width buckets over `screen_w` on `/stats/audience?dimension=screen` (`/tech/screens` page)
- [x] Time-of-day / day-of-week heatmap: `/stats/heatmap` — **§4 exception: aggregate in the viewer's IANA tz** (`toHour(ts,{tz})` / `toDayOfWeek(ts,0,{tz})`); 7×24 zero-filled grid; `components/reports/heatmap-card.tsx` in Overview
- [x] Custom date range picker (frontend-only): native date-input popover (`components/dashboard/custom-range.tsx`, dependency-free) → custom `[from,to)` in the range context; server parses arbitrary ranges already
- [x] Dashboard-wide click-to-filter + multi-filter combos: allowlisted filter dict threaded into every builder + `_SESSIONIZED_CTE` (**server-parameterized `f_*` params, §9**); `core/statsfilters.py::FilterDep`, `components/layout/filter-context.tsx` + `active-filters.tsx` + `onSelect` on cards; every chart/table re-filters
- [x] Page detail view: click a page row → `path` filter → all reports re-slice (falls out of the filter work)
- [x] Top-10 pages ranked by traffic and by engagement (`sort=engagement`: per-page bounce % + avg time-on-page via `leadInFrame`; traffic/engagement toggle)
- [x] **Full parity (decided):** filters + new datasets flow into the public share router (`/public/{token}/{channels,heatmap,audience?dimension=screen,…}`) and CSV export (`channels`/`screens`/`heatmap` datasets + filters in `services/export.py`)

### Phase 11 — Small data additions (first ClickHouse schema change)
**Goal:** city, language, and the live map — plus a real migration convention for `events`.
- [x] **ClickHouse migration convention** (`app/db/ch_migrations.py` — ordered idempotent `ADD COLUMN IF NOT EXISTS` + `--migrate` CLI; `CREATE_EVENTS_TABLE` kept in sync; documented in §3)
- [x] City breakdown: `geo.lookup`→city, threaded to a new `city` column; `/geo/cities` page — **paid-tier** (server 402 gate on stats/public/export via `billing.require_dimension_access`; free UI shows upgrade `EmptyState`)
- [x] Language breakdown: `navigator.language` re-added to tracker (1.1 KB), `language` column, `/geo/languages` page (free)
- [x] Live-by-country panel: `LiveCountries` (flags + live counts + bars) on the live page from the existing live `country` payload — no backend change. **NOTE:** shipped as a lean country panel, not a geographic choropleth (a real map needs a bundled world-map/topojson asset — obtainable only online; deferred)

### Phase 12 — Uptime monitoring & down alerts
**Goal:** ping each site on a schedule; email the owner when it goes down / recovers.
- [x] Pinger worker (`workers/uptime.py`, run-once + cron ~5 min, gated on `UPTIME_ENABLED`): HTTP GET/HEAD per site domain (`services/uptime.py::check_with_retry`) with timeout + in-run retry blip filter + a consecutive-failure threshold before alerting (retry-before-alarm); `uptime_monitors` (state + fail streak) + `uptime_incidents` (ledger) in Postgres (migration `a1b2c3d4e5f6`). Plus an **SSRF guard** (`_screen_host`) — `domain` is an unverified Phase-6 label, so every request + redirect hop resolves the host and refuses any non-global address (loopback/private/link-local incl. 169.254.169.254; IPv4-mapped IPv6 unwrapped), redirects followed manually, GET/HEAD only
- [x] Down / recovered email alerts (`services/email.py::send_uptime_{down,up}_email` → direct `send_email`): **transactional — NEVER through `services/notifications.py` (the marketing opt-out gate)**; alert once per incident via the open incident's `notified_down`/`notified_up` flags (best-effort retry), not per failed ping; only verified owners emailed
- [x] Dashboard status view: `GET /sites/{site_id}/uptime` (authed, ownership-scoped) → `hooks/useSites.ts::useSiteUptime` + `components/uptime/uptime-panel.tsx` (green/red up/down `Badge` on the F0 semantic tokens + recent-incidents list) on the site detail view
- [x] Tests (`tests/test_uptime.py`, 25): down→alert-once, recover→notice, flapping doesn't spam, no alert through the marketing gate (opted-out owner still alerted), SSRF targets refused (incl. redirect-to-internal + IPv4-mapped), unverified-not-emailed, blocked≠incident, endpoint ownership 404

### Phase 13 — Search Console integration (keywords & SEO)
**Goal:** show which search keywords the site performs on, its average position, and opportunity keywords — from the customer's own GSC data.
- [x] GSC connect (`services/searchconsole.py` + `services/gscapi.py` + `routers/searchconsole.py`): a **separate offline-access flow** reusing the Google client creds with `webmasters.readonly` + `access_type=offline`/`prompt=consent`; authed `POST /searchconsole/{site_id}/connect` → consent URL (Redis state binds `(account,site)`); public `GET /searchconsole/callback` exchanges the code, auto-matches the site's domain to a verified property, stores the **refresh token** (`search_console_connections`, Alembic `b2c3d4e5f6a7`; **never logged/returned**, §9)
- [x] Sync worker (`workers/searchconsole.py`, run-once + cron daily): `sync_all` pulls Search Analytics (query/page/clicks/impressions/position) into `search_metrics`; **idempotent per (site, day)** (delete-reinsert); best-effort per site; **Postgres, not ClickHouse** (external low-volume daily data)
- [x] Keyword performance report: `GET /searchconsole/{site_id}/keywords` — top queries by clicks, impression-weighted avg position, derived CTR, date-ranged
- [x] Page-level search performance: `GET /searchconsole/{site_id}/pages`
- [x] Opportunity-keyword recommendations: `GET /searchconsole/{site_id}/opportunities` — position 5–20 ranked by impressions, **no paid keyword API**
- [x] Frontend: `hooks/useSearchConsole.ts` + `components/searchconsole/search-report.tsx` (connect empty-state → consent; clicks/impressions/CTR/position table; sync-now/disconnect; `?gsc=` toast) + `/search-console/{keywords,pages,opportunities}` pages + new "Search Console" nav group. GSC is the only honest keyword source (referrers strip them)

### Phase 14 — Pricing v2: metered pay-per-view + paywall + site limits (billing — unforgiving, §9)
**Goal:** replace the Phase 7 flat plans entirely with graduated usage-priced billing; cap sites at 5; free accounts over the limit hit a dashboard paywall.
**DECIDED:** tiering is **graduated** (each tier priced separately — declining rates make volume tiering nonsensical: a bill must never drop when usage crosses a threshold).
Pricing schedule (per account, per month, **all sites' views counted together** — the `usage:{account_id}:{YYYYMM}` counter is already account-wide, no counter change needed):
| Tier | Rate | Example bill (graduated) |
|---|---|---|
| First 1,000 views | Free | 1k → $0 |
| 1k → 10k | $0.99 per 1k | 10k → $8.91 |
| 10k → 100k | $0.10 per 1k | 100k → $17.91 |
| 100k → 1M | $0.05 per 1k | 1M → $62.91 |
| Over 1M | $0.03 per 1k | — |
(Matches/beats Plausible $9@10k / $19@100k / $69@1M and Fathom $15@100k / $60@1M. Metered = a selling point: no plan-jump cliffs.)
- [x] **Decommission the flat-plan model:** removed 4 flat `STRIPE_PRICE_*` + `PLAN_QUOTAS` + `HARD_CEILING_MULTIPLE`; reused Phase 7's Checkout/Portal/webhook/idempotency/metering. `effective_plan` → **free** vs **metered**. No live flat-plan subscribers (pre-launch) → no migration
- [x] Stripe metered billing: ONE graduated-tiered metered Price (`STRIPE_PRICE_METERED`); `report_usage_to_stripe` pushes the **delta** (additive meter events) from a **durable Postgres high-water mark** (`subscriptions.metered_usage_reported`/`metered_usage_period`, migration `c3d4e5f6a7b8`) so an evicted Redis key can't cause a double-bill (§9); new `workers/usage_report.py` (cron hourly). **Webhooks stay the only writer of entitlement**
- [x] **Free-limit paywall:** `usage_summary` emits `status:"locked"` past 1k; typed **402 `AccountLockedError`** (`code:"account_locked"`) on all `/stats/*` routes + the live WS; web `components/PaywallGate.tsx` mounts a **non-dismissible** `PaywallModal` (CTA → metered Checkout, 7-day trial). **`/collect` never gates (§9).** Checkout blocks any entitled account incl. an in-window trial (no double-subscribe)
- [x] Free-tier UX before the wall: `UsageBanner` — warning ≥80% of 1k, locked >1k; paying accounts see a month-to-date bill estimate (client-side `lib/pricing.ts` over the Redis counter)
- [x] 5-site limit (`services/sites.py::create_site`): typed **403 `SiteLimitError`**, enforced in the service (§3); web hides "Add site" at 5
- [x] Re-map plan-keyed logic: retention (`config.RETENTION_DAYS` → free 30d / **metered 365d**), `show_badge` (`effective_plan==free`); signup starts accounts free (trial moved to upgrade, once per account)
- [x] Updated §1 (pricing + trial-at-upgrade), §6 (Stripe env vars), `.env.example`, §7 (usage-report cron), pricing page
- [x] **OPEN:** free tier stays at **1k** (confirmed) — `config.FREE_MONTHLY_VIEWS` / `lib/pricing.ts::FREE_MONTHLY_VIEWS`
- [x] Tests: boundary math (Vitest, 1k/10k/100k/1M), free no-charge, lock >1k + unlock via webhook, trial-once + trialing-can't-double-subscribe, trial-expiry re-locks, `/collect` ingests while locked, side doors (share/export/digest) follow the lock, durable usage marker (no double-count on Redis loss), site-limit at 5 (not 4), webhook idempotency, retention mapping

### Phase 15 — Premium (DEFER until users ask)
**Goal:** upsell features — build only when paying users request them.
- [x] **Custom events + conversion goals** (built) — tracker `flowly('event', name)` + `event_type`/`name` on `/collect`+ClickHouse; stored-only (never metered/live, §1); paid-gated reports (`billing.require_premium` → 402): `GET /events` + goals CRUD/conversions (`routers/goals.py`, `services/goals.py`, Postgres `goals` table); web `/goals` page (`components/goals/goals-report.tsx`, `hooks/useGoals.ts`, nav under Behavior)
- [ ] Custom dashboards
- [ ] Custom segments / cohorts
- [ ] Funnels + user-flow / path analysis
- [ ] Retention reports
- [ ] Public API access (`routers/`)
- [ ] Integrations (Slack alerts)
- [ ] White-label / remove branding
- [ ] Team seats + roles

### Parked — decided against for now (do NOT build without revisiting the decision)
- **New vs returning visitors** — requires cross-day identity; conflicts with the daily-rotating `visitor_hash` promise (§2, §9 privacy). A product/privacy decision, not a task.
- **404 / broken-page tracking** — client-side JS can't reliably read the document's HTTP status; brittle from a snippet.
- **Page load time / Core Web Vitals / JS error tracking** — needs new tracker event types + `/collect` shape; JS errors are a PII risk (stack traces/URLs) and would need scrubbing to honor §9.
- **Paid keyword research (volume/difficulty suggestions)** — needs a paid third-party keyword API; out of the privacy-first analytics lane.

---

_Last updated: 2026-07-07 — **Phase 14 (Pricing v2 — graduated metered billing + paywall + 5-site limit) built.** Replaced the flat plans with usage-priced billing, reusing Phase 7's Stripe/webhook/metering. **Entitlement → free vs metered** (`billing.effective_plan`, derived from `status`; new accounts start free — trial moved to upgrade, once per account). **Paywall:** `usage_summary` emits `status:"locked"` past `FREE_MONTHLY_VIEWS` (1k); typed **402 `AccountLockedError`** (`code:"account_locked"`, via a new `AppError.code`/web `ApiError.code`) enforced by a router-level dep on all `/stats/*` (incl. CSV export) + the live WS; web `components/PaywallGate.tsx` mounts a **non-dismissible** `PaywallModal` (CTA → metered Checkout w/ 7-day trial). **`/collect` is NEVER gated (§9)** — `test_collect_still_ingests_while_locked` asserts 202 while locked. **Side doors follow the lock:** public share data 402 (meta open), export via the stats dep, weekly digest skips locked accounts. **Stripe metered:** ONE graduated Price (`STRIPE_PRICE_METERED`); `report_usage_to_stripe` pushes the **delta** (additive meter events) from a **durable Postgres high-water mark** (migration `c3d4e5f6a7b8`) → new `workers/usage_report.py` (cron hourly); webhooks stay the only entitlement writer. **5-site cap** (`SiteLimitError` 403, service-enforced; web hides Add at 5). Retention free 30d / metered 365d. Config dropped `PLAN_QUOTAS`/`HARD_CEILING`/4 flat prices; added `FREE_MONTHLY_VIEWS`/`MAX_SITES_PER_ACCOUNT`/`stripe_price_metered`/`stripe_meter_event`. **Post-review hardening (2 pre-go-live billing fixes):** (1) Checkout blocks any **entitled** account incl. an in-window **trialing** one (`effective_plan==metered`) — the old active/past_due-only guard let a trialing user double-subscribe; (2) the usage-push high-water mark moved Redis→**Postgres** (`subscriptions.metered_usage_reported`/`metered_usage_period`) so an evicted marker can't re-push a whole month and Stripe's additive meter can't **double-bill** (§9). Pricing math single source stays `lib/pricing.ts` (boundary bills 10k→$8.91/100k→$17.91/1M→$62.91, Vitest-pinned). **316 backend tests pass** (rewritten `test_billing_{service,router}`; new `test_paywall.py`; durable-marker + trialing-double-subscribe regressions), ruff clean, single Alembic head; web lint + tsc + build green (routes unchanged), 9 Vitest pass. **Manual before deploy:** `alembic upgrade head` (`c3d4e5f6a7b8`), create the Stripe metered Price + Billing Meter, set `STRIPE_PRICE_METERED`/`STRIPE_METER_EVENT`, wire `app.workers.usage_report` to an hourly cron, live Checkout→webhook→meter smoke (`stripe listen`). **Phase 13 (Search Console integration — keywords & SEO) built.** Surfaces the customer's own GSC search keywords, average position, and opportunity keywords. **Backend:** a **separate offline-access OAuth flow** (reuses `GOOGLE_CLIENT_*` with `webmasters.readonly` + `access_type=offline`/`prompt=consent`; sign-in stays online) — authed `POST /searchconsole/{site_id}/connect` returns the consent URL + binds a Redis `state → (account, site)`; public `GET /searchconsole/callback` exchanges the code, auto-matches the site's domain to a verified GSC property (prefer `sc-domain:`), stores the **refresh token** (never logged/returned, §9). Two new Postgres tables (migration `b2c3d4e5f6a7`): `search_console_connections` + `search_metrics` — **Postgres not ClickHouse** (external, low-volume, daily; per-(site,day) idempotency = clean delete-reinsert). `services/gscapi.py` (pure Google httpx layer — **no new dep**) + `services/searchconsole.py` (connect/sync/reports: impression-weighted avg position, derived CTR, opportunities = position 5–20 by impressions) + `workers/searchconsole.py` (daily, best-effort, tokens never logged). Authed ownership-scoped `keywords`/`pages`/`opportunities`/`sync`/`disconnect` endpoints. **Frontend:** `hooks/useSearchConsole.ts`, `components/searchconsole/search-report.tsx` (connect empty-state → consent; clicks/impressions/CTR/position table; sync-now/disconnect; `?gsc=connected|error` toast), three `/search-console/*` pages, new "Search Console" nav group. 296 backend tests pass (new `test_searchconsole.py`, 13), ruff clean; web lint + tsc + build green (+3 routes), 9 Vitest pass, grep gate holds. **Manual:** register `{API_BASE_URL}/searchconsole/callback` in the Google client; live-verify needs real creds + a verified property (tests mock the GSC API). **Deferred:** property picker for multi-property accounts; refresh-token encryption-at-rest; metrics→ClickHouse at scale. **Phase 12 (uptime monitoring & down alerts) built.** A cron-driven pinger checks each site and emails the owner on down / recovery. **Backend:** additive migration `a1b2c3d4e5f6` (two new tables — `uptime_monitors` 1:1 per site with the `fail_streak` that powers retry-before-alarm, `uptime_incidents` whose open `resolved_at IS NULL` row is the alert-idempotency key; applied + downgrade-verified on dev Postgres + SQLite migration test). `services/uptime.py` = the check (`check_domain`/`check_with_retry`, GET/HEAD `https://{domain}` via existing httpx, in-run retry blip filter; down = timeout/connect/DNS/5xx, any <500 = up) + the **SSRF guard** (`_screen_host` resolves every request AND redirect hop and refuses any `not ip.is_global` address — loopback/private/link-local incl. 169.254.169.254/reserved/multicast, IPv4-mapped IPv6 unwrapped; redirects followed manually `follow_redirects=False` re-screened per hop, GET/HEAD only; a "blocked" internal target is recorded but never alerts) + the state machine (`process_result` — incident opens only past `UPTIME_FAIL_THRESHOLD`, owner emailed once down + once up, guarded by `notified_down`/`notified_up`, best-effort retry, verified owners only). `sweep()` fans network checks out with bounded concurrency then applies state sequentially on the one AsyncSession. **Alerts are transactional** (`services/email.py::send_uptime_{down,up}_email` → direct `send_email`, **never** `services/notifications.py`'s marketing gate — opted-out owners still get down alerts). `workers/uptime.py` (run-once + cron ~5 min, gated on `UPTIME_ENABLED`, off by default). Read surface `GET /sites/{site_id}/uptime` (authed, ownership-scoped via `owned_site`). 4 new env vars (`UPTIME_ENABLED`/`UPTIME_CHECK_TIMEOUT`/`UPTIME_FAIL_THRESHOLD`/`UPTIME_MAX_REDIRECTS` in `config.py` + `.env.example` + §6), new §7 worker cron; **no new dependency** (SSRF guard is stdlib `ipaddress`/`socket`). **Frontend:** `hooks/useSites.ts::useSiteUptime`, `components/uptime/uptime-panel.tsx` (green/red up/down `Badge` on F0 semantic tokens + recent-incidents list, UTC localized via new `lib/format.ts::formatDateTime`) on the site detail view; new `UptimeIncident`/`UptimeStatus` api types. 283 backend tests pass (new `tests/test_uptime.py`, 25 — down→alert-once, recover→notice, flapping-no-spam, no-marketing-gate, SSRF incl. redirect-to-internal + IPv4-mapped, unverified-not-emailed, blocked≠incident, ownership 404), ruff clean; web lint + tsc + build green (routes unchanged), 9 Vitest pass, grep gate holds. **Live-verified end-to-end:** real DNS resolution refuses localhost/127.0.0.1/169.254.169.254/10.0.0.1 (→ blocked) + nonexistent → dns; real HTTP check of example.com → up (200); 127.0.0.1 refused without connecting; full down→alert→recover incident lifecycle against a real DB; `UPTIME_ENABLED` gate returns 0 without pinging. **Manual before deploy:** set `UPTIME_ENABLED=true` + wire `app.workers.uptime` to a ~5-min scheduler; a real `EMAIL_API_KEY` (Resend) for live alert delivery (dev stub logs otherwise). **Known limitation (deferred):** SSRF guard resolves-then-connects → small DNS-rebinding TOCTOU window; acceptable at current scale, harden to IP-pinning if high-volume internet-facing. **Phase F7 (polish + support chatbot) built** (F-track) — completes the F0–F7 frontend redesign track. **Support chatbot (hybrid):** new public `POST /assistant/chat` (`routers/assistant.py` → `services/assistant.py`) answers five hardcoded intents (what-is / pricing / features / policy / contact) from canonical text with **no model call** (works with no key), and only genuinely unmatched questions fall through to a **small/cheap model** (`claude-haiku-4-5`) with a tightly-scoped system prompt of public product facts. **Guardrails (§9-style):** per-IP rate limit (`enforce_rate_limit`, 30/hr), low `max_tokens` (300), single-message context, **zero access to user/analytics data** (the AI only ever sees the visitor's message + fixed facts), system prompt forbids inventing pricing and routes unknowns to /contact; with no `ANTHROPIC_API_KEY` the fallback is a canned contact line (graceful degrade — the bot never fails). New dep **anthropic** (official async SDK, §5) called lazily/key-gated; new env var `ANTHROPIC_API_KEY` (`.env.example` + §6). Canonical answers mirror the `content/faq.ts` single source (hand-synced across the TS/Python boundary; the widget also surfaces the FAQ questions as suggested prompts). Frontend: floating `components/ChatWidget.tsx` (toggle + panel, message list, FAQ suggestion chips, typing state, reduced-motion-safe) driven by `hooks/useAssistant.ts`, mounted in the marketing layout (all marketing pages). **Polish:** added a success toast to the site-creation mutation (`(dashboard)/sites`), completing toast feedback on mutations (auth/settings/share already had toasts); the components are built responsive + accessible (token focus-visible rings, aria labels) — a dedicated mobile/contrast visual audit remains the manual step. 228 backend tests pass (new `test_assistant.py`: intent matching, FAQ answers, off-topic→fallback, 422, rate-limit 429), ruff clean; web lint + tsc + build green (25 routes), 7 Vitest pass, grep gate holds; live-verified — `/assistant/chat` returns FAQ answers + contact fallback on the running API, widget builds and mounts. **Manual steps left:** set a real `ANTHROPIC_API_KEY` to enable the AI fallback (hardcoded FAQ works without it), and the dual-theme / mobile / a11y visual pass across the F-track. **Phase F6 (footer + static pages) built** (F-track): the trust layer. **Backend (one new endpoint):** public `POST /contact` (`routers/contact.py` → `services/contact.py`) — honeypot field (`company`; bots fill it → silent drop, returns 204 so it can't tell) + per-IP rate limit (`enforce_rate_limit`, 3/hour) + **transactional** delivery via `send_email` (NOT the marketing opt-out gate; dev-stub logs with no key), sent to `settings.email_from` with the sender's address in the body (no new env var). `ContactRequest` added to `models/schemas.py`; router registered in `main.py`. **Frontend:** rich `components/marketing/footer.tsx` (Product / Company / Legal columns + X/GitHub/LinkedIn inline-SVG brand marks in `currentColor` — brand assets, exempt from no-raw-hex — + a "Powered by Flowly" pill), replacing the F1 placeholder; slim in-app `components/layout/app-footer.tsx` wired below `<main>` in the dashboard shell (© + Privacy/Terms/Contact). New static pages on a shared `components/marketing/prose-page.tsx` (`ProsePage`/`ProseSection`): **`/terms`** (new ToS — charging without terms was a gap), **`/about`**, and **`/privacy` restyled** onto the same layout. **`/contact`** page (client) — `Field`+`Textarea` (new `components/ui/textarea.tsx`) form that hands off **keyless** to the visitor's own mail app (`mailto:`) or WhatsApp (`wa.me`), destinations in `lib/contact.ts` (`CONTACT_EMAIL`, `WHATSAPP_NUMBER` — empty hides the WA button); no email provider needed. The server `POST /contact` endpoint + `hooks/useContact.ts` stay in place (unused) for when a Resend key is configured. **Email delivery note:** `send_email` still dev-stubs unless `EMAIL_API_KEY` is set AND env≠local; contact submissions are addressed to `CONTACT_EMAIL` (backend config, defaults to `EMAIL_FROM`) once a provider is wired. **Custom 404** `app/not-found.tsx` (centered, links home + dashboard). Marketing nav "Pricing" already repointed in F5; footer links surface About/Contact/Terms. **No new deps, no new env vars, no migration.** 222 backend tests pass (new `test_contact.py`: valid-sends / honeypot-drops / 422 / rate-limit), ruff clean; web lint + tsc + build green (27 routes — `/about`,`/contact`,`/terms` added, custom `/_not-found`), 7 Vitest pass, grep gate holds; `/about`,`/contact`,`/terms`,`/privacy` serve 200, unknown routes → 404, and live `POST /contact` → 204. Manual dual-theme / mobile visual pass is the remaining step. **Phase F5 (billing UI) built** (F-track): billing surfaces oriented to the Phase 14 metered model, all consuming `lib/pricing.ts` (the ONE pricing truth — same graduated integer-cents math the F1 slider uses). **Billing page** (`app/(dashboard)/billing/page.tsx`) rewritten: a usage meter (used pageviews + status-colored bar) + a prominent **month-to-date bill estimate** (`estimateMonthlyBill(used)` → `formatUsd`) with the "first 1,000 free · rate falls as you scale" framing + a `/pricing` link; a "Pay as you go" upgrade card whose CTA opens the new **`PaywallModal`**; and a Customer-Portal link (invoices/card/cancel). Replaced the Phase 7 flat Pro/Business monthly-annual plan cards (Phase 14 decommissions flat plans, so re-skinning them would be throwaway) — checkout now flows through the PaywallModal. **`components/PaywallModal.tsx`** (new): a Dialog with the metered pitch + the reused F1 `PricingSlider`, CTA → `useCheckout` (interim flat `{tier:"pro",interval:"monthly"}` so it stays functional; commented for the Phase 14 swap to the single metered Price + trial). Has a `dismissible` prop (default true) — Phase 14 sets it false to make the hard `locked` wall non-escapable (blocks Escape/outside-click) and mounts it over the dashboard on the 402. **`components/UsageBanner.tsx`** reworked into three usage_summary-driven states: free-approaching → amber warning, free-over/`locked` → red upgrade nudge, paying-with-usage → a quiet month-to-date **bill-estimate** strip (only past the free allotment, so no `$0` noise). `UsageSummary.status` gained `"locked"` in `lib/api.ts` (Phase 14 emits it; the UI renders its branch already, so Phase 14 is a backend-only flip). **`/pricing` marketing page** (`app/(marketing)/pricing/page.tsx`, new) reuses the F1 `Pricing` section (graduated table + `PricingSlider`) + FAQ + final CTA; the marketing nav "Pricing" link repointed from the `/#pricing` landing anchor to the dedicated page. **No lock enforcement yet** (402 gating is Phase 14) — everything renders from `usage_summary` flags; no new deps, no new env vars, no backend change. Web lint + tsc + build green (25 routes, `/pricing` added), 7 Vitest pricing-boundary tests still pass, grep gate holds; `/pricing` + `/billing` serve 200 on the running dev server. Manual dual-theme / mobile visual pass (esp. the PaywallModal + slider) is the remaining step. **Phase F4 (dashboard redesign) built** (F-track): the authed dashboard re-rendered premium on the F1 reports kit — **no backend/data changes**. The `components/reports/` kit (StatCards + CountUp, TrafficChartCard, BreakdownCard/PagesCard with indigo share bars + "View all", `row-icon` favicons/flags/device icons, LiveDot) — previously only the public share page used it — now also drives the authed dashboard, fed from the authed `hooks/useStats.ts` instead of the public/token hooks. New shared authed composition: `lib/range.ts` (`rangeForDays` + `RANGE_PRESETS`, deduped from the old per-page copies; public-dashboard keeps its own), `components/layout/range-context.tsx` (`RangeProvider`/`useRange()` mounted in the dashboard layout → the 24h/7d/30d preset persists across report destinations, window frozen per preset), `components/dashboard/report-shell.tsx` (`ReportShell` — active-site + loading/no-site gating with install CTA, title row, shared `RangeTabs`, render-prop `actions(siteId)` + `children(siteId)`), `components/dashboard/overview.tsx` (`OverviewReport` — animated StatCards + TrafficChartCard + summary Sources/Countries/Top-pages cards whose "View all" **routes** to the matching sidebar destination + UtmCard + ShareControl; loaded-but-empty → "No data yet — install your snippet" EmptyState), and `components/dashboard/report-views.tsx` (`AudienceReport`/`PagesReport`/`ReferrersReport`/`CampaignsReport`, limit 25, TableSkeleton while loading). **Each Phase-5-backed report is now a real sidebar destination** — `lib/navigation.ts` flips `ready:true` for Behavior (Pages/Entry/Exit → `/pages?kind=`), Acquisitions (Referrers → `/sources`, Campaigns → `sources.utm`), Geographic (Countries → `/audience?dimension=country`), Technology (Browsers/OS/Devices → `/audience?dimension=`) with a thin route page each under `app/(dashboard)/{behavior,acquisitions,geo,tech}/…`; Channels/Search/Social/AI-platforms/Cities/Languages/Screens stay `ready:false` (need the unbuilt Phase 10/11 backends). Overview page rewritten to `ReportShell` + `OverviewReport` (keeps Export CSV via a `useRange`-bound button in the `actions` slot). **Live polish** (`components/live.tsx`): the connected dot is now the pure-CSS pulsing `LiveDot` (`#10B981`, reduced-motion-safe) and feed items animate in (`animate-in fade-in slide-in-from-top-2`, `motion-reduce:animate-none` — only the newly-prepended keyed row mounts/animates). Old `components/stats.tsx` (table-based, F0-era) **deleted** (its sole consumer, the dashboard page, migrated). No new deps, no new env vars, no backend change. Web lint + tsc + build green (24 routes; 9 new report destinations), 7 Vitest tests pass, grep gate holds; all dashboard routes serve 200 on the running dev server. Manual dual-theme / mobile / reduced-motion visual pass is the remaining step. **Phase F3 (user profile / settings) built** (F-track): new authed **account settings** surface. Backend: `services/account.py` + `routers/account.py` (prefix `/account`, registered in `main.py`) — `GET /account/identities` (linked OAuth logins, `provider`/`created_at` only — never `provider_user_id`), `PUT /account/email-preferences` (toggles the existing `email_opt_out` column — the in-dashboard mirror of the signed unsubscribe link, no token needed since authed), `POST /account/change-password` (verifies current via argon2, 422 for OAuth-only no-password accounts), two-step **change-email** `POST /account/change-email` → `POST /account/verify-email-change` (re-auths with password, emails a 6-digit code to the NEW address via the existing Redis code flow under a new `"email_change"` purpose + matching `CODE_MESSAGES`/`CODE_SUBJECTS` entries in `services/email.py`; step 2 verifies the code then switches the email, flush-guarded to a clean 409 on a raced duplicate), and `POST /account/delete` (password-re-auth; wipes each site's ClickHouse events via new `retention.build_delete_all_query`/`delete_all_for_site` — full-site `ALTER TABLE events DELETE WHERE site_id`, no `ts` predicate — evicts the Redis `site:{site_id}` map via new `billing.uncache_site_account`, then deletes Postgres children in FK order (share_tokens→sites, identities, subscription, onboarding_emails) and the account; ClickHouse/Redis best-effort so a storage hiccup can't strand the account half-deleted). `AccountOut` gained `email_opt_out` + derived `has_password` (built via new `AccountOut.from_account`; `GET /auth/me` updated) so the UI can hide the change-password form for OAuth-only accounts; new `IdentityOut`. **No new migration** (derived fields only), **no new backend dep**. Frontend: `app/(dashboard)/settings/page.tsx` (Profile card w/ username + email + plan badge, Password card, Email-preferences `Switch`, Linked-accounts list, red Danger-zone) composed from `hooks/useAccount.ts` (`useIdentities`/`useChangePassword`/`useRequestEmailChange`/`useVerifyEmailChange`/`useEmailPreferences`/`useDeleteAccount` — mutations write fresh `AccountOut` straight into the `["me"]` cache; delete tears down tokens+cache then redirects to `/sign-in`) + two stateful dialogs `components/settings/{change-email-dialog,delete-account-dialog}.tsx` (delete guarded by a typed "DELETE" confirmation + password). New shadcn `components/ui/switch.tsx` (Radix Switch, already-installed `radix-ui` package — no new dep). `Account` type gained `email_opt_out`/`has_password`, new `Identity` type. "Settings" added to the sidebar Workspace group (`lib/navigation.ts`) + the header user menu (`app-header.tsx`). **No new env vars.** 218 backend tests pass (new `test_account.py`: auth-required on every route, wrong-current-password 401, OAuth-only change-password 422, email-preferences round-trip via `/auth/me`, full change-email code flow, taken-email 409, delete wipes both Postgres rows + site-scoped ClickHouse events + stale-token 401), ruff clean; web lint + tsc + build green (15 routes, `/settings` added), 7 Vitest tests pass, grep gate holds. **Roadmap:** **Frontend redesign track F0–F7 added**; **motion rule added** (Framer Motion, subtle scroll-reveal/stagger/count-up, `prefers-reduced-motion`-safe — §5 gained Framer Motion); **public share page = phpAnalytics-reference styled, doubles as the animated landing hero**; **Phase 10 channel classifier gained an AI-platforms bucket** (ChatGPT/Perplexity/Claude referrals); **demo-video design reference reviewed and encoded** (dark-first landing layout: badge-pill hero with accent-highlighted headline + framed dashboard centerpiece, icon-card features, sparing accent use; full dual-theme rule — marketing + dashboard, system default with dark fallback) (design system foundation: indigo `#6366F1` tokens + shadcn/ui + app shell → landing page with live-demo hero + pricing slider → auth pages incl. missing verify/reset → settings/profile incl. delete-account → dashboard redesign on the phpAnalytics-style sidebar IA → billing UI incl. PaywallModal → footer/Terms/About/Contact/404 → polish + hybrid FAQ chatbot with Claude-API fallback, hard guardrails, built last); §5 gained shadcn/ui + next-themes. Backend feature Phases 10–14 added (query-layer reports & filtering; city/language/live-map + first ClickHouse migration convention; uptime monitoring & down alerts; Search Console keywords/SEO; **Pricing v2 — graduated metered billing REPLACING the flat plans: 1k free / $0.99 per 1k to 10k / $0.10 per 1k to 100k / $0.05 per 1k to 1M / $0.03 beyond, views summed account-wide across all (max 5) sites, dashboard paywall modal when a free account passes 1k (ingestion never blocked, §9)**); old deferred Phase 10 renumbered to **15** (Search Console removed from it — now Phase 13) and a **Parked** list records what we decided against (new-vs-returning, 404 tracking, CWV/JS errors, paid keyword research). Phases 0–9 untouched. Build note history: Phase 8 (growth & retention) + Phase 9 (privacy & trust) built. **Shared email prereq:** `services/email.py` now delivers via **Resend** (a single httpx POST in `_send_via_provider`; still dev-stub-logs in local/no-key) with an optional HTML body; new `services/notifications.py` is the **marketing gate** — `send_marketing_email` refuses opted-out accounts and appends a signed one-click unsubscribe footer, `marketing_recipients` lists verified+not-opted-out accounts, `apply_unsubscribe` flips the flag; `accounts.email_opt_out` column + `create_unsubscribe_token` (new `unsubscribe` JWT type, 10y) + public `routers/email.py` `GET /email/unsubscribe`. Transactional mail (verify/reset, trial-ending) never routes through the gate. **8.1 digest:** `services/digest.py` builds a per-site trailing-week summary by reusing the Phase 5 stats services (no bespoke SQL) → `render_digest` (subject/html/text); `workers/digest.py` (run-once, cron weekly) iterates recipients, skips zero-traffic, sends via the gate, and marks `digest:{account_id}:{ISOyearweek}` in Redis (10-day TTL) for idempotency. **8.2 share + 8.3 badge:** `models.tables.ShareToken` (secret `token_urlsafe`, FK to site pk, soft `revoked_at`) + `services/sharing.py` (create=rotate revokes prior, `resolve_share` only returns live tokens, single-site scope); authed create/rotate/revoke on `routers/sites.py` (`/sites/{id}/share`), **public** `routers/public.py` (`/public/{token}/…`) reuses the stats services with a token gate replacing bearer auth (404 on unknown/revoked before any query) — `GET /public/{token}` returns `{domain, show_badge}` where `show_badge = effective_plan==free`; web `app/share/[token]` read-only dashboard (`hooks/usePublicStats.ts`, unauth `publicFetch`) + `components/{PoweredByBadge,ShareControl}.tsx`. Shared `core/timerange.py::stats_range` extracted from `routers/stats.py` so both stats + public routers use one window parser. **8.4 onboarding:** `models.tables.OnboardingEmail` ((account,step) unique ledger) + `services/onboarding.py` (welcome/install/live content + `already_sent`/`record_step`); `workers/onboarding.py` (run-once, cron hourly) advances each account — welcome once, `live` on first event (`sites.first_event_seen`), `install` nudge only if dark after 24h (and marked-without-emailing once live). `trial_will_end` wired via `billing.on_event_committed` (post-commit, best-effort transactional email) called from the webhook router. **9.1 retention:** `config.RETENTION_DAYS` (free 30 / pro 365 / business 730) + `services/retention.py` (pure `(sql,params)` site-scoped `ALTER TABLE events DELETE WHERE site_id AND ts<cutoff`, cutoff from `effective_plan` so a lapsed trial ages out at 30d) + `db/clickhouse.py::run_command`; `workers/retention.py` (run-once, cron daily) sweeps every site, logs each cutoff (destructive by design, §7). `events` was already `PARTITION BY toYYYYMM(ts)` so no CH schema change. **9.2 export:** `services/export.py` (aggregated reports only — never raw events, no `visitor_hash`/IP) + `GET /stats/export` (authed, `owned_site`+`stats_range`, `text/csv` download). **9.3 privacy:** static Server Component `app/privacy` + landing-page link. **billing hardening:** `effective_plan`/onboarding now coerce a naive stored `trial_ends_at`/`created_at` to UTC (§4) so a mixed-awareness read can't raise (prod asyncpg is already aware; guards the SQLite test path). Migration `f3a9c1d47b20` (batch-mode): `email_opt_out` + `share_tokens` + `onboarding_emails`; applied + downgrade-verified on dev Postgres, single head. **No new deps** (Resend rides existing httpx), **no new env var** (`EMAIL_API_KEY`/`EMAIL_FROM` already present). §7 gained the three worker cron commands. 206 backend tests pass (new `test_notifications`/`test_sharing`/`test_public_router`/`test_digest`/`test_onboarding`/`test_retention`/`test_export`/`test_billing_trial`, extended `test_migration`); web lint + tsc + build green (new `/privacy`, `/share/[token]` routes). Live Resend + Stripe smoke and wiring the three workers to a real scheduler are the manual steps left. Phase 7 post-review hardening: (1) removed the dead `resolve_account_id` (nothing called it; its "self-heals from Postgres" promise was never wired) — the site→account map is now honestly documented as write-once at `create_site`, and a lost best-effort write just under-counts that site until re-saved (never blocks ingestion); `meter_pageview` now debug-logs a cold miss. (2) `create_checkout_session` reuses a known `stripe_customer_id` and **refuses** checkout for an already active/past_due account (402 → use the portal), closing a duplicate-customer / double-subscription hole; it now takes a session. (3) webhook `_account_from_event_object` guards the `UUID(metadata)` parse so a malformed id can't 500-loop Stripe retries. (4) `/script.js` returns 404 (not 500) when the tracker isn't built. Ruff check+format clean; 167 backend tests pass (added checkout-guard + Redis-only cache round-trip tests). Phase 7 build note follows. Phase 7 (billing & usage metering) built: trial converts to paid, metered by pageviews. **Split of truth:** Stripe = entitlement, Redis = usage, Postgres = durable mirror. `services/billing.py` holds the metering half (`record_usage`/`meter_pageview` → `INCR usage:{account_id}:{YYYYMM}` + 45-day TTL; Redis-only `cached_account_id` on the hot path so `/collect` stays off Postgres — the `site:{site_id}→account_id` map is written by `create_site`; `resolve_account_id` warms it from Postgres on a cold miss) plus read-time entitlement: `effective_plan` derives the tier (active/past_due/in-window-trial → `account.plan`, else `free`), so a **lapsed card-free trial or canceled sub downgrades to `free` with no webhook/job**; `usage_summary` → `{plan,quota,used,pct,status: ok|warning(≥80%)|over(≥100%)}`; `over_hard_ceiling` (3× quota) is a runaway guard, **not** enforced on the hot path (would need a Postgres read per event — burst cost is bounded by the Phase 3 rate limit instead). Soft cap: data is **never dropped at the quota** (§9). Stripe half: `create_checkout_session` (mode=subscription, `trial_end=trial_ends_at` pass-through so no double-trial/early-charge, account id in `client_reference_id` + subscription metadata), `create_portal_session` (402 `BillingError` if no customer), `verify_webhook` (sync signature check), and `apply_subscription_event` — **the ONLY writer of entitlement** (never the redirect, §10): `subscription.created|updated` → set `account.plan/status` + upsert `subscriptions` (price/customer/sub id, `cancel_at_period_end`, `current_period_end`), `deleted` → `free`/`canceled`, `invoice.payment_failed` → `past_due` (keeps serving), `trial_will_end` → nudge no-op; account resolved via subscription metadata (order-independent) or `stripe_customer_id`. `routers/billing.py` (thin): authed `POST /billing/checkout`, `POST /billing/portal`, `GET /billing/usage`; **public** `POST /billing/webhook` — verify sig (bad → 400 `WebhookSignatureError`) → dedupe via `processed_stripe_events` (event_id PK) → apply + insert id in one transaction (IntegrityError on a raced redelivery → idempotent ack). New `BillingError` (402) in `core/exceptions.py`; the webhook's bad-signature 400 is a router-local `WebhookSignatureError`. Metering hooks into `services/ingest.py` best-effort after the durable XADD (only counted events; bots/rate-limited already returned). Migration `c7f1b2f13d02` (batch-mode): `subscriptions.stripe_price_id` + `cancel_at_period_end`, new `processed_stripe_events` table + `ProcessedStripeEvent` model; applied + downgrade-verified on dev Postgres. `config.py` gained the Stripe block (secret/webhook/4 price ids) + `PLAN_QUOTAS` (`free 10k / pro 100k / business 1M`, placeholders) + `HARD_CEILING_MULTIPLE=3`. Frontend: `hooks/useBilling.ts` (`useUsage`/`useCheckout`/`usePortal`), `components/UsageBanner.tsx` (amber ≥80% / red ≥100% nudge, injected in the dashboard `layout.tsx` — the only shared chrome; never blocks), `app/(dashboard)/billing/page.tsx` (plan + usage bar, monthly/annual upgrade → Checkout, Customer Portal, `?checkout=success|cancel` return), and a "Billing" dashboard link. New dep **stripe** (15.3.0); new env vars `STRIPE_PRICE_PRO_ANNUAL`/`STRIPE_PRICE_BUSINESS_ANNUAL` (in `.env.example` + §6). 165 backend tests pass (`test_billing_service`, `test_billing_router`, extended `test_ingest`/`test_sites_service`/`test_migration`); web lint + tsc + build green. Live Stripe smoke (Checkout/Portal/webhook via `stripe listen`) is the one manual step left. Phase 6 hardening note follows. Phase 6 hardening (post-review): (1) **duplicate-domain race** closed — the `sites` table gained a `UniqueConstraint("account_id", "domain", name="uq_site_account_domain")` (migration `4962f38126db`, down-rev `0b5153c24ddf`, batch-mode so it runs on SQLite too), and `services/sites.py::create_site` now wraps its `commit()` in a `try/except IntegrityError → ConflictError` (mirrors `auth.py::signup`) so a lost race surfaces a clean 409, not a 500; the pre-check `SELECT` stays as the friendly fast path. (2) **`/sites` is now a manage screen** — `app/(dashboard)/sites/page.tsx` lists existing sites (each with an "Open" → reuses `InstallStep`, now with a "← All sites" back link) above the add form, keeping the app's URL-free in-page-state convention (no dynamic route); the dashboard header link is relabelled "Sites". Migration applied + downgrade-verified on dev Postgres (no existing dupes); 133 backend tests pass (new `test_duplicate_domain_race_caught_by_db_constraint`); web lint + tsc + build green. Phase 6 note follows. Phase 6 (site onboarding) built: a user can add a site, get an install snippet, and watch it flip waiting→connected. `core/urls.py::normalize_host` was extracted from `services/ingest.py::_host` (now imported by both ingest + sites) — it stays **non-raising** (fail-open, so `/collect` can't break) and now handles **bare-domain** input (`example.com`; `urlparse` needs a `//` prefix or its `netloc` is empty). `services/sites.py` gained `create_site` (normalize domain → `ValidationError` if empty; account-scoped duplicate-domain → `ConflictError`; `secrets.token_hex(8)` `site_id` with a 3-try collision retry backed by the `UNIQUE` index), `first_event_seen` (Redis `count_active` first for an instant signal, else a server-parameterized ClickHouse `SELECT 1 … LIMIT 1` existence probe — durable, no new column), `build_snippet` (from new `TRACKER_SCRIPT_URL` in `config.py`), and the canonical `to_site_out` (attaches the computed `snippet`, never `model_validate`). New `routers/sites.py` (`prefix="/sites"`): `GET /sites` (moved out of `live.py`), `POST /sites` (201), `GET /sites/{site_id}`, `GET /sites/{site_id}/status` — the per-site routes use a **path-param** `owned_site` dep (404 before any Redis/CH query, §9). `domain` is a cosmetic label (events scoped by `site_id`, not origin — enforcement deferred). Frontend: `hooks/useSites.ts` gained `useCreateSite` + `useSiteStatus` (polls, stops on connected and after a ~3-min cap + manual re-check), `components/install.tsx` (snippet copy-box + per-platform tabs + status pill), `app/(dashboard)/sites/page.tsx` (add-domain → install two-step), and "Add site" CTAs on the dashboard/live empty states. `SiteOut` gained a required `snippet`; `SiteCreate`/`SiteStatus` added. No new migration (schema unchanged), no new dep; one new env var (`TRACKER_SCRIPT_URL`, already in `.env.example`). 132 backend tests pass (incl. `test_urls.py`, `test_sites_service.py`, extended `test_sites.py`); web lint + tsc + build green. Phase 5 note follows. Phase 5 (historical dashboard metrics) built: `services/stats.py` holds pure `(sql, params)` query-builders + a shaping service — overview (visitors/sessions/pageviews/bounce/avg-duration) with prior-period compare, time-series (hour/day buckets auto-picked from range length, gaps zero-filled in Python), sources+UTM, audience (country/device/browser/os), and pages (top/entry/exit). Sessions/bounce/duration are derived in SQL from a 30-min `visitor_hash`+`ts` gap via `_SESSIONIZED_CTE` (`lagInFrame` → session starts → running sum); there is no `session` column. All ClickHouse SQL is **server-parameterized** (`{site_id:String}`) — no user value string-formatted in (§9). `db/clickhouse.py` gained a raw `query_rows` read helper. `routers/stats.py` exposes `/stats/{overview,timeseries,sources,audience,pages}`, each gated by the `owned_site` dependency that verifies ownership (→ 404) **before** any query. Ownership (`get_owned_site`/`list_account_sites`) was extracted from `services/live.py` into shared `services/sites.py` (live + tests updated). Frontend: `hooks/useStats.ts` (TanStack Query, keyed by endpoint+site+range), `components/stats.tsx` (metric cards + Recharts line chart + sources/audience/pages/UTM tables), and `app/(dashboard)/dashboard/page.tsx` (site picker, 24h/7d/30d presets, audience/pages tabs). New dep: **recharts** (already in §5). No new env var (`SESSION_TIMEOUT_SECONDS=1800`, `MAX_RANGE_DAYS=372` are constants). Cookieless caveat: daily `visitor_hash` rotation over-counts multi-day unique visitors (accepted tradeoff). 102 backend tests pass; web lint + tsc + build green. Phase 4 (live) note follows. Phase 4 (real-time live traffic) built: `services/live.py` holds the presence ZSET + pub/sub — `mark_active` pipelines `ZADD active:{site_id}` + stale eviction + key `EXPIRE` (bounded with no viewer), `count_active` evicts-then-`ZCARD`, `publish_event` fans to `live:{site_id}`, and `subscribe_events` owns a per-connection pub/sub (with an `on_ready` hook so the WS subscribes before sending its count snapshot). `services/ingest.py` calls `live.record_and_publish` (presence + publish in one pipeline) best-effort right after the `XADD` (never blocks/fails `/collect`; forwarded payload is IP-free and hash-free). `routers/live.py` serves `WS /live/{site_id}` — accept → Origin check → `?token=` verify (`decode_token`) → site-ownership on a short-lived session → subscribe → snapshot → forward/heartbeat/receiver tasks, all rejections `close(1008)` — plus a read-only ownership-scoped `GET /sites` (thin borrow from Phase 6) and the `SiteOut` schema. Frontend: `hooks/useLiveTraffic.ts` (native WebSocket, capped feed, backoff reconnect, one token-refresh retry on 1008), `hooks/useSites.ts`, `components/live.tsx`, and `app/(dashboard)/live/page.tsx` (auto-guarded, site picker, remount-per-site via key). No new dep, no new env var (`LIVE_WINDOW_SECONDS=300` is a constant). 72 tests pass. Phase 3 (ingestion), Phase 2 (tracker), Phase 1 (auth) previously built. Keep this date current whenever the stack or rules change._
