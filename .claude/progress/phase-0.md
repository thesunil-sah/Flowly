# Phase 0 — Foundations & Setup ✅ COMPLETE

**Goal:** a reproducible, runnable monorepo skeleton. Success = reproducibility, not features.
**Outcome:** installs from committed lockfiles, backend + web boot locally, lint/test green, pushed to GitHub, CI green.
**Date:** 2026-07-01

---

## Tools & versions used
| Tool | Version | For |
|---|---|---|
| uv | 0.7.4 | Python deps + venv (`apps/api`) |
| Python | 3.12 | backend runtime |
| FastAPI + pydantic-settings | — | API + config |
| pytest + ruff | 9.1.1 / 0.15 | test + lint/format |
| Node | 24.18.0 (via nvm-windows) | frontend runtime |
| pnpm | 11.9.0 (via corepack) | JS workspaces |
| Next.js | 16.2.9 (App Router, TS strict) | `apps/web` |
| Tailwind | v4 (CSS-first) | styling |
| Git + GitHub Actions | — | VCS + CI |

---

## What we built (step by step)
1. **Root scaffold** — `package.json` (pnpm workspaces, engines node `>=24 <25`), `pnpm-workspace.yaml`, `.nvmrc` (24.18.0), `.npmrc` (`engine-strict=true`), `.gitignore` (written first), `.env.example` (all CLAUDE.md §6 vars), `README.md`, root `CLAUDE.md`.
2. **Backend `apps/api`** — `.python-version` (3.12), `pyproject.toml` (fastapi, uvicorn, pydantic-settings + pytest/httpx/ruff), FastAPI app factory (`main.py`), settings anchored to repo-root `.env` (`config.py`), `GET /health` (zero I/O), empty layering packages `routers/ services/ db/ models/ core/ workers/ migrations/`, `tests/test_health.py`. `uv sync` → committed `uv.lock`.
3. **Tracker `apps/tracker`** — stub `package.json` + no-op `src/script.js` (wrapped, never throws).
4. **CI** — `.github/workflows/ci.yml`: backend job (uv sync --frozen → ruff → pytest) + frontend job (pnpm install --frozen-lockfile → build). Frozen installs prove reproducibility.
5. **Frontend `apps/web`** — Node 24 installed via nvm-windows; pnpm pinned via corepack; `create-next-app` (App Router, TS strict, Tailwind v4, ESLint); deduped to a single root `pnpm-lock.yaml`; native builds allowed in `pnpm-workspace.yaml` (`allowBuilds: sharp, unrs-resolver, @tailwindcss/oxide`); placeholder page renders "Flowly".
6. **Git + push** — `git init`, hygiene gate (no `.env`/`.venv/`/`node_modules/`/`.next/` staged), commits on `main`, pushed to `github.com/thesunil-sah/Flowly`.
7. **Cleanup** — removed obsolete `PHASE-0-NEXT-STEPS.md` and duplicate `.claude/CLAUDE.md`.

---

## Verified
- Backend: `uv run pytest` → 1 passed · `ruff check`/`format --check` clean · live `/health` → `200 {"status":"ok","environment":"local","version":"0.1.0"}` (no DB).
- Frontend: `pnpm install --frozen-lockfile` ok · `pnpm --filter web build` ok · `pnpm --filter web lint` clean · dev server → `200` rendering "Flowly".
- CI: both jobs **green** on GitHub Actions.

## Key commands
```bash
# backend (from apps/api)
uv sync && uv run pytest && uv run uvicorn app.main:app --reload   # :8000/health
# frontend (from root; needs Node 24 -> `nvm use 24.18.0`)
corepack enable && pnpm install && pnpm --filter web dev           # :3000
```

## Open follow-ups (not blocking Phase 0)
- Repo visibility → set to **private** in GitHub settings (was created public).
- New terminals may default to Node 20 → run `nvm use 24.18.0` before pnpm.

## Next
**Phase 1 — Tracking + ingestion:** tracker `script.js` (sendBeacon), `POST /collect` (202, rate-limited), cookieless visitor hash (IP+UA+daily salt), bot filtering, Redis Stream buffer + batch writer → ClickHouse `events` table.
