# Phase 0 — remaining steps

The scaffold is complete and committed **except** two steps that need tools not present
when it was built. Do these when ready, then delete this file.

## Prerequisites to install
- **Node 24** — this repo pins Node 24 (`.nvmrc`, `engines`) with `engine-strict=true`,
  so pnpm refuses to run on the current Node 20 (EOL). Install via nvm/fnm/installer.
- **GitHub CLI (`gh`)** — for creating + pushing the repo (or use the manual UI fallback).

## 1. Frontend `apps/web` (needs Node 24)
```bash
nvm install && nvm use                         # reads .nvmrc -> 24.15.0
node -v                                         # confirm v24.x
corepack enable && corepack use pnpm@latest     # pins exact pnpm in root packageManager

cd apps
pnpm create next-app@latest web --ts --app --tailwind --eslint --import-alias "@/*" --use-pnpm
# create-next-app installs Tailwind v4 (CSS-first). Accept it; do NOT hand-roll a v3 config.

# de-duplicate the lockfile to the workspace root:
rm -f web/pnpm-lock.yaml
cd ..
pnpm install                                    # writes the single root pnpm-lock.yaml
```
Then:
- Replace `apps/web/app/page.tsx` with a minimal placeholder ("Flowly — coming soon").
- Confirm `"strict": true` in `apps/web/tsconfig.json`.
- Verify: `pnpm --filter web dev` (placeholder at :3000) and `pnpm --filter web build`.
- Commit `apps/web/**` + the root `pnpm-lock.yaml`.

## 2. First push to GitHub (needs `gh`, or use fallback)
Do this **after** the frontend lands (otherwise CI's frontend job fails — no lockfile yet).
```bash
gh repo create flowly --private --source=. --remote=origin --push
```
Fallback without `gh`:
```bash
# create an empty PRIVATE repo named "flowly" in the GitHub UI, then:
git remote add origin git@github.com:<you>/flowly.git
git push -u origin main
```

## Acceptance check once both are done
- `uv run pytest` + `uv run ruff check .` green (backend) — already passing.
- `pnpm --filter web dev` serves :3000; `pnpm --filter web build` succeeds.
- CI (both jobs) green on push with frozen installs.
- Tick the remaining Phase 0 boxes in `CLAUDE.md`.
