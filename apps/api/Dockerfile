# syntax=docker/dockerfile:1

# Flowly API image. Build context is the REPO ROOT (needs apps/api + apps/tracker):
#   docker build -f apps/api/Dockerfile -t flowly-api .
#
# The SAME image runs the web API and every background worker — only the start
# command differs (see render.yaml / DEPLOY.md). uvicorn is the default CMD;
# workers override it with `python -m app.workers.<name>`.

# --- Stage 1: build the vanilla-JS tracker -------------------------------
# The API serves GET /script.js from apps/tracker/dist/script.js
# (routers/collect.py), so the minified artifact must exist in the image even
# though the API is Python. Built here so nothing depends on a committed dist.
FROM node:24-alpine AS tracker
WORKDIR /tracker
COPY apps/tracker/package.json ./
RUN npm install --no-audit --no-fund
COPY apps/tracker/ ./
RUN npm run build   # -> /tracker/dist/script.js

# --- Stage 2: the FastAPI app + workers ----------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS api

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/apps/api/.venv

WORKDIR /app/apps/api

# Dependencies first (cached until the lockfile changes). This is a non-package
# project (no [build-system]), so `uv sync` installs deps and the app runs from
# the working tree — no wheel build, no app code needed at this step.
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/.python-version ./
RUN uv sync --frozen --no-dev

# App code.
COPY apps/api/ ./

# Tracker artifact at the exact path collect.py resolves (<repo-root>/apps/tracker/dist).
# config.py and collect.py compute paths relative to the source file, so the
# monorepo layout (apps/api, apps/tracker) must be preserved under /app.
COPY --from=tracker /tracker/dist/script.js /app/apps/tracker/dist/script.js

# Put the venv on PATH so `uvicorn` / `alembic` / `python` are the project's.
ENV PATH="/app/apps/api/.venv/bin:$PATH"

# Render/Railway inject $PORT; default to 8000 for a plain `docker run`.
ENV PORT=8000
EXPOSE 8000

# Shell form so $PORT expands. Single worker: scale horizontally via the platform.
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
