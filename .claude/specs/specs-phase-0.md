# Flowly — Phase 0 Specification
### Project setup, dependencies & first push

> **Scope:** Phase 0 only. Companion to `CLAUDE.md` (authority on stack/conventions).
> **Goal:** a skeleton that installs, runs, lints clean, has one passing test, and is on GitHub.

---

## 1. Problem statement

Before any feature exists, the team needs a **reproducible, runnable skeleton** so later phases don't fight environment drift (mismatched Python/Node, un-pinned deps, "works on my machine").

Phase 0 delivers a monorepo that installs deterministically from committed lockfiles, boots the API and web app locally, passes Ruff + one test, sets up the empty `routers → services → db` layering, and is pushed to GitHub. The only runtime behaviour is `GET /health` and a placeholder page — success is measured by **reproducibility, not features**.

**Out of scope:** auth, tracker logic, ingestion, DB schemas, Stripe, real UI. Databases need not be running — `/health` must not depend on them.

---

## 2. Functional requirements

All are **MUST** for the phase.

- **FR-P0-1** Root scaffold: `package.json`, `pnpm-workspace.yaml` (`apps/*`), `.gitignore`, `.env.example`, `README.md`.
- **FR-P0-2** Three app folders: `apps/web`, `apps/api`, `apps/tracker` (tracker may be a stub).
- **FR-P0-3** Backend deps: `pyproject.toml` + `.python-version` pin Python 3.12; `uv sync` creates `.venv/` and commits `uv.lock`.
- **FR-P0-4** Frontend deps: Next.js (App Router, TS) in `apps/web`; `pnpm install` writes `pnpm-lock.yaml`.
- **FR-P0-5** Minimal API: app factory `app/main.py`, settings `app/config.py` (pydantic-settings), public `GET /health`.
- **FR-P0-6** Minimal web: Next.js runs in dev and renders a placeholder page.
- **FR-P0-7** One passing test (`tests/test_health.py` → `/health` = 200) and `ruff check` clean.
- **FR-P0-8** Local verification: `uv run uvicorn ...`, `pnpm --filter web dev`, `uv run pytest` all work.
- **FR-P0-9** Git initialised, GitHub repo created and pushed; `.env`, `.venv/`, `node_modules/` ignored.

---

## 3. API contract

### 3.1 `GET /health` (public, no auth)

```jsonc
// Request:  GET /health   (no auth, no body, no params)
// 200 OK
{ "status": "ok", "environment": "local", "version": "0.1.0" }
```
Returns `200` **without touching Postgres/ClickHouse/Redis** — liveness, not readiness. Zero I/O.

### 3.2 Settings — `app/config.py` (pydantic-settings)

```python
class Settings(BaseSettings):
    environment: str = "local"   # ENVIRONMENT
    api_base_url: str            # API_BASE_URL
    web_base_url: str            # WEB_BASE_URL
    # later phases add JWT_*, DATABASE_URL, CLICKHOUSE_*, REDIS_URL, STRIPE_*, …
```

### 3.3 `.env.example` (committed, placeholders only)

Documents **every** var from `CLAUDE.md` §6; only the App group is read in Phase 0. Real `.env` is git-ignored.

```dotenv
ENVIRONMENT=local
API_BASE_URL=http://localhost:8000
WEB_BASE_URL=http://localhost:3000
# scaffolded now, used later (placeholders):
JWT_SECRET=change-me
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/flowly
CLICKHOUSE_HOST=localhost
REDIS_URL=redis://localhost:6379/0
STRIPE_SECRET_KEY=sk_test_xxx
VISITOR_SALT_SECRET=change-me
# …remaining JWT_*, CLICKHOUSE_*, STRIPE_*, EMAIL_API_KEY, TRACKER_SCRIPT_URL
```

### 3.4 File & folder structure produced

```
/
├── apps/
│   ├── web/        package.json · tsconfig.json · next.config.ts · tailwind.config.ts
│   │   └── app/page.tsx                 # placeholder page
│   ├── api/        pyproject.toml · .python-version (3.12) · uv.lock
│   │   ├── tests/test_health.py         # the one passing test
│   │   └── app/    main.py · config.py · routers/ services/ db/ models/ core/  (only health wired)
│   └── tracker/    package.json · src/script.js   # stub in Phase 0
├── .env.example    .gitignore    package.json    pnpm-workspace.yaml (apps/*)
├── pnpm-lock.yaml  README.md     CLAUDE.md
```
`routers/ services/ db/ models/ core/` are created now (empty) so `routers → services → db` holds from day one.

### 3.5 Commands the scaffold supports

```bash
# apps/api
uv sync                                  # install + .venv + uv.lock
uv run uvicorn app.main:app --reload     # GET /health = 200
uv run pytest                            # test_health passes
uv run ruff check . && uv run ruff format .
# apps/web (from root)
pnpm install
pnpm --filter web dev                    # placeholder at :3000
```

---

## 4. Constraints

- **Tooling (fixed, `CLAUDE.md` §5):** Python 3.12 via `.python-version`, managed by **uv** only (no bare `pip`/hand-made venv); **pnpm workspaces** (no npm/yarn); **Ruff** lint/format; **pytest**; **FastAPI** factory + **pydantic-settings**; **Next.js App Router** + TS strict.
- **Reproducibility:** `uv.lock` and `pnpm-lock.yaml` are **committed**; installs are deterministic. Node version SHOULD be pinned.
- **Structure:** layering scaffolded but empty; no feature code, no DB access, no external calls. `/health` does zero I/O.
- **Security hygiene (from commit #1):** `.gitignore` excludes `.env`, `.venv/`, `node_modules/`, `dist/` **before** the first `git add`. No secrets committed; placeholders are obviously fake (`change-me`).
- **Environment:** Postgres/ClickHouse/Redis need **not** be running for Phase 0 to pass.

---

## 5. Edge cases & error handling

- **Wrong Python version** → `uv sync` fails loudly (honours `.python-version`), never builds against another interpreter.
- **Command run in wrong dir** → backend commands are scoped to `apps/api`; misruns error clearly, no stray root venv.
- **Workspace glob broken** → if `pnpm-workspace.yaml` is missing/mis-globbed, apps don't link; fix the file, not per-app installs.
- **Port in use** (`:8000`/`:3000`) → dev server errors on bind; README documents overriding the port.
- **Missing `.env`** → run with sane defaults (`environment="local"`) or a clear error naming the missing var — never a bare stack trace.
- **`/health` while DBs down** → must still return `200`; any DB dependency here is a defect.
- **Ruff failure** → phase is not done; formatting auto-fixes with `ruff format`.
- **Secret / `.venv/` / `node_modules/` committed** → Phase 0 failure; verify `.gitignore` before first commit.
- **Un-committed lockfile** → non-deterministic installs; treat as a failure.

---

## 6. Acceptance criteria

Done only when all pass **and** `CLAUDE.md` §10 Definition of Done holds.

- **AC-P0-1** Fresh clone: `uv sync` and `pnpm install` succeed with no errors and produce committed lockfiles. *(FR-3,4)*
- **AC-P0-2** Root scaffold + three app folders all present. *(FR-1,2)*
- **AC-P0-3** `uv run uvicorn app.main:app --reload` boots; `GET /health` → `200` with **no database running**. *(FR-5)*
- **AC-P0-4** `pnpm --filter web dev` serves a placeholder page at `:3000` with no runtime errors. *(FR-6)*
- **AC-P0-5** `uv run pytest` runs `test_health.py` and the suite is green. *(FR-7)*
- **AC-P0-6** `ruff check .` reports zero errors; `ruff format` leaves no changes. *(FR-7)*
- **AC-P0-7** `config.py` loads `ENVIRONMENT/API_BASE_URL/WEB_BASE_URL`; `/health` reflects `ENVIRONMENT`. *(FR-5)*
- **AC-P0-8** `.gitignore` excludes `.env/.venv/node_modules/dist`; `git status` stages none of them; no secret in history. *(FR-9)*
- **AC-P0-9** Baseline pushed to GitHub; a teammate can clone and reproduce AC-1…AC-6. *(FR-8,9)*
- **AC-P0-10** Following only the README, a new engineer installs, runs both apps, and passes test + lint — no undocumented steps. *(FR-8)*

---

## 7. Open questions
- Node version + pinning mechanism (`.nvmrc` / `engines` / Volta)?
- Is `apps/tracker` a real stub now, or deferred to Phase 2 (folder listed here, script lands in Phase 2)?
- Keep `version` in `/health` now or defer until a versioning scheme exists?
- Add a minimal CI (lint + test on push) in Phase 0 or later?

_Derived from `CLAUDE.md` Phase 0. Update and tick checklist boxes as the scaffold lands._