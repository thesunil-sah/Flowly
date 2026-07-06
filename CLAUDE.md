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
    components/            # reusable UI
      ui/                  #   shadcn/ui kit (copied in) + EmptyState
      layout/              #   app shell: sidebar, header, site-switcher, site-context
      charts/              #   Recharts theme module (CSS-var colors)
    lib/                   # api client (attaches auth token), format.ts, navigation.ts (sidebar IA + ready flags), constants
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
| Geo-IP | **geoip2** (MaxMind GeoLite2-City `.mmdb`) — fail-open | a paid geo API on the hot path |
| Background work | FastAPI tasks / a worker reading **Redis Streams** | Celery (overkill now) |
| Billing | **Stripe** (Checkout + Customer Portal + webhooks) | manual invoicing |
| Email | a transactional provider (Resend / Postmark) | your own SMTP |
| Python tooling | **uv**, **Ruff**, **pytest** | pip + venv by hand |
| Frontend | **Next.js (App Router)**, **TanStack Query**, **Recharts**, **Tailwind v4 (CSS-first — tokens in `globals.css` `@theme`, NO `tailwind.config.ts`)** | CRA, Redux for server state |
| UI components / theming | **shadcn/ui** (copied into `components/ui/`, restyled via the F0 tokens only — never raw hex/gray utilities in components; green/red reserved for live/up/down/error semantics) + **next-themes** (class-strategy light/dark) + **lucide-react** icons + **sonner** for toasts | Material UI, Chakra, Bootstrap, ad-hoc per-page styling, shadcn's deprecated `toast` |
| Animation | **Framer Motion via the `motion` package** (import from `motion/react`; wrappers in `components/motion.tsx`) — subtle, ≤500ms, gated on `prefers-reduced-motion`; hover lifts + live pulse are pure CSS | GSAP, AOS, CSS keyframe soup, scroll-jacking libs |
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
| Web (Next.js — `NEXT_PUBLIC_*` inlined at build; real dev values go in `apps/web/.env.local`, not the repo-root `.env`) | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEMO_SHARE_TOKEN` (share token for the landing page's live-demo hero — public by design; blank → labeled sample data) |
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
- **Frontend:** Vitest for units — set up in F1 (`apps/web/vitest.config.ts`, node env, pure-function tests only; run with `pnpm --filter web test`; first suite: `lib/pricing.test.ts` pinning the advertised graduated-bill boundaries). A Playwright test for the full flow (sign up -> install -> first data -> upgrade) is worth it once onboarding + billing land (Phases 6–7).
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

### Phase 10 — Query-layer reports (existing data — no schema or tracker changes)
**Goal:** richer breakdowns + drill-down, built purely on data already in `events`.
- [ ] Channel classifier (`services/channels.py` or inside `services/stats.py`): bucket `referrer` host → direct / search (Google/Bing/DDG…) / social (X/LinkedIn/Reddit/Facebook…) / referral; expose search-engine + social breakdowns on `/stats/sources`
- [ ] Screen-size / viewport breakdown: width buckets over existing `screen_w` (audience report)
- [ ] Time-of-day / day-of-week heatmap: `toHour(ts)` / `toDayOfWeek(ts)` aggregation (`services/stats.py` + a heatmap panel in `components/stats.tsx`) — **UTC in SQL, user timezone at display only (§4)**
- [ ] Custom date range picker (frontend-only): calendar picker in the dashboard calling the existing endpoints; server already parses arbitrary ranges via `core/timerange.py::stats_range` (bounded by `MAX_RANGE_DAYS`)
- [ ] Dashboard-wide click-to-filter + multi-filter combos (country + device + source stacked): optional filter params threaded into every `(sql, params)` builder in `services/stats.py` (**server-parameterized — never string-formatted, §9**) + filter state in the dashboard; every chart/table re-filters
- [ ] Page detail view: click a page → all reports filtered by `path` (trend, referrers, bounce, avg time) — falls out of the filter work
- [ ] Top-10 pages ranked by traffic and by engagement (bounce / avg time on page, reusing `_SESSIONIZED_CTE`)

### Phase 11 — Small data additions (first ClickHouse schema change)
**Goal:** city, language, and the live map — plus a real migration convention for `events`.
- [ ] **Establish the ClickHouse migration convention first** (Alembic is Postgres-only, §3): ordered, idempotent `ALTER TABLE events ADD COLUMN IF NOT EXISTS …` scripts + how they run in dev/prod; document it in §3 in the same change
- [ ] City breakdown: read city from the GeoLite2-City lookup already in `services/geo.py` (fail-open), new `city` column, surface in audience — **paid-tier report** (gate at read time via `effective_plan`, including the public share + CSV export paths)
- [ ] Language breakdown: re-add `navigator.language` to the tracker (dropped in Phase 2; keep < 2 KB), pass through `/collect` (`models/events.py`), new `language` column, audience report
- [ ] Live visitor map: country-level dots/choropleth on the live page from the existing `live:{site_id}` pub/sub payload (already carries `country`, no `visitor_hash`) — no backend change

### Phase 12 — Uptime monitoring & down alerts
**Goal:** ping each site on a schedule; email the owner when it goes down / recovers.
- [ ] Pinger worker (`workers/uptime.py`, run-once + cron like digest/retention): HTTP check per site domain with timeout + retry-before-alarm (avoid flapping false alarms); status + incidents stored in Postgres (new table via Alembic)
- [ ] **SSRF guard:** `domain` is an unverified, user-supplied label (Phase 6) — the pinger must resolve and refuse private/loopback/link-local addresses, cap redirects, and only ever issue GET/HEAD
- [ ] Down / recovered email alerts (`services/uptime.py` → `services/email.py` Resend): **transactional — direct send like verify/reset, NEVER through the marketing opt-out gate**; alert once per incident (idempotent), not per failed ping
- [ ] Dashboard status view: current up/down + recent incidents per site (`hooks/`, small panel or `/sites` badge)
- [ ] Tests: down→alert-once, recover→notice, flapping doesn't spam, no alert through the marketing gate, SSRF targets refused

### Phase 13 — Search Console integration (keywords & SEO)
**Goal:** show which search keywords the site performs on, its average position, and opportunity keywords — from the customer's own GSC data.
- [ ] GSC connect (`services/searchconsole.py` + `routers/`): extend the existing Google OAuth (`identities`) with the `webmasters.readonly` scope; store the site↔GSC-property link + refresh token (Postgres, Alembic; **never log tokens, §9**)
- [ ] Sync worker (`workers/searchconsole.py`, cron daily): pull Search Analytics (query, page, clicks, impressions, CTR, position) into a search-metrics table; idempotent per (site, day)
- [ ] Keyword performance report: top queries by clicks/impressions with average position (rank), date-ranged like other stats
- [ ] Page-level search performance: which pages perform best in Google search
- [ ] Opportunity-keyword recommendations: queries at position ~5–20 with high impressions / low CTR ("just off page one — optimize these"), derived from the same data — **no paid third-party keyword API**
- [ ] Note: the JS snippet cannot see search keywords (search engines strip them from referrers) — GSC is the only honest source. GSC only reports queries the site already appears for.

### Phase 14 — Pricing v2: metered pay-per-view + paywall + site limits (billing — unforgiving, §9)
**Goal:** replace the Phase 7 flat plans entirely with graduated usage-priced billing; cap sites at 5; free accounts over the limit hit a dashboard paywall whose upgrade carries a 7-day trial.
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
- [ ] **Decommission the flat-plan model (replaces Phase 7's pricing, not its plumbing):** remove the 4 flat `STRIPE_PRICE_*` ids + `PLAN_QUOTAS` tier quotas; keep and reuse Phase 7's Checkout/Portal/webhook/idempotency/metering infrastructure. `effective_plan` collapses to two states: **free** (no active subscription) vs **paying** (active or trialing metered subscription). Migrate/notify any existing flat-plan subscribers — **explain before running (§ rule 7)**
- [ ] **Re-position the 7-day trial to the paywall:** the trial no longer starts at signup — it starts when the paywall modal's CTA opens Checkout with a 7-day trial on the metered subscription (dashboard unlocks immediately via the `trialing` webhook; metered billing starts when the trial ends). **One trial per account** — skip the trial for any account that already had a subscription/trial (track via existing `trial_ends_at` / subscription history); trial ends unconverted → back to free → locked again while over 1k. Keep the `trial_will_end` nudge email; update §1 wording (trial starts at upgrade, not signup)
- [ ] Stripe metered billing (`services/billing.py`): ONE graduated-tiered metered Price (tiers as above); push usage to Stripe (Billing Meters / usage records) from the Redis counter — Redis stays the real-time truth, Stripe gets periodic usage pushes (worker or on-invoice); **webhooks stay the only writer of entitlement**
- [ ] **Free-limit paywall:** when a free account (no subscription) exceeds 1k views in the current month → dashboard shows a **blocking upgrade modal** (`components/PaywallModal.tsx`, driven by a `usage_summary` flag e.g. `status: locked`; server also enforces — stats/live endpoints return a typed 402 `PaymentRequired` for locked accounts so the gate isn't UI-only) → modal's CTA opens Stripe Checkout for the metered subscription (with the 7-day trial above) → webhook flips entitlement → dashboard unlocks with all data intact. **CRITICAL: `/collect` keeps ingesting regardless (§9 never drop data)** — the paywall gates the *dashboard*, never the *pipeline*; a paying-late user must not have holes in their charts
- [ ] **Close the side doors while locked:** decide + enforce what a locked account's **public share links** (`/public/{token}`), **CSV export** (`/stats/export`), and **weekly digest** do — they read the same data the paywall gates; leaving all three open makes the wall decorative (default call: share links + export follow the locked state, digest skips locked accounts)
- [ ] Free-tier UX before the wall: reuse `UsageBanner` — warning at ≥80% of 1k ("approaching your free limit"), locked at >1k; paying accounts instead see a running month-to-date bill estimate (from the graduated math over the Redis counter)
- [ ] 5-site limit (`services/sites.py::create_site`): count account sites before insert → typed error → 403/409 with an upgrade-path message; enforce in the service, not the router (§3); frontend disables "Add site" at 5
- [ ] Re-map plan-keyed logic: retention windows (`config.RETENTION_DAYS` → free 30d / paying 365d — decide exact paying window), `show_badge` (free = no subscription)
- [ ] Update §1 (pricing facts + trial-at-upgrade), §6 (Stripe env vars), and the pricing page in the same change
- [ ] **OPEN (growth call, cheap to change later):** free tier stays at 1k for now; consider bumping to 3k–5k for acquisition (free users cost ~nothing at these rates)
- [ ] Tests: graduated tier math at exact boundaries (1k/10k/100k/1M), free-tier no-charge, paywall lock at >1k free + unlock via webhook (never via redirect), trial-once-per-account (second checkout gets no trial), trial-expiry re-locks an over-limit account, `/collect` still ingests while locked, side doors (share/export/digest) follow the locked state, site-limit at 5 (and not at 4), webhook idempotency still holds, retention follows the new free/paying mapping

### Phase 15 — Premium (DEFER until users ask)
**Goal:** upsell features — build only when paying users request them.
- [ ] Custom events + conversion goals
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

_Last updated: 2026-07-06 — **Phase F1 (landing page) built** (F-track, `frontendClaude.md`): new `app/(marketing)/` route group (nav + placeholder footer; `/` and `/privacy` moved in, URLs unchanged) with the one-scroll landing page — sticky nav, staggered hero with ONE indigo headline word, claims strip (honest social-proof substitute), 6-card features grid, how-it-works, privacy USP, **metered pricing section** (free-vs-paying cards + graduated rate table + snap-point slider, all reading `lib/pricing.ts` — **the ONE source of pricing truth**, integer-cents graduated math with boundaries pinned by `lib/pricing.test.ts` under a new **minimal Vitest setup** (`pnpm --filter web test` now real)), FAQ (shadcn Accordion over single-source `content/faq.ts` — F7's chatbot reuses it), final CTA. **Hero embeds a live demo dashboard** (`components/public-dashboard/demo-embed.tsx`): Flowly's own stats via the Phase 8 public share API, token from new `NEXT_PUBLIC_DEMO_SHARE_TOKEN` (+ previously-undocumented `NEXT_PUBLIC_API_URL` now in `.env.example`/§6; real values in `apps/web/.env.local`); unset/failed token → same composition fed labeled sample data (`components/reports/sample-data.ts`). **Share page restyled to the phpAnalytics reference** via a new presentational kit `components/reports/` (delta StatCards + CountUp, TrafficChartCard, icon-rich Breakdown/Pages cards with indigo share bars + "View all", `row-icon.tsx` DDG-favicon/emoji-flag/lucide icons, LiveDot) composed by `components/public-dashboard/{public-dashboard,report-sidebar}.tsx` (grouped in-page-state sidebar scoped to the public API) — hero embed + share page are compositions of the SAME kit; F4 reuses it for the authed dashboard (`components/stats.tsx` remains until then). **Motion**: new dep `motion` (§5 Animation row) via `components/motion.tsx` (Reveal/Stagger/CountUp — reduced-motion gated, ≤500ms, CountUp animates ref textContent to satisfy the set-state-in-effect lint rule); hover lifts + live pulse are pure CSS. New shadcn: accordion, slider. Web lint + tsc + build green (routes unchanged), 7 Vitest pricing tests pass, grep gate holds. Manual steps left: dual-theme/reduced-motion/mobile visual pass and minting a real demo share token for production. **Phase F0 (design system foundation) built** (first phase of the frontend redesign track F0–F7, tracked in `frontendClaude.md`): design tokens live in `apps/web/app/globals.css` `@theme inline` (**Tailwind v4 CSS-first — no `tailwind.config.ts`**, dark mode = `.dark` class via `@custom-variant dark`) — indigo primary `#6366F1` (+`--primary-hover`), slate neutrals, semantic `--success`/`--warning`/`--destructive` (green/red reserved for live/up/down/error), `--chart-1..5`; **next-themes** (system default, `ThemeProvider` in `providers.tsx`, `suppressHydrationWarning` on `<html>`, `components/theme-toggle.tsx` with CSS-swapped icons); **shadcn/ui** kit copied into `components/ui/` (new CLI `init -b radix -p nova`; Button/Card/Input/Select/Table/Dialog/Tabs/Badge/Skeleton/DropdownMenu/Sheet + **sonner as Toast** + custom `EmptyState`; Button default hover → `bg-primary-hover`); duplicated pill-Tabs/site-`<select>`s/"Loading…" strings killed → shared `components/segmented-tabs.tsx` (thin adapter over shadcn Tabs), `SiteProvider`/`useActiveSite()` (`components/layout/site-context.tsx`, localStorage-persisted via `useSyncExternalStore` — the `react-hooks/set-state-in-effect` lint rule forbids setState-in-effect), `components/skeletons.tsx`; **app shell** in `(dashboard)/layout.tsx` (auth guard unchanged): `components/layout/{app-sidebar,app-header,site-switcher}.tsx` driven by `lib/navigation.ts` — the FULL future sidebar IA (Behavior/Acquisitions incl. AI platforms/Geographic/Technology) as data with `ready` flags, only shipped pages render; header = mobile Sheet nav + SiteSwitcher + date-range-picker slot (F1) + theme toggle + user menu; **Recharts theme module** `components/charts/chart-theme.tsx` (colors as `var(--chart-N)` straight into SVG props → auto theme flip; `ChartTooltip`/`ChartGradient`/grid/axis presets; TrafficChart = indigo Area + gradient, compact axes); formatters centralized in `lib/format.ts`; the Geist-defeating `font-family: Arial` bug in globals.css fixed. New deps: next-themes, shadcn (runtime), radix-ui, cva, clsx, tailwind-merge, lucide-react, tw-animate-css, sonner (§5 updated). Grep gate: no raw hex/`gray-*`/`bg-black` utilities outside `globals.css` (exception: vendored dialog/sheet scrim). Web lint + tsc + build green (13 routes). Manual dual-theme visual pass is the remaining verification step. **tz-param fix:** ClickHouse `DateTime` params are now bound **tz-aware UTC** (`services/stats.py::_range_params`, `services/retention.py::build_delete_query`); a naive param is rendered as a bare string that ClickHouse parses in the *server* timezone, which shifted every stats window and retention cutoff by the server's UTC offset — on a BST dev server the newest hour of events was invisible in every "until now" report (dashboard, public share, CSV export, digest). Found by live E2E (unit tests don't run real ClickHouse); contract pinned in `test_stats_builders`/`test_retention`. 206 backend tests pass, ruff clean. **Roadmap (2026-07-04):** new Phases 10–14 added (query-layer reports & filtering; city/language/live-map + first ClickHouse migration convention; uptime monitoring & down alerts; Search Console keywords/SEO; **Pricing v2 — graduated metered billing REPLACING the flat plans: 1k free / $0.99 per 1k to 10k / $0.10 per 1k to 100k / $0.05 per 1k to 1M / $0.03 beyond, views summed account-wide across all (max 5) sites, dashboard paywall modal when a free account passes 1k whose Checkout carries the repositioned 7-day trial — trial starts at upgrade, once per account; ingestion never blocked, §9**); old deferred Phase 10 renumbered to **15** (Search Console removed from it — now Phase 13) and a **Parked** list records what we decided against (new-vs-returning, 404 tracking, CWV/JS errors, paid keyword research). Phases 0–9 untouched. Build note history: Phase 8 (growth & retention) + Phase 9 (privacy & trust) built. **Shared email prereq:** `services/email.py` now delivers via **Resend** (a single httpx POST in `_send_via_provider`; still dev-stub-logs in local/no-key) with an optional HTML body; new `services/notifications.py` is the **marketing gate** — `send_marketing_email` refuses opted-out accounts and appends a signed one-click unsubscribe footer, `marketing_recipients` lists verified+not-opted-out accounts, `apply_unsubscribe` flips the flag; `accounts.email_opt_out` column + `create_unsubscribe_token` (new `unsubscribe` JWT type, 10y) + public `routers/email.py` `GET /email/unsubscribe`. Transactional mail (verify/reset, trial-ending) never routes through the gate. **8.1 digest:** `services/digest.py` builds a per-site trailing-week summary by reusing the Phase 5 stats services (no bespoke SQL) → `render_digest` (subject/html/text); `workers/digest.py` (run-once, cron weekly) iterates recipients, skips zero-traffic, sends via the gate, and marks `digest:{account_id}:{ISOyearweek}` in Redis (10-day TTL) for idempotency. **8.2 share + 8.3 badge:** `models.tables.ShareToken` (secret `token_urlsafe`, FK to site pk, soft `revoked_at`) + `services/sharing.py` (create=rotate revokes prior, `resolve_share` only returns live tokens, single-site scope); authed create/rotate/revoke on `routers/sites.py` (`/sites/{id}/share`), **public** `routers/public.py` (`/public/{token}/…`) reuses the stats services with a token gate replacing bearer auth (404 on unknown/revoked before any query) — `GET /public/{token}` returns `{domain, show_badge}` where `show_badge = effective_plan==free`; web `app/share/[token]` read-only dashboard (`hooks/usePublicStats.ts`, unauth `publicFetch`) + `components/{PoweredByBadge,ShareControl}.tsx`. Shared `core/timerange.py::stats_range` extracted from `routers/stats.py` so both stats + public routers use one window parser. **8.4 onboarding:** `models.tables.OnboardingEmail` ((account,step) unique ledger) + `services/onboarding.py` (welcome/install/live content + `already_sent`/`record_step`); `workers/onboarding.py` (run-once, cron hourly) advances each account — welcome once, `live` on first event (`sites.first_event_seen`), `install` nudge only if dark after 24h (and marked-without-emailing once live). `trial_will_end` wired via `billing.on_event_committed` (post-commit, best-effort transactional email) called from the webhook router. **9.1 retention:** `config.RETENTION_DAYS` (free 30 / pro 365 / business 730) + `services/retention.py` (pure `(sql,params)` site-scoped `ALTER TABLE events DELETE WHERE site_id AND ts<cutoff`, cutoff from `effective_plan` so a lapsed trial ages out at 30d) + `db/clickhouse.py::run_command`; `workers/retention.py` (run-once, cron daily) sweeps every site, logs each cutoff (destructive by design, §7). `events` was already `PARTITION BY toYYYYMM(ts)` so no CH schema change. **9.2 export:** `services/export.py` (aggregated reports only — never raw events, no `visitor_hash`/IP) + `GET /stats/export` (authed, `owned_site`+`stats_range`, `text/csv` download). **9.3 privacy:** static Server Component `app/privacy` + landing-page link. **billing hardening:** `effective_plan`/onboarding now coerce a naive stored `trial_ends_at`/`created_at` to UTC (§4) so a mixed-awareness read can't raise (prod asyncpg is already aware; guards the SQLite test path). Migration `f3a9c1d47b20` (batch-mode): `email_opt_out` + `share_tokens` + `onboarding_emails`; applied + downgrade-verified on dev Postgres, single head. **No new deps** (Resend rides existing httpx), **no new env var** (`EMAIL_API_KEY`/`EMAIL_FROM` already present). §7 gained the three worker cron commands. 206 backend tests pass (new `test_notifications`/`test_sharing`/`test_public_router`/`test_digest`/`test_onboarding`/`test_retention`/`test_export`/`test_billing_trial`, extended `test_migration`); web lint + tsc + build green (new `/privacy`, `/share/[token]` routes). Live Resend + Stripe smoke and wiring the three workers to a real scheduler are the manual steps left. Phase 7 post-review hardening: (1) removed the dead `resolve_account_id` (nothing called it; its "self-heals from Postgres" promise was never wired) — the site→account map is now honestly documented as write-once at `create_site`, and a lost best-effort write just under-counts that site until re-saved (never blocks ingestion); `meter_pageview` now debug-logs a cold miss. (2) `create_checkout_session` reuses a known `stripe_customer_id` and **refuses** checkout for an already active/past_due account (402 → use the portal), closing a duplicate-customer / double-subscription hole; it now takes a session. (3) webhook `_account_from_event_object` guards the `UUID(metadata)` parse so a malformed id can't 500-loop Stripe retries. (4) `/script.js` returns 404 (not 500) when the tracker isn't built. Ruff check+format clean; 167 backend tests pass (added checkout-guard + Redis-only cache round-trip tests). Phase 7 build note follows. Phase 7 (billing & usage metering) built: trial converts to paid, metered by pageviews. **Split of truth:** Stripe = entitlement, Redis = usage, Postgres = durable mirror. `services/billing.py` holds the metering half (`record_usage`/`meter_pageview` → `INCR usage:{account_id}:{YYYYMM}` + 45-day TTL; Redis-only `cached_account_id` on the hot path so `/collect` stays off Postgres — the `site:{site_id}→account_id` map is written by `create_site`; `resolve_account_id` warms it from Postgres on a cold miss) plus read-time entitlement: `effective_plan` derives the tier (active/past_due/in-window-trial → `account.plan`, else `free`), so a **lapsed card-free trial or canceled sub downgrades to `free` with no webhook/job**; `usage_summary` → `{plan,quota,used,pct,status: ok|warning(≥80%)|over(≥100%)}`; `over_hard_ceiling` (3× quota) is a runaway guard, **not** enforced on the hot path (would need a Postgres read per event — burst cost is bounded by the Phase 3 rate limit instead). Soft cap: data is **never dropped at the quota** (§9). Stripe half: `create_checkout_session` (mode=subscription, `trial_end=trial_ends_at` pass-through so no double-trial/early-charge, account id in `client_reference_id` + subscription metadata), `create_portal_session` (402 `BillingError` if no customer), `verify_webhook` (sync signature check), and `apply_subscription_event` — **the ONLY writer of entitlement** (never the redirect, §10): `subscription.created|updated` → set `account.plan/status` + upsert `subscriptions` (price/customer/sub id, `cancel_at_period_end`, `current_period_end`), `deleted` → `free`/`canceled`, `invoice.payment_failed` → `past_due` (keeps serving), `trial_will_end` → nudge no-op; account resolved via subscription metadata (order-independent) or `stripe_customer_id`. `routers/billing.py` (thin): authed `POST /billing/checkout`, `POST /billing/portal`, `GET /billing/usage`; **public** `POST /billing/webhook` — verify sig (bad → 400 `WebhookSignatureError`) → dedupe via `processed_stripe_events` (event_id PK) → apply + insert id in one transaction (IntegrityError on a raced redelivery → idempotent ack). New `BillingError` (402) in `core/exceptions.py`; the webhook's bad-signature 400 is a router-local `WebhookSignatureError`. Metering hooks into `services/ingest.py` best-effort after the durable XADD (only counted events; bots/rate-limited already returned). Migration `c7f1b2f13d02` (batch-mode): `subscriptions.stripe_price_id` + `cancel_at_period_end`, new `processed_stripe_events` table + `ProcessedStripeEvent` model; applied + downgrade-verified on dev Postgres. `config.py` gained the Stripe block (secret/webhook/4 price ids) + `PLAN_QUOTAS` (`free 10k / pro 100k / business 1M`, placeholders) + `HARD_CEILING_MULTIPLE=3`. Frontend: `hooks/useBilling.ts` (`useUsage`/`useCheckout`/`usePortal`), `components/UsageBanner.tsx` (amber ≥80% / red ≥100% nudge, injected in the dashboard `layout.tsx` — the only shared chrome; never blocks), `app/(dashboard)/billing/page.tsx` (plan + usage bar, monthly/annual upgrade → Checkout, Customer Portal, `?checkout=success|cancel` return), and a "Billing" dashboard link. New dep **stripe** (15.3.0); new env vars `STRIPE_PRICE_PRO_ANNUAL`/`STRIPE_PRICE_BUSINESS_ANNUAL` (in `.env.example` + §6). 165 backend tests pass (`test_billing_service`, `test_billing_router`, extended `test_ingest`/`test_sites_service`/`test_migration`); web lint + tsc + build green. Live Stripe smoke (Checkout/Portal/webhook via `stripe listen`) is the one manual step left. Phase 6 hardening note follows. Phase 6 hardening (post-review): (1) **duplicate-domain race** closed — the `sites` table gained a `UniqueConstraint("account_id", "domain", name="uq_site_account_domain")` (migration `4962f38126db`, down-rev `0b5153c24ddf`, batch-mode so it runs on SQLite too), and `services/sites.py::create_site` now wraps its `commit()` in a `try/except IntegrityError → ConflictError` (mirrors `auth.py::signup`) so a lost race surfaces a clean 409, not a 500; the pre-check `SELECT` stays as the friendly fast path. (2) **`/sites` is now a manage screen** — `app/(dashboard)/sites/page.tsx` lists existing sites (each with an "Open" → reuses `InstallStep`, now with a "← All sites" back link) above the add form, keeping the app's URL-free in-page-state convention (no dynamic route); the dashboard header link is relabelled "Sites". Migration applied + downgrade-verified on dev Postgres (no existing dupes); 133 backend tests pass (new `test_duplicate_domain_race_caught_by_db_constraint`); web lint + tsc + build green. Phase 6 note follows. Phase 6 (site onboarding) built: a user can add a site, get an install snippet, and watch it flip waiting→connected. `core/urls.py::normalize_host` was extracted from `services/ingest.py::_host` (now imported by both ingest + sites) — it stays **non-raising** (fail-open, so `/collect` can't break) and now handles **bare-domain** input (`example.com`; `urlparse` needs a `//` prefix or its `netloc` is empty). `services/sites.py` gained `create_site` (normalize domain → `ValidationError` if empty; account-scoped duplicate-domain → `ConflictError`; `secrets.token_hex(8)` `site_id` with a 3-try collision retry backed by the `UNIQUE` index), `first_event_seen` (Redis `count_active` first for an instant signal, else a server-parameterized ClickHouse `SELECT 1 … LIMIT 1` existence probe — durable, no new column), `build_snippet` (from new `TRACKER_SCRIPT_URL` in `config.py`), and the canonical `to_site_out` (attaches the computed `snippet`, never `model_validate`). New `routers/sites.py` (`prefix="/sites"`): `GET /sites` (moved out of `live.py`), `POST /sites` (201), `GET /sites/{site_id}`, `GET /sites/{site_id}/status` — the per-site routes use a **path-param** `owned_site` dep (404 before any Redis/CH query, §9). `domain` is a cosmetic label (events scoped by `site_id`, not origin — enforcement deferred). Frontend: `hooks/useSites.ts` gained `useCreateSite` + `useSiteStatus` (polls, stops on connected and after a ~3-min cap + manual re-check), `components/install.tsx` (snippet copy-box + per-platform tabs + status pill), `app/(dashboard)/sites/page.tsx` (add-domain → install two-step), and "Add site" CTAs on the dashboard/live empty states. `SiteOut` gained a required `snippet`; `SiteCreate`/`SiteStatus` added. No new migration (schema unchanged), no new dep; one new env var (`TRACKER_SCRIPT_URL`, already in `.env.example`). 132 backend tests pass (incl. `test_urls.py`, `test_sites_service.py`, extended `test_sites.py`); web lint + tsc + build green. Phase 5 note follows. Phase 5 (historical dashboard metrics) built: `services/stats.py` holds pure `(sql, params)` query-builders + a shaping service — overview (visitors/sessions/pageviews/bounce/avg-duration) with prior-period compare, time-series (hour/day buckets auto-picked from range length, gaps zero-filled in Python), sources+UTM, audience (country/device/browser/os), and pages (top/entry/exit). Sessions/bounce/duration are derived in SQL from a 30-min `visitor_hash`+`ts` gap via `_SESSIONIZED_CTE` (`lagInFrame` → session starts → running sum); there is no `session` column. All ClickHouse SQL is **server-parameterized** (`{site_id:String}`) — no user value string-formatted in (§9). `db/clickhouse.py` gained a raw `query_rows` read helper. `routers/stats.py` exposes `/stats/{overview,timeseries,sources,audience,pages}`, each gated by the `owned_site` dependency that verifies ownership (→ 404) **before** any query. Ownership (`get_owned_site`/`list_account_sites`) was extracted from `services/live.py` into shared `services/sites.py` (live + tests updated). Frontend: `hooks/useStats.ts` (TanStack Query, keyed by endpoint+site+range), `components/stats.tsx` (metric cards + Recharts line chart + sources/audience/pages/UTM tables), and `app/(dashboard)/dashboard/page.tsx` (site picker, 24h/7d/30d presets, audience/pages tabs). New dep: **recharts** (already in §5). No new env var (`SESSION_TIMEOUT_SECONDS=1800`, `MAX_RANGE_DAYS=372` are constants). Cookieless caveat: daily `visitor_hash` rotation over-counts multi-day unique visitors (accepted tradeoff). 102 backend tests pass; web lint + tsc + build green. Phase 4 (live) note follows. Phase 4 (real-time live traffic) built: `services/live.py` holds the presence ZSET + pub/sub — `mark_active` pipelines `ZADD active:{site_id}` + stale eviction + key `EXPIRE` (bounded with no viewer), `count_active` evicts-then-`ZCARD`, `publish_event` fans to `live:{site_id}`, and `subscribe_events` owns a per-connection pub/sub (with an `on_ready` hook so the WS subscribes before sending its count snapshot). `services/ingest.py` calls `live.record_and_publish` (presence + publish in one pipeline) best-effort right after the `XADD` (never blocks/fails `/collect`; forwarded payload is IP-free and hash-free). `routers/live.py` serves `WS /live/{site_id}` — accept → Origin check → `?token=` verify (`decode_token`) → site-ownership on a short-lived session → subscribe → snapshot → forward/heartbeat/receiver tasks, all rejections `close(1008)` — plus a read-only ownership-scoped `GET /sites` (thin borrow from Phase 6) and the `SiteOut` schema. Frontend: `hooks/useLiveTraffic.ts` (native WebSocket, capped feed, backoff reconnect, one token-refresh retry on 1008), `hooks/useSites.ts`, `components/live.tsx`, and `app/(dashboard)/live/page.tsx` (auto-guarded, site picker, remount-per-site via key). No new dep, no new env var (`LIVE_WINDOW_SECONDS=300` is a constant). 72 tests pass. Phase 3 (ingestion), Phase 2 (tracker), Phase 1 (auth) previously built. Keep this date current whenever the stack or rules change._
