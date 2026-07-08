# Deploying Flowly (Render / Railway)

Production deploy guide. `render.yaml` provisions the compute + Postgres + Redis
automatically; this file covers everything that lives **outside** it — external
services (ClickHouse, Stripe, Google), the secret values, and the order to do
things in.

> **Architecture recap.** Three apps run as containers: the **API** (FastAPI —
> ingestion + dashboard API + WebSocket + serves `/script.js`), the **web**
> dashboard (Next.js), and background **workers** (one always-on batch writer +
> six cron jobs). Data lives in **Postgres** (metadata), **ClickHouse** (events),
> and **Redis** (live + usage + ingest buffer). Render/Railway host Postgres and
> Redis; **ClickHouse comes from ClickHouse Cloud** (neither PaaS offers it).

---

## 0. Prerequisites

- The repo pushed to GitHub (Render/Railway deploy from a git remote).
- Accounts: **Render** (or Railway), **ClickHouse Cloud**, **Stripe**, and
  optionally **Google Cloud** (OAuth + Search Console), **Resend** (email),
  **Anthropic** (support-chatbot AI), **MaxMind** (GeoLite2 city DB).
- A domain you can add DNS records to (for the API + web custom domains and the
  tracker script URL). You can launch on the `*.onrender.com` URLs first and add
  domains later.

---

## 1. Provision ClickHouse (ClickHouse Cloud)

1. Create a ClickHouse Cloud service; note the **host**, **port `8443`**,
   **username** (`default`), and **password**.
2. Create the database (default name `default` is fine — match `CLICKHOUSE_DB`).
3. That's all — the API's pre-deploy step (§4) creates the `events` table and
   applies column migrations idempotently on first deploy.

These map to env vars (set in §3): `CLICKHOUSE_HOST`, `CLICKHOUSE_USER`,
`CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DB`, and **`CLICKHOUSE_SECURE=true`** (TLS on
8443 — the app defaults the port to 8443 when secure).

---

## 2. Create the Render Blueprint

1. Render → **New +** → **Blueprint** → pick this repo. Render reads
   `render.yaml` and creates: `flowly-api`, `flowly-web`, `flowly-batch-writer`,
   the six cron jobs, `flowly-postgres`, and `flowly-redis`.
2. It will pause for the `sync: false` env vars — fill them in §3 before the
   first deploy finishes (or set them, then trigger a redeploy).

`DATABASE_URL` and `REDIS_URL` are wired automatically from the managed
Postgres/Redis. `JWT_SECRET` and `VISITOR_SALT_SECRET` are auto-generated once
and shared across all services.

---

## 3. Environment variables to fill (the `sync: false` set)

Set these on the **`flowly-shared`** env group (applies to API + all workers):

| Var | Value |
|---|---|
| `API_BASE_URL` | the API's public URL, e.g. `https://api.yourdomain.com` |
| `WEB_BASE_URL` | the web app's public URL, e.g. `https://app.yourdomain.com` (this is the CORS + WebSocket origin allowlist — must be exact) |
| `TRACKER_SCRIPT_URL` | `${API_BASE_URL}/script.js` (the API serves the built tracker) |
| `CLICKHOUSE_HOST` / `_USER` / `_PASSWORD` / `_DB` | from §1 |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRICE_METERED` | from §5 |
| `EMAIL_API_KEY` / `EMAIL_FROM` / `CONTACT_EMAIL` | Resend key + a verified sender; blank leaves email in dev-stub (log-only) mode |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | from §6 (enables Google sign-in **and** Search Console) |
| `ANTHROPIC_API_KEY` | optional — blank = chatbot answers FAQ only, no AI fallback |

Already defaulted in `render.yaml` (override if needed): `CLICKHOUSE_SECURE=true`,
`STRIPE_METER_EVENT=pageviews`, `UPTIME_ENABLED=false`, `ENVIRONMENT=production`.

On the **`flowly-web`** service set (these are Docker **build args** — inlined at
build, so a change needs a redeploy):

| Var | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | same as `API_BASE_URL` |
| `NEXT_PUBLIC_DEMO_SHARE_TOKEN` | optional — a share token for the landing-page live demo; blank = sample data |

**GeoIP (optional, for city/region enrichment):** `GEOIP_DB_PATH` needs a MaxMind
GeoLite2-City `.mmdb` on the API's disk. The simplest path is to bake it into the
API image (add a `COPY` in `apps/api/Dockerfile` and set `GEOIP_DB_PATH` to that
path) or attach a Render disk. Left unset, geo fails open (empty country/city) —
everything else works.

---

## 4. First deploy — order of operations

1. Ensure §3 vars are set. Trigger the deploy (auto on blueprint create).
2. The **API build** compiles the tracker (`dist/script.js`) into the image, then
   its **`preDeployCommand`** runs automatically:
   `alembic upgrade head && python -m app.db.clickhouse --migrate`
   — so Postgres migrations (through `d4e5f6a7b8c9`) **and** the ClickHouse
   `events` table + columns are applied with no manual step. Watch the deploy log
   to confirm both succeed.
3. Verify: `GET ${API_BASE_URL}/health` → `{"status":"ok"}`; open `WEB_BASE_URL`.
4. Confirm `flowly-batch-writer` is **running** (not crash-looping) — without it
   no event reaches ClickHouse.

---

## 5. Stripe (metered billing) — required before charging

1. Create a **graduated metered Price** whose tiers mirror `apps/web/lib/pricing.ts`
   (1k free / $0.99 per 1k to 10k / $0.10 to 100k / $0.05 to 1M / $0.03 beyond),
   attached to a **Billing Meter** with event name `pageviews`. Put the Price id
   in `STRIPE_PRICE_METERED`.
2. Add a webhook endpoint → `${API_BASE_URL}/billing/webhook`, subscribe to
   subscription created/updated/deleted, `customer.subscription.trial_will_end`,
   and `invoice.payment_failed`. Put its signing secret in `STRIPE_WEBHOOK_SECRET`.
3. Smoke-test with the Stripe CLI against the live URL, then run one real
   Checkout → webhook → confirm the account flips to `metered` and usage pushes
   via the hourly `flowly-usage-report` cron.

---

## 6. Google OAuth + Search Console (optional)

1. In Google Cloud, create an OAuth client; set `GOOGLE_CLIENT_ID` / `_SECRET`.
2. Authorized redirect URIs:
   - `${API_BASE_URL}/auth/oauth/google/callback` (sign-in)
   - `${API_BASE_URL}/searchconsole/callback` (Search Console connect)
3. GitHub sign-in is analogous (`GITHUB_CLIENT_ID` / `_SECRET`, redirect
   `${API_BASE_URL}/auth/oauth/github/callback`).

---

## 7. Post-deploy checklist

- [ ] `/health` OK; web loads; sign-up → verify (real email once `EMAIL_API_KEY` set).
- [ ] Add a site, install the snippet on a test page, see it flip to **Connected**
      and appear in **Live** (Redis) and **Overview** (after the batch writer flushes).
- [ ] Fire a `flowly('event','signup')` → shows under **Goals & events** on a paid
      account (free → upgrade prompt, by design).
- [ ] Real Checkout → account becomes `metered`; usage-report cron pushes to Stripe.
- [ ] Cron jobs show successful runs in the Render dashboard.

---

## Railway alternative

Same shape, different wiring:

- Add plugins for **PostgreSQL** and **Redis**; reference `${{Postgres.DATABASE_URL}}`
  and `${{Redis.REDIS_URL}}` (the app auto-upgrades a `postgres://` DSN to the
  asyncpg driver, so the plugin URL works as-is).
- Create one service per process from this repo, each using the Dockerfiles:
  API (`apps/api/Dockerfile`), web (`apps/web/Dockerfile`), and the batch writer +
  crons (API Dockerfile with a custom **Start Command** / **Cron Schedule**, e.g.
  `python -m app.workers.usage_report`).
- Railway passes service variables as Docker build args, so set `NEXT_PUBLIC_API_URL`
  on the web service. Run the migrations once via a one-off command
  (`alembic upgrade head && python -m app.db.clickhouse --migrate`) or replicate the
  API pre-deploy hook.

---

## Notes & caveats

- **Verify the image builds locally first** (`docker build -f apps/api/Dockerfile .`
  and the web one with `--build-arg NEXT_PUBLIC_API_URL=…`). The web standalone
  build in a pnpm monorepo is the fiddliest part; catching a break locally is
  cheaper than in CI.
- **ClickHouse is external** — retention/analytics costs scale there, not on the PaaS.
- **The refresh token** for Search Console is stored plaintext (guarded by
  never-log/never-return); encryption-at-rest is a recommended future hardening.
- Scale the API and batch writer independently as traffic grows; the ingest path
  is designed to return in milliseconds and drain asynchronously.
