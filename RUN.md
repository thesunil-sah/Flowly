# Flowly — run locally & manual check (F0 + F1)

A copy-paste runbook to boot the whole stack on this machine and manually
verify the F0 design system + F1 landing page. Nothing here is automated —
follow it top to bottom. (Personal helper file — not part of the phase docs.)

---

## 0. Prerequisites (one-time)

- **Postgres**, **ClickHouse**, and **Redis** running and reachable — however
  you host them; the API only uses the connection strings in `.env`.
- Root `.env` exists (copy from `.env.example`, fill `DATABASE_URL`,
  `CLICKHOUSE_*`, `REDIS_URL`, `JWT_SECRET`).
- **Web env is separate**: Next.js does NOT read the repo-root `.env`.
  Create `apps/web/.env.local` (git-ignored) with:

  ```
  NEXT_PUBLIC_API_URL=http://localhost:8000
  # leave unset for now — step 5 fills it in:
  # NEXT_PUBLIC_DEMO_SHARE_TOKEN=
  ```

## 1. Start the backend

```powershell
cd apps\api
uv sync                                   # first time / after dep changes
uv run alembic upgrade head               # apply Postgres migrations
uv run uvicorn app.main:app --reload      # API on http://localhost:8000
```

In a **second terminal** (needed so events actually reach ClickHouse):

```powershell
cd apps\api
uv run python -m app.workers.batch_writer # drains Redis stream -> ClickHouse
```

Sanity: open http://localhost:8000/health → should return OK.

## 2. Start the web app

Third terminal:

```powershell
pnpm install                  # first time / after dep changes
pnpm --filter web dev         # http://localhost:3000
```

## 3. Create an account + site

1. http://localhost:3000/sign-up → sign up (in dev the verification code is
   shown on-screen as a "Dev mode" hint).
2. Sign in → you land in the dashboard shell (F0: sidebar, header, theme
   toggle top-right).
3. Sidebar → **Sites** → add a domain (e.g. `example.com`) → you get the
   install snippet. Keep this tab open (it polls waiting→connected).

## 4. Generate traffic (so charts aren't empty)

Use the tracker test harness:

```powershell
pnpm --filter tracker build
```

Open `apps\tracker\test\index.html` in a browser and set its `data-site` to
your new site_id (from the Sites page snippet). Every page load fires a
pageview at `/collect`. Reload it a bunch of times; also try with UTM params
(`?utm_source=newsletter&utm_medium=email`) for the campaigns table.

- The Sites tab should flip to **Connected** within seconds.
- **Live** (sidebar) shows the visitor immediately (Redis path).
- **Overview** shows history once the batch writer has flushed (a few seconds).

## 5. Mint the demo share token (powers the landing hero)

1. Dashboard → Overview → scroll to **Public share link** → *Create share
   link* → Copy. The URL looks like `http://localhost:3000/share/<TOKEN>`.
2. Put the token part into `apps\web\.env.local`:

   ```
   NEXT_PUBLIC_DEMO_SHARE_TOKEN=<TOKEN>
   ```

3. **Restart** `pnpm --filter web dev` — `NEXT_PUBLIC_*` is inlined at build
   time, a hot reload is not enough.

## 6. Manual verification checklist

### Landing page — http://localhost:3000

- [ ] Hero: badge pill → headline with ONE indigo word → two CTAs → framed
      demo. With the token set: **your real numbers**, live dot pulsing,
      stat values count up, caption "Live demo — last 7 days", footer link
      "Explore the full live demo →".
- [ ] Remove/comment the token + restart → same frame shows **"Sample data"**
      caption with plausible numbers, **zero** requests to :8000, no errors.
- [ ] Nav links Features / Pricing / Live demo scroll to their sections and
      the headings are NOT hidden under the sticky nav.
- [ ] Scroll down slowly: each section fades up **once** (~16px rise), never
      re-triggers when scrolling back.
- [ ] Pricing: rate table shows 1k free / $0.99 / $0.10 / $0.05 / $0.03;
      slider at 100k reads **≈ $17.91 / month**, at 1M **≈ $62.91**.
- [ ] FAQ accordion opens/closes; Final CTA + footer render.

### Themes (dark is the primary presentation)

- [ ] Toggle Light / Dark / System from the marketing nav AND the app header.
- [ ] Hard-reload with OS in dark + theme "System" → **no flash** of white.
- [ ] Walk every route in BOTH themes — nothing invisible/white-on-white:
      `/`, `/privacy`, `/sign-in`, `/sign-up`, `/dashboard`, `/live`,
      `/sites`, `/billing`, `/share/<TOKEN>`. Chart grid/tooltip/gradient
      must look right in both.

### Reduced motion

- [ ] DevTools → Rendering → *Emulate prefers-reduced-motion: reduce* →
      reload `/`: no stagger/reveal/count-up, live dot static, ALL content
      visible (nothing stuck faded out).

### Share page — http://localhost:3000/share/<TOKEN>

- [ ] Grouped sidebar (Overview / Behavior / Acquisitions / Audience) switches
      reports in-page; "View all" on overview cards jumps to the section.
- [ ] Icon rows: favicons on domain sources, pointer icon on "direct", emoji
      flag (or "US" letters on Windows — expected) on countries.
- [ ] 24h / 7d / 30d presets refetch; indigo share bars scale per row.
- [ ] Revoke the link from the dashboard → the share URL shows
      **"Dashboard not found"**; the landing hero falls back to sample data.
      (Re-create the link after — new token, update `.env.local`.)

### Mobile (~375px, DevTools device toolbar)

- [ ] Landing: hamburger opens the sheet nav; demo frame stacks; pricing
      slider draggable by touch; no horizontal scroll anywhere.
- [ ] Dashboard: sidebar collapses to the header hamburger (Sheet).
- [ ] Share page: sidebar becomes a horizontal pill row.

### Automated (should all be green before/after your pass)

```powershell
pnpm --filter web lint
pnpm --filter web exec tsc --noEmit
pnpm --filter web test          # 7 pricing boundary tests
pnpm --filter web build
cd apps\api; uv run pytest      # 206 backend tests
```

## Troubleshooting

- **Hero stuck on skeletons** → API not running, or token typo'd; check the
  browser network tab for `/public/<token>` (404 = bad/revoked token).
- **Overview empty but Live works** → batch writer isn't running (step 1,
  second terminal).
- **Theme toggle "does nothing"** → hard-reload; if it persists, the `.dark`
  class isn't reaching `<html>` — check for console hydration errors.
- **`pnpm --filter web dev` shows old env** → restart it; `NEXT_PUBLIC_*`
  vars are baked in at startup.
