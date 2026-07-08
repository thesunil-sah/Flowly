# syntax=docker/dockerfile:1

# Flowly web (Next.js) image. Build context is the REPO ROOT (pnpm workspace):
#   docker build -f apps/web/Dockerfile \
#     --build-arg NEXT_PUBLIC_API_URL=https://api.example.com -t flowly-web .
#
# NEXT_PUBLIC_* are inlined into the browser bundle at BUILD time, so they are
# build args here — NOT runtime env. Rebuild to change them.

FROM node:24-alpine AS base
ENV PNPM_HOME=/pnpm PATH="/pnpm:$PATH" NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

# --- deps: install the workspace (frozen) --------------------------------
FROM base AS deps
WORKDIR /repo
# Root manifest + lockfile + every workspace package.json the lockfile references
# (pnpm needs them all present to resolve a frozen install).
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/
COPY apps/tracker/package.json ./apps/tracker/
RUN pnpm install --frozen-lockfile --filter web...

# --- build: compile the standalone server --------------------------------
FROM base AS build
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/web ./apps/web
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_DEMO_SHARE_TOKEN
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_DEMO_SHARE_TOKEN=$NEXT_PUBLIC_DEMO_SHARE_TOKEN
RUN pnpm --filter web build

# --- run: minimal runtime with the traced server -------------------------
FROM base AS run
WORKDIR /repo
ENV NODE_ENV=production PORT=3000
# Standalone output carries its own pruned node_modules + server.js. With
# outputFileTracingRoot=repo root, the server entrypoint is apps/web/server.js.
COPY --from=build /repo/apps/web/.next/standalone ./
COPY --from=build /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build /repo/apps/web/public ./apps/web/public
EXPOSE 3000
# Next's standalone server binds $PORT (Render/Railway inject it).
CMD ["node", "apps/web/server.js"]
