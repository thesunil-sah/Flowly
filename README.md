# Flowly

Privacy-first, cookieless web-traffic analytics SaaS. This repository is a pnpm +
uv monorepo with three apps:

| App | Path | Stack |
|---|---|---|
| Dashboard / marketing | `apps/web` | Next.js (App Router, TypeScript strict) |
| Backend API | `apps/api` | FastAPI + uv (Python 3.12) |
| Tracking script | `apps/tracker` | Vanilla JS (stub in Phase 0) |

> **Phase 0 status:** reproducible skeleton only. The only runtime behaviour is
> `GET /health` and a placeholder web page. See `CLAUDE.md` for the full spec.

---

## Prerequisites

- **Node 24** — pinned in `.nvmrc`. With nvm: `nvm install && nvm use`. The repo sets
  `engine-strict=true`, so pnpm **refuses to run on the wrong Node version**.
- **corepack** (bundled with Node) — activates the pinned pnpm: `corepack enable`.
- **uv** — Python package/venv manager: <https://docs.astral.sh/uv/>. Manages Python 3.12
  automatically via `apps/api/.python-version`. Never use bare `pip` or a hand-made venv.
- Postgres / ClickHouse / Redis are **not required** for Phase 0 (`/health` does zero I/O).

## Setup

```bash
# 1. Environment (single .env at the repo root)
cp .env.example .env        # placeholders are fine for Phase 0

# 2. Frontend deps (from repo root)
corepack enable
pnpm install                # writes the single root pnpm-lock.yaml

# 3. Backend deps
cd apps/api && uv sync      # creates .venv/ and writes uv.lock
```

## Run

**Backend** (from `apps/api`):
```bash
uv run uvicorn app.main:app --reload      # http://localhost:8000
curl http://localhost:8000/health          # {"status":"ok","environment":"local","version":"0.1.0"}
```

**Frontend** (from repo root):
```bash
pnpm --filter web dev                       # http://localhost:3000
```

## Test & lint

```bash
# Backend (from apps/api)
uv run pytest                               # test_health passes
uv run ruff check .                         # zero errors
uv run ruff format --check .                # no changes

# Frontend (from repo root)
pnpm --filter web build                     # production build
pnpm --filter web lint
```

## Port overrides

If `:8000` or `:3000` is in use:

```bash
uv run uvicorn app.main:app --reload --port 8001     # API
pnpm --filter web dev -- --port 3001                 # web
```

## Troubleshooting

- **`pnpm` errors about Node version** — you're not on Node 24. Run `nvm use` (reads `.nvmrc`).
  This is intentional (`engine-strict`), not a bug.
- **Backend command run from the wrong directory** — all `uv run ...` commands are scoped to
  `apps/api`. Run them there; there should be no stray venv at the repo root.
- **Missing `.env`** — the API falls back to sane defaults (`ENVIRONMENT=local`); it won't crash.
- **Lockfiles** — `uv.lock` and `pnpm-lock.yaml` are committed. Don't delete them; installs
  must stay deterministic.
