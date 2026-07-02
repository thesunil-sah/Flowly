# FLOWLY — PHASE 1 IMPLEMENTATION PLAN

## Database & auth system

Derived from CLAUDE.md (§3 architecture, §5 libraries, §9 critical rules, Phase 1 checklist)
and the current Phase 0 scaffold. **This document is the deliverable — no code is written here.**
Code lands on approval.

---

## Changes from the first draft (what this revision fixes)

1. **Docker removed** — no `docker-compose.yml`. Postgres + Redis are run however you prefer (local install or hosted), matching CLAUDE.md's *Local services* note.
2. **Refresh-token exposure reduced** — access token kept **in memory**; refresh token in localStorage with a **7-day** TTL (was 14). XSS-reads-refresh is documented as an accepted MVP risk with a clear upgrade path.
3. **Email normalization** — emails are lowercased + trimmed at the boundary and used consistently for the unique index, login lookup, and rate-limit key.
4. **Password max length (128)** — guards against an argon2 hashing-DoS.
5. **`plan` vs `status` split** — the accounts model separates tier (`plan`) from state (`status`), so "trialing Pro" is representable at billing time (P7).
6. **Login response parity** — unknown email and wrong password return an identical 401; verification runs even for unknown emails to avoid user enumeration.
7. **Signup auto-login** — signup returns tokens so the user lands logged in.
8. **Logout** — client-side token clear + a dashboard button (stateless; server-side revoke is future work).
9. **Migration test** — a test runs `alembic upgrade head` to catch ORM/migration drift.
10. **pytest-asyncio** — `asyncio_mode = auto`, no custom `event_loop` fixture.

---

## 1. Problem statement

Phase 0 left a bare, liveness-only skeleton: the API answers `GET /health` with zero I/O, and the
web app renders a placeholder. There is no database, no data model, and no way for a person to
become a user.

Phase 1 makes Flowly **multi-tenant and authenticated**. A visitor can sign up, log in, stay logged
in across access-token expiry (via refresh), and reach a protected dashboard; every authed request
resolves to exactly one account. This is the security foundation every later phase (sites,
ingestion, live, billing) builds on — so it must be correct: hashed passwords, verified tokens, and
strict per-account (tenant) scoping. Getting this wrong leaks one customer's data to another, so
this phase is unforgiving and gets tests on every path.

**Goal (done looks like):** a user can sign up, log in, and reach a guarded dashboard; the API
issues + verifies JWTs, stores only argon2 password hashes, enforces a login rate limit, and has the
`accounts` / `sites` / `subscriptions` schema under Alembic. Backend tests cover signup, login, token
verify, rejection of missing/invalid tokens, and the migration; lint + tests are green.

**Out of scope (later phases):** the tracking script (P2), `/collect` ingestion (P3), live
websockets (P4), stats queries (P5), the add-site UI flow (P6), Stripe/billing (P7). The
`subscriptions` table is created as baseline schema now but no billing logic touches it yet. The
ClickHouse client is created for connectivity only — no events table until P3.

---

## 2. What we build (deliverables)

**Backend (`apps/api`):**
- Extended `Settings`: DB, JWT, Redis, ClickHouse env vars.
- `db/postgres.py` — async SQLAlchemy engine + session dependency.
- `db/redis.py` — async redis-py client + dependency.
- `db/clickhouse.py` — async clickhouse-connect client (connectivity only).
- `models/` — SQLAlchemy ORM (`Account`, `Site`, `Subscription`) + Pydantic request/response schemas.
- Alembic — initialised, baseline migration creating the three tables.
- `core/security.py` — argon2 hashing, JWT issue/verify, `require_user` dependency.
- `core/ratelimit.py` — Redis fixed-window limiter (used on `/auth/login`; reusable for `/collect` in P3).
- `core/exceptions.py` — typed errors + central handlers (no scattered `HTTPException`).
- `services/auth.py` — signup, login, refresh business logic (with email normalization + login parity).
- `routers/auth.py` — `POST /auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`, and a protected `GET /auth/me`.
- `main.py` wiring — register auth router, CORS locked to the web origin, exception handlers, engine dispose on shutdown.
- `tests/` — conftest fixtures + auth/security/rate-limit/migration tests.

**Frontend (`apps/web`):**
- TanStack Query provider mounted in the root layout.
- `lib/auth.ts` — access token in memory; refresh token storage (get/set/clear).
- `lib/api.ts` — fetch wrapper: base URL + Bearer header + 401→refresh→retry.
- `hooks/` — `useSignup` / `useLogin` / `useMe` / `useLogout`.
- `app/sign-in`, `app/sign-up` — custom auth pages calling `/auth/*`.
- `app/(dashboard)` — route group with a guard layout + placeholder page + logout button.
- `.env.local` — `NEXT_PUBLIC_API_URL`.

**Infra:** none added (no Docker). Postgres + Redis must be running/reachable.

---

## 3. Decisions

### Locked by CLAUDE.md §5 (do not substitute)
- Postgres access: **SQLAlchemy 2.0 async + asyncpg**
- Migrations: **Alembic**
- Password hashing: **argon2 (argon2-cffi)**
- Auth tokens: **PyJWT** — short-lived access + refresh
- Redis: **redis-py (async)**
- Frontend data: **TanStack Query** (no raw fetch in components)

### Decisions made in this revision (override any; see §8)

- **D1 — Token storage.** Access token in **memory** (Query cache / module variable, lost on reload and re-minted via refresh). Refresh token in **localStorage** with a **7-day** TTL. Rationale: keeps the API contract simple (Bearer header, no cross-origin cookie config for `:8000` vs `:3000`) while shrinking the refresh blast radius. **Accepted risk:** an XSS bug can read the refresh token for up to 7 days. **Upgrade path (no API-contract change for access):** move the refresh token to an httpOnly, Secure, SameSite cookie once web + API share a registrable domain in production. *If you'd rather do httpOnly cookies now, say so — it adds CORS-credentials + cookie handling to Steps 9 and 12.*
- **D2 — Refresh strategy.** Stateless rotating refresh JWT (type-tagged `"refresh"`, verified by signature + exp; no DB table). Each refresh issues a new access **and** a new refresh token. **Limitation:** no server-side revoke or reuse-detection before expiry; the 7-day TTL is the blast radius. A `refresh_tokens` table can be added later for logout-all / reuse-detection.
- **D3 — Email normalization.** Lowercase + strip whitespace at the boundary; store the normalized value. The unique index is effectively case-insensitive (store normalized, or a citext/lower index). The login lookup and the rate-limit key both use the normalized email. Prevents duplicate accounts and rate-limit bypass via case changes.
- **D4 — Password policy.** Min **8** chars, **max 128** chars. The max is a DoS guard (argon2 will happily burn CPU on a multi-KB input). Enforced in the Pydantic `SignupRequest`.
- **D5 — Account model: tier vs state.** `plan` holds the **tier** (`free` | `pro` | `business`); a new `status` column holds the **state** (`trialing` | `active` | `past_due` | `canceled`). On signup: `plan="pro"`, `status="trialing"`, `trial_ends_at = now + 7 days`. *(Product decision — flip to `plan="free"` if the trial should be of the free tier. Enforcement of expiry arrives with billing in P7.)*
- **D6 — Login parity.** Unknown email and wrong password return an **identical 401 body**; `services.login` always runs a password verification (against the found hash, or a dummy hash when the email is unknown) so timing doesn't leak which emails exist.
- **D7 — Signup auto-login.** `POST /auth/signup` returns a `TokenResponse` (access + refresh) so the user is logged in immediately and the frontend redirects straight to the dashboard.
- **D8 — Logout.** Client-side: `clearTokens()` + a dashboard button. Stateless — there is no server-side revoke this phase (consistent with D2). Noted as future work if logout-all is needed.
- **D9 — Local services.** Postgres + Redis must be **running and reachable** (local install or hosted); the API connects only via the env-var connection strings. ClickHouse client is created for connectivity only — no schema until P3. **No Docker.**
- **D10 — Rate limiter.** Home-grown Redis fixed-window (no new library — slowapi isn't in §5). Keyed by `(client IP + normalized email)`. **5 attempts / 15 min → 429.** Helper is reused for per-site limiting in P3.
- **D11 — Token TTLs (from `.env`).** Access **900s** (15 min); refresh **604800s** (7 days).
- **D12 — Testing setup.** `pytest-asyncio` with `asyncio_mode = auto` (no custom `event_loop` fixture). A dedicated test database (or per-test transactional rollback). One test runs the real Alembic migration.

---

## 4. Dependencies & requirements to install

### 4.1 Backend runtime deps (from `apps/api`, `uv add …` — never bare pip)
| Package | Purpose |
|---|---|
| `sqlalchemy[asyncio]` | ORM + async engine |
| `asyncpg` | Postgres async driver |
| `alembic` | migrations |
| `pyjwt` | JWT encode/decode |
| `argon2-cffi` | password hashing |
| `redis` | async Redis client (rate limit now; live/usage later) |
| `clickhouse-connect` | ClickHouse client (connectivity only this phase) |
| `pydantic[email]` | `EmailStr` validation for signup |

`DATABASE_URL` in `.env` already uses the `postgresql+asyncpg://` driver.

### 4.2 Backend dev deps (`uv add --dev …`)
- `pytest-asyncio` (async tests; first needed now). `pytest`, `httpx`, `ruff` already present.

### 4.3 Frontend deps (from repo root, `pnpm add … --filter web`)
- `@tanstack/react-query`
- `@tanstack/react-query-devtools` (add with `-D`)

### 4.4 Services / requirements
- **Postgres + Redis running and reachable** (local install or a hosted instance) — no Docker.
- Real `.env` at repo root (copy from `.env.example`). Set a **strong random `JWT_SECRET`** (do not keep `change-me`; never commit `.env` — already ignored).
- Env vars consumed this phase (all already in `.env.example`): `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_TTL`, `REFRESH_TOKEN_TTL`, `DATABASE_URL`, `REDIS_URL`, `CLICKHOUSE_HOST/USER/PASSWORD/DB`, `WEB_BASE_URL`.
- **No new env var is introduced.** If that changes, add it to `.env.example` in the same step (CLAUDE.md §6).

---

## STEP-BY-STEP

### STEP 0 — Pre-flight (services + env, before any code)
- **0.1** Ensure **Postgres and Redis are running and reachable** (local install or hosted). Create the database (e.g. `flowly`) and a separate `flowly_test` for tests.
- **0.2** Copy `.env.example → .env` at repo **root**. Set `ENVIRONMENT=local`, a strong random `JWT_SECRET`, and confirm `DATABASE_URL` / `REDIS_URL` point at your running services. Confirm `.env` is git-ignored (it is).
- **0.3** Confirm connectivity before writing app code: Postgres reachable, Redis reachable (a quick `psql` / `redis-cli ping`, or defer to Step 5's `alembic upgrade` as the first real Postgres check).

### STEP 1 — Backend dependencies
- **1.1** From `apps/api`, add the runtime deps (§4.1) and dev deps (§4.2) via `uv add` / `uv add --dev`. Commit the updated `pyproject.toml` + `uv.lock`.

### STEP 2 — Config (extend Settings)
- **2.1** In `app/config.py` add typed fields, keeping the existing root-anchored `env_file` and `extra="ignore"`:
  - `database_url: str`
  - `jwt_secret: str`, `jwt_algorithm: str = "HS256"`
  - `access_token_ttl: int = 900`, `refresh_token_ttl: int = 604800`  *(7 days — D11)*
  - `redis_url: str`
  - `clickhouse_host/user/password/db`
  - `web_base_url: str`
- Give safe local defaults where reasonable so importing config never crashes without a full `.env` (mirrors the Phase 0 pattern). `jwt_secret` may have a dev-only default, but the plan notes **production MUST override it**.

### STEP 3 — DB clients (`db/`)
- **3.1** `db/postgres.py` — async engine from `settings.database_url` + `async_sessionmaker`; expose a `get_session` dependency yielding an `AsyncSession` (commit/rollback/close around the request). Engine is module-level but connects **lazily**, so importing it doesn't require Postgres — this keeps the existing `/health` test DB-free.
- **3.2** `db/redis.py` — async redis client from `settings.redis_url`; expose `get_redis`. Lazy connect.
- **3.3** `db/clickhouse.py` — async clickhouse-connect client factory from `CLICKHOUSE_*`. Connectivity/helper only this phase; no schema.
- **3.4** RULE (CLAUDE.md §3): `db/` holds client setup + raw helpers only — no business rules. Services call `db/`, never the reverse.

### STEP 4 — Models (`models/`)
- **4.1** ORM (SQLAlchemy 2.0 declarative), matching CLAUDE.md Core data model, **with the D5 tier/state split**:
  - `Base(DeclarativeBase)`.
  - `Account`: `id`, `email` (unique, indexed, **stored normalized**), `password_hash`, `plan` (`free|pro|business`), `status` (`trialing|active|past_due|canceled`), `trial_ends_at`, `created_at`.
  - `Site`: `id`, `account_id` (FK→accounts), `site_id` (public, unique, indexed), `domain`, `created_at`.
  - `Subscription`: `id`, `account_id` (FK), `stripe_customer_id`, `stripe_subscription_id`, `status`, `plan`, `current_period_end`. *(Created now; unused until P7.)*
  - All timestamps **UTC** (CLAUDE.md §4).
- **4.2** Pydantic v2 request/response schemas (validate at the boundary):
  - `SignupRequest` (`email: EmailStr`, `password: str` — **min 8, max 128**, D4).
  - `LoginRequest` (`email: EmailStr`, `password: str`).
  - `TokenResponse` (`access_token`, `refresh_token`, `token_type="bearer"`, `expires_in`).
  - `RefreshRequest` (`refresh_token`).
  - `AccountOut` (`id`, `email`, `plan`, `status`, `trial_ends_at`) — **never** includes `password_hash`. Used by `GET /auth/me`.
  - Normalize `email` to lowercase+trim in a validator so every entry point is consistent (D3).
- **4.3** Keep ORM and Pydantic schemas as separate types; convert in the service layer. Never return an ORM object with the hash to the client.

### STEP 5 — Alembic baseline + migrate
- **5.1** Initialise Alembic under `apps/api` (`alembic.ini` at `apps/api` root; `script_location = app/migrations`). Point `env.py` at the async engine and set `target_metadata = Base.metadata` so autogenerate sees the ORM.
- **5.2** Autogenerate the baseline migration creating `accounts`, `sites`, `subscriptions` (unique indexes on `accounts.email` and `sites.site_id`, plus the FKs). **REVIEW the generated migration before applying** (CLAUDE.md §7: explain schema-changing actions).
- **5.3** Apply: `uv run alembic upgrade head`. This is also the first real proof of Postgres connectivity + `DATABASE_URL`. Commit the migration file.

### STEP 6 — `core/security.py` (the security surface — do it right)
- **6.1** Password hashing (argon2-cffi): `hash_password(plain) -> str`, `verify_password(plain, hash) -> bool`. **Never log either argument.**
- **6.2** JWT (PyJWT), signed with `settings.jwt_secret` / `jwt_algorithm`:
  - `create_access_token(account_id)`: claims `sub=account_id`, `type="access"`, `exp=now+access_token_ttl`.
  - `create_refresh_token(account_id)`: `type="refresh"`, `exp=now+refresh_token_ttl`.
  - `decode_token(token, expected_type)`: verify signature + exp **and** that the `type` claim matches — reject an access token used as refresh and vice-versa. Raise a typed `AuthError` on any failure.
- **6.3** `require_user` dependency: read the Bearer token from the `Authorization` header, decode as an **access** token, load the `Account` by `sub` via `get_session`, and **return the account** (tenant scope = this account). Missing/invalid/expired → 401. Every authed route depends on this; nothing trusts a raw id from the client. *(CLAUDE.md §9: verify token on every authed route; tenant isolation.)*

### STEP 7 — `core/ratelimit` + `core/exceptions`
- **7.1** Redis fixed-window limiter (`core/ratelimit.py`): a dependency/helper that, given a key + limit + window, `INCR`s a Redis counter with a TTL and raises a typed `RateLimitError` (→429) when exceeded. Key = `(client IP + normalized email)`. (D9/D10)
- **7.2** `core/exceptions.py`: typed exceptions (`AuthError`→401, `RateLimitError`→429, `ConflictError`→409 for duplicate email, etc.) plus exception-handler functions. Services raise these; handlers translate to HTTP — no scattered `HTTPException` in services (CLAUDE.md §4).

### STEP 8 — `services/auth.py` (business logic)
- **8.1** `signup(email, password)`: normalize email; reject if it exists (`ConflictError`→409); hash the password; create the `Account` with `plan="pro"`, `status="trialing"`, `trial_ends_at = now+7d` (D5); issue access + refresh; return them (D7 auto-login).
- **8.2** `login(email, password)`: normalize email; load account. **Always run `verify_password`** — against the real hash, or a dummy hash if the email is unknown — then decide success. On failure raise a single generic `AuthError` (identical body for unknown-email and wrong-password) (D6). On success issue access + refresh.
- **8.3** `refresh(refresh_token)`: `decode_token(expected_type="refresh")`; issue a **new access token and a rotated refresh token** (D2). Invalid/expired → `AuthError`.
- **8.4** Services call `db/` (session passed in from the router) and `core/security`; they contain no HTTP objects.

### STEP 9 — `routers/auth.py` + `main.py` wiring
- **9.1** `routers/auth.py` (thin — parse request, call service, return schema):
  - `POST /auth/signup` → `services.signup` → **201 + TokenResponse** (D7).
  - `POST /auth/login` → rate-limit dep (Step 7) → `services.login` → `TokenResponse`.
  - `POST /auth/refresh` → `services.refresh` → `TokenResponse`.
  - `POST /auth/logout` → 204. Stateless — no server state to clear this phase (D8); present for a clean client contract and future revoke.
  - `GET /auth/me` → `Depends(require_user)` → `AccountOut`. (Protected route used by the frontend guard + tests.)
- **9.2** `main.py`:
  - Register the auth router.
  - Add CORS **locked to `settings.web_base_url`** (dashboard API is private). Do **not** open CORS to all origins — that's only for `/collect` in P3 (CLAUDE.md §9).
  - Register the exception handlers from `core/exceptions`.
  - Add a shutdown hook to dispose the engine / close redis. **Do not** add a mandatory DB ping on startup — `/health` must stay zero-I/O and its test must pass with no Postgres running.

### STEP 10 — Backend tests (`tests/`)
- **10.1** `conftest.py`: async test client (httpx `ASGITransport`); `pytest-asyncio` with `asyncio_mode = auto` (no custom `event_loop` fixture) (D12); a DB fixture using `flowly_test` or per-test transactional rollback; override `get_session` to the test session.
- **10.2** `test_migration.py`: run `alembic upgrade head` against the test DB and assert the three tables + indexes exist. Catches ORM/migration drift (D12).
- **10.3** `test_security.py`: hash/verify roundtrip (wrong password fails); access/refresh encode→decode roundtrip; `decode` rejects wrong type; expired token rejected.
- **10.4** `test_auth.py` (the unforgiving paths, CLAUDE.md §8):
  - signup creates an account and stores a **hash** (never plaintext); returns tokens (D7).
  - duplicate email → 409; case-variant email is treated as the same account (D3).
  - login success → access + refresh; wrong password → 401; **unknown email → same 401 body** (D6).
  - refresh returns a new access token; a refresh token can't be used as access (and vice-versa) → 401.
  - `GET /auth/me` with a valid token → 200 + account; missing token → 401; invalid/expired → 401.
  - password over 128 chars → 422 (D4).
- **10.5** `test_ratelimit.py`: exceeding the login attempt limit → 429 (D10).
- **10.6** Run full suite + ruff; all green before commit. Every later bug fix adds a regression test.

### STEP 11 — Frontend: provider + env
- **11.1** Add `@tanstack/react-query` (+ devtools). Create `app/providers.tsx` (`"use client"`) wrapping children in `QueryClientProvider`; mount it inside the existing `app/layout.tsx` around `{children}`.
- **11.2** Add `apps/web/.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000` (`.env*` is already git-ignored).

### STEP 12 — Frontend: API client + token storage (`lib/`)
- **12.1** `lib/auth.ts`: **access token in memory** (module variable / Query cache); refresh token in **localStorage** with the 7-day expectation. `getAccessToken` / `getRefreshToken` / `setTokens` / `clearTokens`, guarded for SSR (only touch `window` on the client) (D1).
- **12.2** `lib/api.ts`: a typed fetch wrapper that prefixes `NEXT_PUBLIC_API_URL`, sets `Authorization: Bearer <access>` when present, parses JSON, and on **401** tries **one** `/auth/refresh` then retries; if refresh fails, `clearTokens` and signal logged-out. No component calls `fetch` directly (CLAUDE.md §4).

### STEP 13 — Frontend: auth pages + hooks
- **13.1** `hooks/`: `useSignup` + `useLogin` (Query mutations calling `/auth/signup` / `/auth/login` via `lib/api`, storing tokens on success); `useMe` (query hitting `/auth/me` to validate the session); `useLogout` (`clearTokens` + `/auth/logout` + redirect).
- **13.2** `app/sign-up/page.tsx` and `app/sign-in/page.tsx`: client components with an email + password form, using the hooks, showing validation/errors, redirecting to the dashboard on success.

### STEP 14 — Frontend: dashboard guard
- **14.1** Create the `app/(dashboard)` route group with a layout that guards access: if there's no token / `useMe` fails, redirect to `/sign-in`; otherwise render (D1 — client-side guard).
- **14.2** `app/(dashboard)/page.tsx`: a minimal placeholder ("Welcome, <email>") plus a **logout button** (D8), proving the full loop works. (Real metrics arrive in P5.)
- **14.3** *(Optional)* move the current marketing placeholder into an `app/(marketing)` group; not required for Phase 1 done.

---

## VERIFICATION (end-to-end)

**Backend** (from `apps/api`, services running + `.env` set):
```
uv sync                                       # deps from committed lock
uv run alembic upgrade head                   # tables created (real DB check)
uv run uvicorn app.main:app --reload
  GET  /health                → 200, still zero-I/O (unchanged)
  POST /auth/signup           → 201 + access+refresh; accounts row holds a HASH (never plaintext)
  POST /auth/login            → 200 + access+refresh
  GET  /auth/me (no token)    → 401
  GET  /auth/me (Bearer)      → 200 + account
  POST /auth/refresh          → 200 + new access (+ rotated refresh)
  login unknown email         → 401, identical body to wrong-password
  6th rapid bad login         → 429
uv run pytest                                 # auth/security/ratelimit/migration all green
uv run ruff check . && uv run ruff format --check .
```

**Frontend** (from repo root, API running):
```
pnpm install
pnpm --filter web dev
  /sign-up  → create account → redirected to dashboard
  reload    → still authenticated (access re-minted from stored refresh)
  /(dashboard) with no token → redirected to /sign-in
  logout button → tokens cleared → back to /sign-in
pnpm --filter web build                       # builds clean
pnpm --filter web lint
```

Full loop: sign up → land on guarded dashboard → `/auth/me` resolves the account.

---

## DEFINITION OF DONE (maps CLAUDE.md §10)

- [ ] `routers → services → db` layering respected; routers stay thin; no query/JWT logic in a router.
- [ ] Only §5 libraries used (SQLAlchemy async+asyncpg, Alembic, PyJWT, argon2-cffi, redis-py, TanStack Query); nothing added outside §5 without updating §5. (Rate limiter is home-grown — no new dep.)
- [ ] Passwords argon2-hashed; hashes/tokens/passwords **never** logged.
- [ ] JWT verified on every authed route via `require_user`; access short-lived + refresh; tenant scoping (token → account) enforced.
- [ ] Emails normalized everywhere (unique index, login lookup, rate-limit key). *(new)*
- [ ] Password length capped (max 128). *(new)*
- [ ] `plan` (tier) and `status` (state) modeled separately. *(new)*
- [ ] Unknown email and wrong password return an identical 401. *(new)*
- [ ] Dashboard API CORS locked to the web origin (not open).
- [ ] `/auth/login` rate-limited.
- [ ] Alembic baseline creates `accounts`/`sites`/`subscriptions`; migration reviewed before apply; a test runs the migration. *(migration test new)*
- [ ] Tests cover signup, login, token verify, rejection of missing/invalid tokens, and rate limit; lint + tests green locally.
- [ ] `/health` still zero-I/O; its test passes with no Postgres running.
- [ ] No new env var introduced (all already in `.env.example`); real `.env` has a strong `JWT_SECRET` and is git-ignored.
- [ ] CLAUDE.md Phase 1 checklist boxes ticked; "Last updated" date bumped.

---

## OPEN ITEMS (my defaults are in use; flip any and I'll adjust)

- **O1 — Refresh token storage (D1).** Default: refresh in localStorage, 7-day TTL, accepted XSS risk. Alternative: httpOnly Secure cookie now (adds CORS-credentials + cookie handling). **This is the one I'd most like you to confirm.**
- **O2 — Signup default plan (D5).** Default: `plan="pro"`, `status="trialing"`. Alternative: `plan="free"` if the 7-day trial is of the free tier.
- **O3 — Access-token lifetime (D11).** Default 15 min. Shorter = safer but more refreshes.
- **O4 — Logout scope (D8).** Default: stateless client clear. Alternative: add a `refresh_tokens` table now for server-side revoke / logout-all.
- **O5 — Login rate limit (D10).** Default 5 / 15 min per (IP, email). Adjust thresholds if too strict/loose.