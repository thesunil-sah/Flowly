# Flowly — test-server runbook (Docker Compose, one box, plain HTTP)

Stand the **whole** app up on your own server to exercise every feature. This is
a **staging/test** deployment, not the production one (that's `DEPLOY.md` /
`render.yaml`). It runs its own **Postgres + ClickHouse + Redis** in containers,
so the only thing the server needs is **Docker**.

> Reach the app at `http://SERVER_IP:3000`. OAuth and Stripe webhooks need HTTPS
> and are covered in the last section — everything else works over plain HTTP.

---

## 0. Prerequisites on the server

- A Linux server (2 vCPU / 4 GB RAM is comfortable — ClickHouse likes memory).
- **Docker Engine + Compose v2** installed:
  ```bash
  curl -fsSL https://get.docker.com | sh
  docker compose version   # must print v2.x
  ```
- Inbound firewall open for **3000** (web) and **8000** (API). The databases are
  NOT published to the host — they're reachable only inside the Docker network.

---

## 1. Get the code + configure

```bash
git clone <your-repo-url> flowly && cd flowly
git checkout <the-branch-you-want-to-test>

cp .env.server.example .env.server
nano .env.server            # set SERVER_IP + the four secrets (see below)
```

Fill in `.env.server`:

| Var | What to put |
|---|---|
| `SERVER_IP` | the server's **public IP or hostname** — no scheme, no port. Must match how you open it in the browser, or CORS/WebSocket reject everything. |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `VISITOR_SALT_SECRET` | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | any strong string |
| `CLICKHOUSE_PASSWORD` | any strong string |
| `ENVIRONMENT` | leave `local` (see note below) |

**Why `ENVIRONMENT=local` on a server?** With no email provider configured, the
signup / verify / password-reset responses surface the one-time `dev_code`
on-screen so you can finish those flows in the browser. Set it to `production`
only if you also set a real `EMAIL_API_KEY` (otherwise the codes go only to the
container logs — see `docker compose logs api`).

---

## 2. Bring it up

```bash
docker compose --env-file .env.server up -d --build
```

First run builds three images (tracker+API, web) and pulls Postgres/ClickHouse/
Redis. Give it a few minutes. The **API applies all migrations automatically on
start** (`alembic upgrade head` + ClickHouse `--migrate`) — no manual DB step.

Check everything is healthy:

```bash
docker compose --env-file .env.server ps      # all "healthy" / "running"
curl http://localhost:8000/health             # {"status":"ok",...}
curl -I http://localhost:8000/script.js       # 200, application/javascript
```

Then open **`http://SERVER_IP:3000`** in a browser.

> **Changed `SERVER_IP` later?** The web bundle bakes it in at build time —
> rebuild web: `docker compose --env-file .env.server up -d --build web`.

---

## 3. Smoke-test the core flow (no external services needed)

1. **Sign up** at `/sign-up`. The page shows a "Dev mode" code (because
   `ENVIRONMENT=local`) — use it to verify. Sign in.
2. **Add a site** (sidebar → Sites) → copy the install snippet. It points at
   `http://SERVER_IP:8000/script.js`.
3. **Generate traffic.** Put the snippet on any test page served over the
   network (or use `apps/tracker/test/index.html` with `data-site` set to your
   new site_id). Reload a few times; add `?utm_source=news&utm_medium=email` to
   populate campaigns.
   - The Sites tab flips **waiting → connected** within seconds.
   - **Live** shows the visitor instantly (Redis path).
   - **Overview** fills in after the batch writer flushes (a few seconds).
4. Fire a custom event from the page console to test goals:
   `flowly('event','signup')` → shows under **Goals & events** on a paid account
   (free shows the upgrade prompt — by design).

> Bot filter note: requests from `curl` (or any bot User-Agent) are accepted with
> `202` but intentionally **not** counted. Test ingestion from a real browser, or
> the numbers stay at zero.

## 4. Run the background workers on demand

The always-on **batch writer** runs as its own service. The other jobs are cron
tasks in production — run any of them once against the live stack like this:

```bash
docker compose --env-file .env.server exec api python -m app.workers.retention
docker compose --env-file .env.server exec api python -m app.workers.digest
docker compose --env-file .env.server exec api python -m app.workers.onboarding
docker compose --env-file .env.server exec api python -m app.workers.usage_report
docker compose --env-file .env.server exec api python -m app.workers.uptime       # needs UPTIME_ENABLED=true
docker compose --env-file .env.server exec api python -m app.workers.searchconsole
```

## 5. Logs, restart, teardown

```bash
docker compose --env-file .env.server logs -f api          # follow API logs (verify codes land here in production mode)
docker compose --env-file .env.server logs -f batch-writer
docker compose --env-file .env.server restart api
docker compose --env-file .env.server down                 # stop (keeps data volumes)
docker compose --env-file .env.server down -v              # stop + WIPE all data (fresh start)
```

---

## What you CAN'T fully test over plain IP + HTTP

These features need a real domain with HTTPS (external providers refuse plain
`http://IP` callbacks). Everything else — ingestion, live, all reports, sites,
goals, CSV export, sharing, privacy, contact, chatbot FAQ — works as-is.

| Feature | Why it needs HTTPS | To enable |
|---|---|---|
| **Google / GitHub sign-in** | OAuth redirect URIs can't be `http://IP` | domain + HTTPS, then register `${API_BASE_URL}/auth/oauth/<provider>/callback` |
| **Search Console** | same OAuth flow (`webmasters.readonly`) | domain + HTTPS + `${API_BASE_URL}/searchconsole/callback` |
| **Stripe webhooks** (checkout → `metered`, usage push) | Stripe posts to a public HTTPS URL | domain + HTTPS + webhook at `${API_BASE_URL}/billing/webhook` |
| **Real transactional email** | needs a Resend key + verified sender | set `EMAIL_API_KEY` + `EMAIL_FROM` (works over HTTP once keyed) |

### Upgrading this box to a domain + HTTPS

When you're ready to test the auth/billing features, point a domain at the server
and put a TLS reverse proxy (e.g. **Caddy**, which does automatic Let's Encrypt)
in front — route `app.yourdomain.com → web:3000` and `api.yourdomain.com →
api:8000`. Then set in `.env.server`: `SERVER_IP` stays for internal wiring but
change the browser-facing URLs to the domains (this needs a small compose tweak
to split internal vs. public URLs — ask and I'll add a `caddy` service +
`API_PUBLIC_URL`/`WEB_PUBLIC_URL` split). Register the OAuth redirect URIs and the
Stripe webhook against the HTTPS domain.

---

## Notes

- **GeoIP** (country/city on visitors) is off unless you mount a MaxMind
  GeoLite2-City `.mmdb` and set `GEOIP_DB_PATH`. Geo fails open — everything else
  works, the country column is just blank.
- **Data persistence**: Postgres/ClickHouse/Redis write to named Docker volumes
  (`pgdata`, `chdata`, `redisdata`). They survive `down`; `down -v` wipes them.
- **This is a test box** — it publishes only 3000/8000, keeps the databases
  private to the Docker network, and uses self-signed-free plain HTTP. Do not put
  real customer data through it.
