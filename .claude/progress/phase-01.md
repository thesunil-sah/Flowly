# Phase 1 — Database & Auth System ✅ COMPLETE

**Goal:** a user can sign up, log in, and reach a protected dashboard — with hashed
passwords, verified JWTs, and strict per-account (tenant) scoping.
**Outcome:** full auth system live end-to-end against real Postgres + Redis, including
email verification, password reset, and Google/GitHub social login. 29 backend tests
pass; frontend builds + lints clean.
**Date:** 2026-07-02
**Branch:** `phase-1-auth` (commit `740a125`)

> Scope note: the checklist items in CLAUDE.md Phase 1 are all done. Email verification,
> username, password reset, and social OAuth were built on top as requested extensions.

---

## Tools & versions used
| Tool | Version | For |
|---|---|---|
| SQLAlchemy (async) + asyncpg | 2.0 / 0.31 | Postgres ORM + driver |
| Alembic | 1.18 | migrations |
| PyJWT | 2.13 | access/refresh/reset tokens |
| argon2-cffi | 25.1 | password hashing |
| redis-py | 8.0 | rate limit, codes, OAuth state |
| clickhouse-connect | 1.4 | CH client (connectivity only) |
| httpx | (runtime) | OAuth provider calls |
| pytest + pytest-asyncio | — | tests (`asyncio_mode=auto`) |
| aiosqlite + fakeredis | — | test-only: portable DB/Redis |
| TanStack Query | 5 | frontend data hooks |
| Postgres / Redis | 16 / running | local services |

---

## What we built (by area)

### Backend (`apps/api`)
1. **Config** — extended `Settings` with DB, JWT, Redis, ClickHouse, Email, and Social
   OAuth vars (root-anchored `.env`, safe defaults).
2. **DB clients** (`db/`) — async `postgres.py` (engine + `get_session`), `redis.py`,
   `clickhouse.py`; all lazy-connect so `/health` stays zero-I/O.
3. **Models** (`models/`) — ORM `Account`, `Site`, `Subscription`, `Identity`
   (UUID PKs, UTC timestamps, tier `plan` vs lifecycle `status`); Pydantic request/
   response schemas with email/username normalization + password bounds (8–128).
4. **Migrations** — Alembic baseline (`0001`) + `username`/`email_verified_at` (`c134…`,
   backfilled) + `identities` table & nullable `password_hash` (`0b51…`). All applied.
5. **Security** (`core/security.py`) — argon2 hash/verify; type-tagged access/refresh/
   reset JWTs; `require_user` dependency (token → account tenant scope).
6. **Cross-cutting** (`core/`) — Redis fixed-window rate limiter (login: 5/15 min);
   typed exceptions + central handlers (no scattered `HTTPException`).
7. **Services** (`services/`)
   - `auth.py` — signup (unverified + code), login (email **or** username, verified
     check, timing parity), refresh (rotating), forgot/verify-reset/reset-password,
     and `oauth_login` (create-or-link-by-verified-email).
   - `verification.py` — 6-digit codes in Redis (10-min TTL, cooldown + attempt caps).
   - `email.py` — dev stub (logs codes); real Resend/Postmark is a one-module swap.
   - `oauth.py` — Google + GitHub configs, CSRF `state`, code exchange, profile fetch.
8. **Routers** (`routers/`) — `auth.py` (signup, verify-email, resend-code, login,
   forgot-password, verify-reset-code, reset-password, refresh, logout, `/me`);
   `oauth.py` (`/auth/oauth/{provider}/start` + `/callback`). `main.py` wires routers,
   CORS locked to the web origin, exception handlers, shutdown cleanup.
9. **Tests** (29 passing) — `test_security`, `test_auth`, `test_password_reset`,
   `test_ratelimit`, `test_oauth`, `test_migration`, `test_health`.

### Frontend (`apps/web`)
1. **Providers/env** — TanStack Query provider in the root layout; `NEXT_PUBLIC_API_URL`.
2. **`lib/`** — `auth.ts` (in-memory access token + remember-me local/session refresh),
   `api.ts` (fetch wrapper: Bearer + 401→refresh→retry, `oauthStartUrl`), `constants.ts`.
3. **`hooks/useAuth.ts`** — signup, verify-email, resend, login, forgot, verify-reset,
   reset, me, logout.
4. **Pages** — multi-step **sign-up** (username/email/password/confirm/remember → code),
   **sign-in** (email/username + remember + social + forgot link), **forgot-password**
   (email → code), **reset-password** (new password), **/auth/callback** (OAuth token
   capture), and the guarded **(dashboard)** with logout.
5. **Components** — shared form kit (`form.tsx`), `SocialButtons` (Google + GitHub).

### Infra / env
- Postgres role `flowly` + database `flowly` created; migrations applied.
- Node switched to 24 (nvm) for pnpm/engine-strict.
- New env vars added to `.env.example`: `EMAIL_FROM`, `GOOGLE_*`, `GITHUB_*`.

---

## Verified
- **Backend:** `uv run pytest` → 29 passed; `ruff check`/`format --check` clean.
- **Migrations:** `alembic upgrade head` applied to Postgres; schema + indexes confirmed.
- **Live (real PG + Redis):** signup → 403 before verify → verify-email → login by
  email/username → refresh → `/auth/me`; forgot → reset → old pw 401 / new pw 200;
  login rate limit `[401×5, 429]`; argon2 hash stored, no plaintext leak.
- **Social:** Google + GitHub sign-in completed in-browser; both linked to one account
  (`identities`: google + github → same passwordless, verified account).
- **Frontend:** `pnpm --filter web build` + ESLint clean; full loop works in-browser.

---

## Decisions (as built; flippable)
- Token storage: in-memory access + refresh in localStorage (remember) / sessionStorage.
- Refresh: stateless rotating JWT (7-day). Reset: short-lived reset JWT.
- OAuth linking: link to existing account **only when provider email is verified**.
- Email: dev stub (codes logged/shown locally) until a provider key is set.
- Tests: in-memory SQLite + fakeredis for portability (CI needs no services).

## Open / follow-ups
- Push done; PR to `main` to be opened via GitHub UI (gh CLI not installed).
- Rotate the Google + GitHub secrets (shared in plaintext during setup).
- Later: real email provider; optional httpOnly-cookie refresh; real `flowly_test` PG.

---

## Key commands
```bash
# backend (apps/api)
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest -q
uv run ruff check . && uv run ruff format --check .

# frontend (repo root)
pnpm --filter web dev
pnpm --filter web build
```
