# Phase 2 — Tracking Script (core) ✅ COMPLETE

**Goal:** a tiny script that, dropped on any page, fires a pageview to the API.
**Outcome:** a vanilla-JS, zero-runtime-dependency tracker that sends a pageview to
`/collect` via `navigator.sendBeacon` on first load and on SPA navigations. Built +
minified to `dist/script.js` at **~1.0 KB** (budget < 2 KB). Never throws and never breaks
the host page. All Phase 2 checklist items done.
**Date:** 2026-07-02
**Branch:** `phase-1-auth` (commit `368b995`) → merged to `main` via PR #2 (`75d0c6f`)

> Scope note: `/collect` itself is Phase 3, so this phase delivers only the **client half**.
> Verification confirms the beacon *fires* with the correct URL + payload; the server-side
> receipt/validation/storage lands in Phase 3.

---

## Tools & versions used
| Tool | Version | For |
|---|---|---|
| esbuild | 0.24.2 | minify/bundle `src/script.js` → `dist/script.js` (devDependency only) |
| pnpm (workspaces) | 11.9 | `--filter tracker build`; `allowBuilds: esbuild` for its native binary |
| Node | 24.18 | build runtime |
| Node `vm` harness | — | headless behavioral verification of the built script |

The **shipped script has zero runtime dependencies** — esbuild is build-time tooling only.

---

## What we built (by area)

### Tracking script (`apps/tracker`)
1. **`src/script.js`** — rewrote the Phase-0 no-op stub into the real tracker. A single
   IIFE, everything wrapped in `try/catch`, fails silently:
   - **Script element captured once** (`document.currentScript` + `script[data-site]`
     fallback) — `currentScript` is `null` inside later SPA callbacks, so all attributes
     are read up front.
   - **`data-site`** → `site_id`; bail silently if absent.
   - **Endpoint discovery:** `data-api` override, else the script's own `<script src>`
     origin → `{origin}/collect`.
   - **Transport:** `navigator.sendBeacon` with a **`text/plain` Blob** (keeps it a
     CORS-safelisted "simple request" → no preflight), with a
     `fetch(..., {keepalive:true, mode:'no-cors'})` fallback.
   - **`track()`** builds the payload and **dedupes by `path`** (repeated same-path
     navigations don't double-count).
   - **SPA support:** monkeypatches `history.pushState` + `replaceState` (each wrapped so a
     host error can't surface), plus a `popstate` listener. Fires once on initial load.
2. **Build tooling** — `package.json` gains a `build` script (esbuild `--minify
   --format=iife`) and `esbuild` devDependency; root `package.json` gains `build:tracker`;
   `pnpm-workspace.yaml` allows esbuild's install script.
3. **`test/index.html`** — dev-only manual harness: SPA `pushState` buttons, a same-path
   button (proves dedupe), a `popstate` link, a UTM link, and a second script tag with a
   missing `data-site` (proves the silent no-op).

### The wire contract (locked — Phase 3 inherits it verbatim)
The exact JSON body POSTed to `{base}/collect`:
| field | source | notes |
|---|---|---|
| `site_id` | `data-site` | tags every event |
| `path` | `location.pathname` | **no query string** (privacy) |
| `referrer` | `document.referrer` | raw; same-site stripping is a Phase 3 concern |
| `screen_w` | `screen.width` | maps to the `events.screen_w` column |
| `utm_source` / `utm_medium` / `utm_campaign` | `location.search` | extracted client-side, `null` when absent |

> **`language` intentionally dropped:** the CLAUDE.md checklist listed it, but the ClickHouse
> `events` table has no column to store it — so the script does not send it. (Reconciled in
> the CLAUDE.md checklist.)

### Docs
- **README.md** — updated the tracker row; added a build + install-snippet section.
- **CLAUDE.md** — ticked all Phase 2 boxes (payload line updated to drop `language`),
  refreshed the "Last updated" footer.
- **`.claude/plan/phase-02-implementation-plan.md`** — the reviewed implementation plan.

---

## Features completed (Phase 2 checklist)
- [x] Read `data-site` (site_id) from the script tag
- [x] Send pageview via `navigator.sendBeacon` to `/collect`
- [x] Payload: site_id, path, referrer, screen width, UTM (language dropped — no column)
- [x] SPA support: wrap `history.pushState`/`replaceState` + listen for `popstate`
- [x] Wrap everything in try/catch; fail silently; never break the host page
- [x] Build + minify → `apps/tracker/dist/script.js` (~1.0 KB, < 2 KB) via esbuild
- [x] Manual test harness (`test/index.html`) + headless verification

---

## Verified
- **Build:** `pnpm --filter tracker build` → `dist/script.js` = **1072 bytes (~1.0 KB)**.
- **Behavioral (headless `vm` harness against the built script) — 22/22 checks:**
  - initial pageview fires; endpoint from `data-api` override **and** from script origin;
  - payload has exactly `site_id, path, referrer, screen_w, utm_source/medium/campaign`
    (no `language`); `text/plain` content-type;
  - `pushState` → new beacon; same-path `pushState` → **deduped** (no beacon);
  - UTM captured from query while `path` stays query-free; `popstate` fires;
  - **missing `data-site` → silent no-op** (no beacon, no fetch);
  - **`sendBeacon` throwing → `fetch` fallback** (keepalive + no-cors).
- **No regressions:** `uv run pytest` → 30 passed; `pnpm --filter web lint` clean.

---

## Decisions (as built; flippable)
- **Endpoint:** origin-derived with optional `data-api` override (zero-config install).
- **No preflight:** `text/plain` Blob body; Phase 3's `/collect` reads the raw body as JSON.
- **Dedupe key:** `pathname` only — a query-only SPA navigation isn't counted as a new view.
- **`replaceState` tracked** like `pushState` (the pathname dedupe absorbs the common
  same-path case, keeping over-count risk low).
- **`dist/` stays gitignored** — the minified file is a build artifact, not committed source.
- **Referrer sent raw** — same-site filtering + `source` derivation deferred to Phase 3.

## Open / follow-ups
- Serving `/script.js` from the API host or a CDN, and `TRACKER_SCRIPT_URL` wiring → later
  (the script is only built to `dist/` for now).
- `utm_content` / `utm_term` — add only if wanted (needs matching Phase 3 columns).
- Real end-to-end (beacon → stored event) becomes testable once **Phase 3** ships `/collect`.

---

## Key commands
```bash
# build the tracker (repo root or apps/tracker)
pnpm --filter tracker build        # -> apps/tracker/dist/script.js  (~1.0 KB)
pnpm build:tracker                 # same, from root

# manual test: build, then open apps/tracker/test/index.html and watch
# DevTools > Network for the POST to /collect (no OPTIONS preflight).
```

### Install snippet (for customers)
```html
<script defer src="https://your-host/script.js" data-site="YOUR_SITE_ID"></script>
```
