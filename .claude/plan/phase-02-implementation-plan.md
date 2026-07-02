# FLOWLY — PHASE 2 IMPLEMENTATION PLAN

## Tracking script (core)

Planning-only deliverable — **no code is written in this task.** Suggested save location:
`.claude/plan/phase-02-implementation-plan.md` (or wherever you keep phase plans).

---

## Changes from the reviewed draft (what this revision fixes)

1. **`referrer` semantics corrected.** The draft claimed `document.referrer` is "the previous in-app URL for SPA transitions" — it isn't; it's the external referrer and stays frozen for the whole SPA session. The field is kept but described accurately, and same-site filtering is assigned to Phase 3. (D3)
2. **UTM contract resolved.** The draft stripped the query string client-side (good for privacy) but then expected Phase 3 to derive `utm_*` server-side — which is impossible once the query is gone. The script now **extracts the UTM params explicitly** and sends them as fields, keeping `path` query-free. (D4)
3. **No-preflight assertion added to verification.** Decision "send a `text/plain` Blob to avoid a preflight" is now actually verified (Network tab shows the POST with **no preceding OPTIONS**). (V2)
4. **Wire contract locked** — an explicit final field list (below) that Phase 3's Pydantic model and `routers/collect.py` adopt verbatim.
5. **Minor:** the script element is captured **once** at IIFE top (never re-queried inside `track()`); `--bundle` noted as a harmless no-op on a zero-import file.

---

## Context

Flowly's product is the tracking script + `/collect` endpoint; everything else reads from the data
they produce (CLAUDE.md §1). Phase 1 (database + auth) is complete and merged. Phase 2 delivers the
**client half**: a tiny vanilla-JS script a customer drops on their site that fires a pageview.

Today `apps/tracker/` is only a stub — a bare `package.json` (no scripts/deps) and a no-op
`src/script.js`. There's no minifier in the repo, no `dist/` output, and `dist/` is gitignored. The
`/collect` endpoint does not exist yet (Phase 3), so this phase's realistic verification is
confirming the beacon **fires with the correct URL and payload in browser devtools** — not a server
round-trip.

**Goal (CLAUDE.md Phase 2):** "a tiny script that, dropped on a page, fires a pageview to the API."
**Constraints:** zero runtime dependencies, **< 2 KB minified**, must never throw and never break the
host page.

---

## Decisions (chosen defaults — override any; see Open items)

- **D1 — Endpoint discovery.** Derive from the script's own `<script src>` origin → `{origin}/collect`, with an optional `data-api` attribute override. Zero-config, and matches serving the script from the API host (`TRACKER_SCRIPT_URL=http://localhost:8000/script.js`).
- **D2 — Scope: tracker-only.** Build `dist/script.js` + a local test page. **Do not touch `apps/api`** this phase (no `/script.js` serving route, no `/collect` — both are later). This keeps the phase single-theme.
- **D3 — `referrer` field.** Send `document.referrer` **as-is** (raw). It is the *external* referrer of the session, not the previous in-app URL, and it does not change on SPA navigations. On classic multi-page sites it can be **same-site**; **Phase 3 strips same-site referrers** so only external referrers drive `source`/`channel`. Previous-in-app-page tracking (for user-flow) is a deferred premium feature (Phase 10) and is intentionally **not** built now.
- **D4 — UTM handling (privacy-first).** `path` is `location.pathname` with **no query string** (query may carry PII). The UTM campaign params are extracted **explicitly** from `location.search` and sent as their own fields (`utm_source`, `utm_medium`, `utm_campaign`), each `null` when absent. This gives campaign attribution without shipping the raw query. Phase 3 stores them directly — no server-side query parsing.
- **D5 — Minifier.** `esbuild` as a **devDependency** (minifies in one step). Shipped script keeps zero runtime deps. `--bundle` is harmless here (no imports to bundle); `--minify` does the work.
- **D6 — Transport content-type.** Send the JSON body inside a `text/plain` Blob so the beacon stays a CORS-safelisted **simple request** (no preflight). Phase 3's `/collect` reads the raw body and parses JSON regardless of content-type.
- **D7 — `dist/` stays gitignored** — the minified file is a build artifact from `pnpm --filter tracker build` (and later a CDN/deploy step), not committed source.

---

## The wire contract (LOCKED — Phase 3 inherits this verbatim)

Exact JSON body the script POSTs to `{base}/collect`. Field names are frozen; Phase 3's Pydantic
model and `routers/collect.py` adopt them directly.

```
{
  "site_id":      string,          // from data-site; tags every event
  "path":         string,          // location.pathname — NO query string
  "referrer":     string,          // document.referrer (raw; may be same-site — Phase 3 filters)
  "screen_w":     number,          // window.screen.width
  "utm_source":   string | null,   // from ?utm_source=  (null if absent)
  "utm_medium":   string | null,   // from ?utm_medium=
  "utm_campaign": string | null    // from ?utm_campaign=
}
```

**Server-derived in Phase 3 (NOT sent by the script):** `visitor_hash`, `country`, `region`,
`device`, `browser`, `os`, `source`, `ts`. (`source` is derived from `referrer`; `utm_*` come from
the client above.)

> **`language` intentionally dropped.** CLAUDE.md's Phase 2 checklist lists a `language` field, but
> the `events` table has **no column to store it** — so the script does not send it. When ticking
> the Phase 2 boxes, also update that checklist line in CLAUDE.md to drop `language` (or add the
> column in Phase 3 first if it's ever wanted).

Maps cleanly onto the CLAUDE.md `events` columns: `site_id, ts, path, referrer, source, utm_source,
utm_medium, utm_campaign, country, region, device, browser, os, visitor_hash, screen_w`.

---

## Files to create / modify

### `apps/tracker/src/script.js` (rewrite the stub — the real logic)
- Single **IIFE**, everything wrapped in `try/catch`, fails silently.
- **Capture the script element once at the top:** `document.currentScript` with a fallback to `document.querySelector('script[data-site]')` (covers async/defer). Read `data-site` and `data-api` from it now — never re-query inside `track()` (`currentScript` is `null` inside later callbacks).
- If `site_id` is absent → **bail silently** (no site → do nothing).
- **Endpoint:** `data-api` override if present, else `new URL(scriptEl.src).origin`; POST target = `${base}/collect`.
- **UTM extraction:** parse `location.search` once via `URLSearchParams`; pull `utm_source`, `utm_medium`, `utm_campaign` (null when absent). Recompute per `track()` call so SPA navigations to campaign URLs are captured.
- **`send(payload)`:** prefer `navigator.sendBeacon(url, new Blob([JSON.stringify(payload)], {type:'text/plain'}))`; fall back to `fetch(url, {method:'POST', body, keepalive:true, mode:'no-cors'})` when `sendBeacon` is unavailable or returns `false`.
- **`track()`** builds the pageview payload (the wire contract above) and sends it. **Dedupe** by remembering the last-sent `path` so repeated `pushState` to the same URL doesn't double-count.
- Fire **once on initial load**.
- **SPA support:** monkeypatch `history.pushState` and `replaceState` (call the original, then `track()`); add a `popstate` listener that calls `track()`. Each patched function is itself wrapped so a host-page error can't surface through it.

### `apps/tracker/package.json` (add build tooling)
- `"scripts": { "build": "esbuild src/script.js --bundle --minify --format=iife --outfile=dist/script.js" }` (an optional `"size"` check may be added).
- `"devDependencies": { "esbuild": "^0.x" }` via `pnpm add -D esbuild --filter tracker`.
- Keep `"private": true`; **no runtime dependencies.**

### Root `package.json` (wire the tracker into top-level scripts)
- Add `"build:tracker": "pnpm --filter tracker build"` (mirrors the web entries).

### `apps/tracker/test/index.html` (new — manual test harness, dev-only)
- Loads `../dist/script.js` with `data-site="test-site"` (and, if testing cross-host, a `data-api`).
- Buttons calling `history.pushState` to different paths, a same-path button (to prove dedupe), a link that exercises `popstate`, and a link carrying `?utm_source=…&utm_medium=…&utm_campaign=…` (to prove UTM capture).

### Docs
- **README.md:** replace the "Vanilla JS (stub in Phase 0)" note; document `pnpm --filter tracker build` and the install snippet.
- **CLAUDE.md:** tick the Phase 2 checklist boxes as completed; refresh the "Last updated" footer.

---

## Reuse / references
- The existing stub already establishes the "wrap everything, fail silently" IIFE shape — extend that contract, don't fight it.
- `pnpm-workspace.yaml` already globs `apps/*`, so `--filter tracker` works with no workspace change; only a build script is missing.
- The wire contract above is the input to Phase 3's `models/` event schema and `routers/collect.py` — keep field names stable.

---

## Verification (end-to-end for this phase)

- **V1 — Build.** `pnpm add -D esbuild --filter tracker`, then `pnpm --filter tracker build` → produces `apps/tracker/dist/script.js`. Confirm it exists and is **< 2 KB** (check the byte size).
- **V2 — Payload + no preflight.** Serve the test page (any static server, or open `test/index.html`), DevTools → Network:
  - On load, a **POST** to `…/collect` appears (shown as failed/pending since `/collect` doesn't exist yet — expected in Phase 2).
  - **Confirm there is NO preceding `OPTIONS` request** — this proves the `text/plain` Blob kept it a simple request (D6).
  - Inspect the request payload: correct `site_id`, `path` (no query string), `referrer`, `screen_w`, and `utm_*` (null when the URL has none).
- **V3 — SPA + dedupe + UTM.** Click the pushState buttons / back-forward → each navigation fires **exactly one** new beacon; the same-path button does **not** double-fire; the UTM link sends populated `utm_*`.
- **V4 — Never-break-host.** Load with a missing `data-site`, and with `sendBeacon` stubbed to throw → the page still runs, **no uncaught errors** in the console.
- **V5 — No regressions.** `pnpm --filter web lint` and existing suites remain green.
- *(Optional)* run a throwaway local POST listener that logs the body, to confirm the exact JSON before `/collect` exists.

---

## Definition of done (CLAUDE.md §10)

- [ ] `src/script.js` implements: read `data-site`, resolve endpoint, `sendBeacon` to `/collect`, the **locked payload** (site_id / path / referrer / screen_w / utm_source / utm_medium / utm_campaign), SPA `pushState`+`replaceState`+`popstate`, same-path dedupe, try/catch fail-safe.
- [ ] `path` carries **no query string**; `utm_*` are sent as explicit fields; `referrer` is raw `document.referrer` (same-site filtering deferred to Phase 3). *(fix)*
- [ ] `dist/script.js` builds and is **< 2 KB** minified.
- [ ] Zero runtime deps; `esbuild` added only as a devDependency (note in the same change if §5 needs it).
- [ ] Manual test confirms the beacon fires with the right payload **and no OPTIONS preflight**. *(fix)*
- [ ] Never-break-host verified (missing `data-site`; `sendBeacon` throwing).
- [ ] README + CLAUDE.md updated, Phase 2 boxes ticked, footer date refreshed.

---

## Out of scope (later phases)
- `POST /collect`, payload validation, bot filtering, visitor hashing, rate limiting, Redis stream + batch writer, ClickHouse `events` table → **Phase 3**.
- `source` derivation from `referrer` + same-site referrer filtering → **Phase 3**.
- Previous-in-app-page / user-flow tracking → **Phase 10 (premium)**.
- Serving `/script.js` from the API and CDN deploy → later (script is built to `dist/` now).

---

## Open items (my defaults are in use; flip any and I'll adjust)
- **O1 — UTM breadth (D4).** Default sends `utm_source/medium/campaign` (matches the `events` columns). Add `utm_content`/`utm_term` only if you want them — requires adding the columns in Phase 3.
- **O2 — Endpoint override (D1).** Default: origin-derived with optional `data-api`. Alternative: require `data-api` explicitly (more config, fewer surprises if the script is ever self-hosted).
- **O3 — `replaceState` handling (script logic).** Default: treat `replaceState` like `pushState` and track it. Flip if you'd rather ignore `replaceState` (some apps use it for non-navigational URL tweaks, which would over-count).