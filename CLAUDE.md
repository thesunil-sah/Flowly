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
accounts        id, email (unique), password_hash, plan, trial_ends_at, created_at
sites           id, account_id (FK), site_id (public, unique), domain, created_at
subscriptions   id, account_id (FK), stripe_customer_id, stripe_subscription_id,
                status, plan, current_period_end
```

**ClickHouse (analytics — append-only, queried by `site_id`):**
```
events          site_id, ts (UTC), path, referrer, source, utm_source, utm_medium,
                utm_campaign, country, region, device, browser, os, visitor_hash, screen_w
```

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
| Background work | FastAPI tasks / a worker reading **Redis Streams** | Celery (overkill now) |
| Billing | **Stripe** (Checkout + Customer Portal + webhooks) | manual invoicing |
| Email | a transactional provider (Resend / Postmark) | your own SMTP |
| Python tooling | **uv**, **Ruff**, **pytest** | pip + venv by hand |
| Frontend | **Next.js (App Router)**, **TanStack Query**, **Recharts**, **Tailwind** | CRA, Redux for server state |
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
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_BUSINESS` |
| Email | `EMAIL_API_KEY` |
| Tracking | `VISITOR_SALT_SECRET` (seed for the daily salt), `TRACKER_SCRIPT_URL` |

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
- **Frontend:** Vitest for units; a Playwright test for the onboarding flow (sign up -> install -> first data -> upgrade) is worth it once Phase 4 lands.
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

## Features — build checklist (feature-wise micro-tasks)

Build top-down; finish a phase before starting the next. Each feature notes **where** it is built.

### Phase 0 — Foundations & setup
- [ ] **Monorepo + tooling** (repo root)
  - [x] Root `package.json` + `pnpm-workspace.yaml` (`apps/*`)
  - [x] `.gitignore`, `.env.example`, root `README.md`
- [ ] **Backend bootstrap** (`apps/api`)
  - [x] `pyproject.toml` + `.python-version` (3.12); `uv sync` creates `.venv/`
  - [x] App factory `app/main.py` + settings `app/config.py`
  - [x] Folder skeleton: `routers/ services/ db/ models/ core/ workers/ migrations/ tests/`
  - [x] `GET /health` route
- [ ] **Local services reachable** (Postgres + ClickHouse + Redis running)
  - [ ] Clients: `db/postgres.py`, `db/clickhouse.py`, `db/redis.py`
  - [ ] Confirm each connects via its env-var connection string
- [ ] **Postgres schema + migrations** (`apps/api/app/migrations`)
  - [ ] Alembic init + baseline
  - [ ] Tables: `accounts`, `sites`, `subscriptions` (see Core data model)
- [ ] **Authentication (custom)** (`apps/api/app/services/auth.py`, `routers/auth.py`, `core/security.py`, `apps/web`)
  - [ ] Password hashing util (argon2/bcrypt) in `core/security.py`
  - [ ] `POST /auth/signup` — create account, store `password_hash`
  - [ ] `POST /auth/login` — verify password, issue access + refresh JWT
  - [ ] `POST /auth/refresh` — rotate access token from a valid refresh token
  - [ ] JWT verification dependency in `core/security.py` -> `require_user`
  - [ ] `require_user` applied to every authed router; resolve `user_id -> account` (tenant scoping)
  - [ ] Rate-limit `/auth/login`
  - [ ] Frontend: custom `sign-in/` + `sign-up/` pages calling `/auth/*`
  - [ ] Frontend: store token, attach it in the `lib/` api client, guard `(dashboard)` routes
  - [ ] (Optional, later) social OAuth (Google/GitHub) — defer; it's substantial to build yourself

### Phase 1 — Tracking + ingestion (the core)
- [ ] **Tracking script** (`apps/tracker/src/script.js`)
  - [ ] Read `data-site` (site_id) from the script tag
  - [ ] Send pageview via `navigator.sendBeacon` to `/collect`
  - [ ] Payload: site_id, path, referrer, screen width, language
  - [ ] SPA support: wrap `history.pushState` + listen for `popstate`
  - [ ] Wrap everything in try/catch; fail silently
  - [ ] Build + minify -> `apps/tracker/dist/script.js`; serve from CDN
- [ ] **Collect endpoint** (`routers/collect.py` -> `services/ingest.py`)
  - [ ] `POST /collect`: public, open CORS, returns `202` immediately
  - [ ] Validate payload via Pydantic model in `models/`
  - [ ] Per-site_id rate limiting (`core/`)
- [ ] **Cookieless visitor ID** (`services/visitor.py`)
  - [ ] Hash `IP + UA + daily salt`; never store/log raw IP
  - [ ] Daily salt rotation (Redis `salt:{date}`, 24h TTL)
- [ ] **Bot filtering** (`services/ingest.py`)
  - [ ] UA bot list + heuristics; drop before counting
- [ ] **Buffer + batch writer** (`db/redis.py`, `workers/batch_writer.py`)
  - [ ] Push validated event to `stream:events`
  - [ ] Worker batches the stream + bulk-inserts into ClickHouse
- [ ] **ClickHouse events table** (`db/clickhouse.py` + init script)
  - [ ] `events` schema (see Core data model)

### Phase 2 — Real-time / live (headline feature)
- [ ] **Active users** (`services/live.py`)
  - [ ] On event: `ZADD active:{site_id} {ts} {visitor_hash}`
  - [ ] Count online: `ZCOUNT` last 5 min; evict stale with `ZREMRANGEBYSCORE`
- [ ] **Pub/sub publish** (`services/ingest.py`)
  - [ ] `PUBLISH live:{site_id} {event_json}` on each event
- [ ] **WebSocket endpoint** (`routers/live.py`)
  - [ ] `WS /live/{site_id}` — authed + verify site ownership
  - [ ] Subscribe to the Redis channel, forward to the client
- [ ] **Live dashboard view** (`apps/web/app/(dashboard)/live`)
  - [ ] Live visitor counter, live event feed, current pages list

### Phase 3 — Core dashboard metrics
- [ ] **Stats queries** (`services/stats.py`)
  - [ ] Overview aggregates (visitors, sessions, pageviews, bounce, avg duration)
  - [ ] Time-series for the trend chart
  - [ ] Sources + UTM, audience (geo/device/browser/os), top/entry/exit pages
- [ ] **Stats endpoints** (`routers/stats.py`)
  - [ ] `GET /stats/overview`, `/stats/sources`, `/stats/pages`, etc. — authed + ownership check
- [ ] **Dashboard UI** (`apps/web/components`, `apps/web/hooks`)
  - [ ] Date-range picker + period comparison
  - [ ] Charts (Recharts), metric cards, data tables

### Phase 4 — Onboarding + billing (trial -> paid)
- [ ] **Add-site flow** (`routers/sites.py`, `services/sites.py`, web)
  - [ ] Create site -> generate `site_id` -> store in `sites`
  - [ ] Show the install snippet with their site_id
  - [ ] Install verification: poll for first event, flip "waiting" -> "connected"
- [ ] **Install guides** (`apps/web`)
  - [ ] Snippets for Next.js, WordPress, Shopify, Webflow, GTM
- [ ] **Usage metering** (`services/billing.py`, Redis)
  - [ ] Per-account monthly pageview counter (`usage:{account_id}:{YYYYMM}`)
  - [ ] Limit enforcement + 80% warning
- [ ] **Stripe** (`routers/billing.py`, `services/billing.py`)
  - [ ] Checkout session with 7-day trial
  - [ ] Customer Portal link (manage/cancel)
  - [ ] Webhooks (signed + idempotent): subscription created/updated, `trial_will_end`, payment failed
  - [ ] Annual plan price option
  - [ ] Link Stripe customer -> `subscriptions`

### Phase 5 — Growth & retention (micro-SaaS engine)
- [ ] **Weekly email digest** (`workers/`, email provider)
- [ ] **Public / shareable dashboard** (read-only route + share token)
- [ ] **"Powered by Flowly" badge** on free tier
- [ ] **Onboarding email sequence**

### Phase 6 — Privacy & trust
- [ ] **Retention deletion job** (`workers/`, per-plan window)
- [ ] **CSV export** endpoint (`routers/stats.py`)
- [ ] **Privacy / GDPR page** documenting the cookieless approach

### Phase 7 — Premium (DEFER until users ask)
- [ ] Custom events + conversion goals
- [ ] Custom dashboards
- [ ] Custom segments / cohorts
- [ ] Funnels + user-flow / path analysis
- [ ] Retention reports
- [ ] Public API access (`routers/`)
- [ ] Integrations (Search Console, Slack alerts)
- [ ] White-label / remove branding
- [ ] Team seats + roles

---

_Last updated: 2026-07-01 — Phase 0 scaffold (monorepo, backend bootstrap, `/health`)._
