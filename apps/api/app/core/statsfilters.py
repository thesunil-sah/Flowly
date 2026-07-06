"""Shared dashboard-filter parsing for stats-serving routes (Phase 10, §3).

The authed dashboard (`routers/stats.py`) and the public shareable dashboard
(`routers/public.py`) accept the same optional slice-by-dimension filters, so the
dependency lives here rather than being duplicated (mirrors `core/timerange.py`,
which shares the `[from, to)` window between both routers).

Each filter is an exact-match on one allowlisted `events` column. The value is
carried through to `services/stats.py`, which binds it as a **server-side param**
— never string-formatted into SQL (§9). An empty/absent filter is simply dropped.
"""

from typing import Annotated

from fastapi import Depends, Query


def stats_filters(
    country: Annotated[str | None, Query()] = None,
    device: Annotated[str | None, Query()] = None,
    browser: Annotated[str | None, Query()] = None,
    os: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    path: Annotated[str | None, Query()] = None,
) -> dict[str, str]:
    """Collect the active dashboard filters into a `{column: value}` dict.

    Only non-empty values are included; the keys are a fixed allowlist mirrored by
    `services/stats.py::_FILTER_COLUMNS` (which rejects anything else). Multiple
    filters stack (AND) — e.g. `?country=US&device=mobile`.
    """
    candidates = {
        "country": country,
        "device": device,
        "browser": browser,
        "os": os,
        "source": source,
        "path": path,
    }
    return {key: value for key, value in candidates.items() if value}


FilterDep = Annotated[dict[str, str], Depends(stats_filters)]
