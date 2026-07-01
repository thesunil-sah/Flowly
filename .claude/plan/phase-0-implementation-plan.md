===============================================================================
FLOWLY — PHASE 0 IMPLEMENTATION PLAN (step-by-step)
Project setup, dependencies & first push
-------------------------------------------------------------------------------
Derived from .claude/specs/specs-phase-0.md and CLAUDE.md.
This document is the deliverable. On approval, save to .claude/plans/0-phase.md.
No feature code is written; only scaffolding. Success = reproducibility, not features.
Revision: fixes applied (Node 24 LTS, gh check, .env anchoring, engine-strict,
tightened engines range, frozen CI installs, Tailwind v4 awareness, pinned pnpm).
===============================================================================

CONTEXT
-------------------------------------------------------------------------------
Flowly is a privacy-first, cookieless web-analytics SaaS. Phase 0 delivers a
reproducible monorepo skeleton: installs deterministically from committed
lockfiles, boots the API and web app locally, passes Ruff + one test, sets up the
empty routers -> services -> db layering, and is pushed to GitHub. The only
runtime behaviour is GET /health (zero I/O) and a placeholder web page.


DECISIONS (locked)
-------------------------------------------------------------------------------
- Node pinning:   .nvmrc = 24.15.0 (current Active LTS, supported to Apr 2028)
                  + engines.node ">=24 <25" in root package.json.
                  (Node 20 is EOL as of 30 Apr 2026 — do NOT use it.)
- pnpm:           activate via corepack; pin exact version in packageManager
                  (corepack use pnpm@latest writes it). No global install.
- Enforcement:    .npmrc with engine-strict=true so engines is enforced, not advisory.
- .env location:  single .env at repo ROOT; config.py anchors to root via __file__
                  (cwd-independent). .env.example at root; real .env git-ignored.
- CI:             GitHub Actions on push/PR — Python (uv sync --frozen, ruff, pytest)
                  + JS (pnpm install --frozen-lockfile, build). Node 24.
- /health:        keep "version": "0.1.0" now.
- apps/tracker:   real stub now (folder + package.json + no-op src/script.js).
- Tailwind:       accept whatever create-next-app scaffolds (currently v4, CSS-first).
                  Do NOT hand-roll v3 config that won't match.


===============================================================================
STEP 0 — PRE-FLIGHT (verify the machine before writing anything)
===============================================================================
Run and confirm each. Fix any that fail before continuing.

  uv --version            # expect 0.7.x  (present)
  python --version        # expect 3.12.x (present)
  git --version           # expect 2.4x   (present)
  node --version          # MUST be 24.x — machine currently has 20.18.0 (EOL)
  gh --version            # GitHub CLI — was NOT in the verified list; confirm it
  gh auth status          # confirm authenticated, else Step 6 push will fail

Actions if a check fails:
  - Node not 24: install Node 24 LTS (nvm install 24 / fnm install 24 / installer),
    then `nvm use 24`. Re-check `node --version` shows 24.x.
  - gh missing or unauthenticated: either `gh auth login`, OR skip gh in Step 6
    and use the manual GitHub fallback (create repo in UI, then add remote + push).
  - corepack: `corepack --version` (bundled with Node). Run `corepack enable` once.


===============================================================================
STEP 1 — ROOT SCAFFOLD  (write .gitignore FIRST — hygiene before any add)
===============================================================================
Create these at the repo root, in this order.

1.1  .gitignore  (BEFORE anything else, before `git init`)
     Exclude:
       .env
       .env.*
       !.env.example
       .venv/
       node_modules/
       dist/
       .next/
       __pycache__/
       .pytest_cache/
       .ruff_cache/
       # OS / editor noise
       .DS_Store
       Thumbs.db
       .idea/
       .vscode/

1.2  package.json  (private root; workspaces via pnpm-workspace.yaml)
     {
       "name": "flowly",
       "private": true,
       "engines": { "node": ">=24 <25", "pnpm": ">=10" },
       "packageManager": "pnpm@10.0.0",   // replaced with exact value in Step 3.1
       "scripts": {
         "dev:web": "pnpm --filter web dev",
         "build:web": "pnpm --filter web build",
         "lint:web": "pnpm --filter web lint"
       }
     }

1.3  pnpm-workspace.yaml
       packages:
         - "apps/*"

1.4  .nvmrc
       24.15.0

1.5  .npmrc            # makes engines enforced (pnpm won't run on wrong Node)
       engine-strict=true
       # if Next hoisting causes issues later, revisit node-linker here

1.6  .env.example      # every var from CLAUDE.md §6; App group live now, rest fake
       # --- App (used in Phase 0) ---
       ENVIRONMENT=local
       API_BASE_URL=http://localhost:8000
       WEB_BASE_URL=http://localhost:3000
       # --- Scaffolded now, consumed later (obviously-fake placeholders) ---
       JWT_SECRET=change-me
       JWT_ALGORITHM=HS256
       ACCESS_TOKEN_TTL=900
       REFRESH_TOKEN_TTL=1209600
       DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/flowly
       CLICKHOUSE_HOST=localhost
       CLICKHOUSE_USER=default
       CLICKHOUSE_PASSWORD=
       CLICKHOUSE_DB=flowly
       REDIS_URL=redis://localhost:6379/0
       STRIPE_SECRET_KEY=sk_test_xxx
       STRIPE_WEBHOOK_SECRET=whsec_xxx
       STRIPE_PRICE_PRO=price_xxx
       STRIPE_PRICE_BUSINESS=price_xxx
       EMAIL_API_KEY=xxx
       VISITOR_SALT_SECRET=change-me
       TRACKER_SCRIPT_URL=http://localhost:8000/script.js

1.7  README.md
     Must let a new engineer reproduce AC-1..AC-6 with NO undocumented steps.
     Sections: prerequisites (uv, Node 24 via nvm/.nvmrc, corepack); setup
     (copy .env.example -> .env at ROOT); backend run/test/lint commands;
     frontend run/build commands; port-override notes (:8000 / :3000); troubleshooting.

1.8  CLAUDE.md
     Write the project guide to disk at root (currently only in Claude's context;
     the spec tree and README both reference it at root).


===============================================================================
STEP 2 — BACKEND  apps/api
===============================================================================
2.1  Create apps/api/.python-version
       3.12

2.2  Create apps/api/pyproject.toml
       - project deps:  fastapi, "uvicorn[standard]", pydantic-settings
       - dev deps:      pytest, httpx (for TestClient), ruff
                        (pytest-asyncio NOT needed yet — health test is sync;
                         add it with the first async test in Phase 1+)
       - [tool.ruff]:   line-length = 100, target-version = "py312"
       Add deps with `uv add ...` / `uv add --dev ...` — NEVER bare pip.

2.3  Create the app package (each dir gets __init__.py):
       apps/api/app/__init__.py
       apps/api/app/main.py
       apps/api/app/config.py
       apps/api/app/routers/__init__.py
       apps/api/app/routers/health.py
       apps/api/app/services/__init__.py     # empty, present for layering
       apps/api/app/db/__init__.py           # empty
       apps/api/app/models/__init__.py       # empty
       apps/api/app/core/__init__.py         # empty
     (workers/ and migrations/ are intentionally OMITTED in Phase 0 — they land
      in their own phases. Keep only the five layering packages above.)

2.4  app/config.py  — anchor env_file to repo ROOT (cwd-independent), sane defaults
     -------------------------------------------------------------------------
     from pathlib import Path
     from pydantic_settings import BaseSettings, SettingsConfigDict

     # apps/api/app/config.py -> parents[3] == repo root.
     # If the folder depth changes, update this index.
     _ROOT = Path(__file__).resolve().parents[3]

     class Settings(BaseSettings):
         model_config = SettingsConfigDict(
             env_file=_ROOT / ".env",
             env_file_encoding="utf-8",
             extra="ignore",
         )
         environment: str = "local"                       # ENVIRONMENT
         api_base_url: str = "http://localhost:8000"       # API_BASE_URL
         web_base_url: str = "http://localhost:3000"       # WEB_BASE_URL

     settings = Settings()
     -------------------------------------------------------------------------
     Defaults mean a missing .env does NOT crash the app (edge case §5).

2.5  app/routers/health.py  — thin, zero I/O, imports nothing from db/
     -------------------------------------------------------------------------
     from fastapi import APIRouter
     from app.config import settings

     router = APIRouter()

     @router.get("/health")
     async def health() -> dict[str, str]:
         return {
             "status": "ok",
             "environment": settings.environment,
             "version": "0.1.0",
         }
     -------------------------------------------------------------------------

2.6  app/main.py  — app factory, register router (NO empty middleware hook —
                     add middleware when something actually needs it)
     -------------------------------------------------------------------------
     from fastapi import FastAPI
     from app.routers import health

     def create_app() -> FastAPI:
         app = FastAPI(title="Flowly API")
         app.include_router(health.router)
         return app

     app = create_app()
     -------------------------------------------------------------------------

2.7  tests/__init__.py  and  tests/test_health.py  — runs with NO database
     -------------------------------------------------------------------------
     from fastapi.testclient import TestClient
     from app.main import app

     def test_health_ok() -> None:
         client = TestClient(app)
         resp = client.get("/health")
         assert resp.status_code == 200
         body = resp.json()
         assert body["status"] == "ok"
         assert "environment" in body
     -------------------------------------------------------------------------

2.8  Install + lock:
       cd apps/api
       uv sync            # creates .venv/ and writes uv.lock (COMMIT uv.lock)


===============================================================================
STEP 3 — FRONTEND  apps/web  (scaffold with the CLI, then trim)
===============================================================================
3.1  Enable + pin pnpm (writes exact packageManager version to root package.json):
       corepack enable
       corepack use pnpm@latest        # run at repo root; updates packageManager pin
     Confirm root package.json "packageManager" now shows an EXACT pnpm version
     (e.g. pnpm@10.x.y) — Corepack rejects ranges.

3.2  Scaffold Next.js from the apps/ dir (do NOT hand-roll config):
       cd apps
       pnpm create next-app@latest web --ts --app --tailwind --eslint \
            --import-alias "@/*" --use-pnpm
     NOTE: current create-next-app installs Tailwind v4 (CSS-first: globals.css
     uses `@import "tailwindcss";`, PostCSS uses @tailwindcss/postcss, and there
     may be NO tailwind.config.ts). Accept this — do not force a v3 layout.

3.3  De-duplicate the lockfile for the monorepo:
       - Delete apps/web/pnpm-lock.yaml if create-next-app made one.
       - From repo ROOT run:  pnpm install
       - Confirm a SINGLE pnpm-lock.yaml exists at the ROOT (commit it).

3.4  Replace app/page.tsx with a minimal placeholder ("Flowly — coming soon").
     Keep deps minimal (Next + React + Tailwind). TanStack Query / Recharts are
     later phases — do not add them now.

3.5  Confirm TypeScript strict mode is on in apps/web/tsconfig.json
       "strict": true


===============================================================================
STEP 4 — TRACKER  apps/tracker  (real stub, no build yet)
===============================================================================
4.1  apps/tracker/package.json
       { "name": "tracker", "private": true, "version": "0.0.0" }   # zero deps

4.2  apps/tracker/src/script.js  — no-op placeholder, wrapped, never throws
     -------------------------------------------------------------------------
     // Flowly tracker — placeholder (real logic lands in Phase 2).
     (function () {
       try {
         // no-op for now
       } catch (_) { /* fail silently, never break the host page */ }
     })();
     -------------------------------------------------------------------------
     No build wired in Phase 0.


===============================================================================
STEP 5 — CI  .github/workflows/ci.yml
===============================================================================
On push + pull_request. Two jobs (or two steps). Use FROZEN installs so CI fails
on stale lockfiles — that is what proves reproducibility off a clean machine.

  Python job:
    - actions/checkout
    - astral-sh/setup-uv  (with python-version 3.12)
    - working-directory apps/api:
        uv sync --frozen              # fails if uv.lock is out of date
        uv run ruff check .
        uv run ruff format --check .
        uv run pytest

  JS job:
    - actions/checkout
    - actions/setup-node  with node-version-file: .nvmrc   (-> Node 24)
    - corepack enable
    - pnpm install --frozen-lockfile  # fails if pnpm-lock.yaml is out of date
    - pnpm --filter web build

  (Caching — uv cache + pnpm store — is optional at Phase 0 but cheap to add.)
  (gh CLI is NOT needed in CI; it is only used locally in Step 6.)


===============================================================================
STEP 6 — GIT + FIRST PUSH  (hygiene gate before committing)
===============================================================================
6.1  git init
6.2  git add -A
6.3  git status  — VERIFY none of these are staged:
        .env  .venv/  node_modules/  dist/  .next/
     If any appear, STOP and fix .gitignore before committing (AC-P0-8).
6.4  git commit -m "Phase 0: monorepo scaffold, /health, CI"
6.5  Create the remote (private) and push:
        gh repo create flowly --private --source=. --remote=origin --push
     Fallback if gh is unavailable/unauthenticated:
        - Create an EMPTY private repo named "flowly" in the GitHub UI.
        - git remote add origin git@github.com:<you>/flowly.git
        - git branch -M main
        - git push -u origin main


===============================================================================
VERIFICATION  (maps to acceptance criteria)
===============================================================================
Backend (from apps/api):
  uv sync                                # AC-1: installs, writes uv.lock
  uv run uvicorn app.main:app --reload   # AC-3: /health = 200 with NO db running
  curl localhost:8000/health             #       -> {"status":"ok","environment":"local","version":"0.1.0"} (AC-7)
  uv run pytest                          # AC-5: test_health green
  uv run ruff check .                    # AC-6: zero errors
  uv run ruff format --check .           # AC-6: no changes

Frontend (from repo root):
  corepack enable
  pnpm install                           # AC-1: writes single root pnpm-lock.yaml
  pnpm --filter web dev                  # AC-4: placeholder page at :3000, no errors
  pnpm --filter web build                # build succeeds

Repo hygiene / reproducibility:
  git status                             # AC-8: no .env/.venv/node_modules/dist staged
  AC-2:   root scaffold + apps/{web,api,tracker} all present
  AC-9/10: fresh clone -> follow README only -> uv sync + pnpm install +
           run both apps + pass test/lint, no undocumented steps
  CI:     Actions re-runs lint+test+build on push (frozen installs) off a clean machine


DEFINITION OF DONE  (CLAUDE.md §10)
-------------------------------------------------------------------------------
[ ] Style + chosen libraries respected (FastAPI factory, pydantic-settings, uv,
    Ruff, pytest, Next App Router + strict TS, pnpm).
[ ] Lint clean + tests green locally AND in CI.
[ ] Every scaffolded env var is in .env.example; no library added outside CLAUDE.md §5.
[ ] .nvmrc, engines, .npmrc engine-strict, and packageManager all pin the same lines.
[ ] .env is git-ignored; no secret committed; git history is clean.
[ ] CLAUDE.md written to repo root; README reproduces AC-1..AC-6 with no gaps.
[ ] Phase 0 checklist boxes ticked in CLAUDE.md.
===============================================================================
