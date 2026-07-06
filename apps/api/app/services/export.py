"""CSV export of aggregated reports (§9, Phase 9).

Exports the same **aggregated** reports the dashboard shows — never raw events —
so nothing per-visitor (not even the anonymous `visitor_hash`) ever leaves in a
file, keeping the privacy promise intact (§9). Each dataset reuses a Phase 5
stats service, then serializes to CSV; reports are top-N (bounded), so building
in memory is fine.
"""

import csv
import io
from datetime import datetime

from clickhouse_connect.driver import AsyncClient

from app.core.exceptions import ValidationError
from app.services import stats

# Exportable report datasets. Kept as an allowlist so an unknown value is a clean
# 422, never an attempt to build arbitrary output.
DATASETS = (
    "overview",
    "timeseries",
    "sources",
    "audience",
    "pages",
    "channels",
    "screens",
    "heatmap",
)


def _csv(header: list[str], rows: list[list[object]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


# All exports carry the dashboard filters so a downloaded report matches what's
# on screen (Phase 10). `filters` flows straight to the stats services, which
# bind values as server-side params (§9).
async def _overview_csv(
    client: AsyncClient, site_id: str, f: datetime, t: datetime, filters: dict[str, str]
) -> str:
    ov = await stats.overview(client, site_id, f, t, True, filters)
    header = ["metric", "value", "previous", "change_pct"]
    rows: list[list[object]] = [
        [
            name,
            m.value,
            m.previous if m.previous is not None else "",
            m.change_pct if m.change_pct is not None else "",
        ]
        for name, m in (
            ("pageviews", ov.pageviews),
            ("visitors", ov.visitors),
            ("sessions", ov.sessions),
            ("bounce_rate", ov.bounce_rate),
            ("avg_duration", ov.avg_duration),
        )
    ]
    return _csv(header, rows)


async def _timeseries_csv(
    client: AsyncClient, site_id: str, f: datetime, t: datetime, filters: dict[str, str]
) -> str:
    ts = await stats.timeseries(client, site_id, f, t, filters)
    rows = [[p.bucket.isoformat(), p.pageviews, p.visitors] for p in ts.points]
    return _csv(["bucket", "pageviews", "visitors"], rows)


async def _sources_csv(
    client: AsyncClient, site_id: str, f: datetime, t: datetime, limit: int, filters: dict[str, str]
) -> str:
    src = await stats.sources(client, site_id, f, t, limit, filters)
    rows = [[r.label, r.pageviews, r.visitors] for r in src.sources]
    return _csv(["source", "pageviews", "visitors"], rows)


async def _audience_csv(
    client: AsyncClient,
    site_id: str,
    f: datetime,
    t: datetime,
    dimension: str,
    limit: int,
    filters: dict[str, str],
) -> str:
    br = await stats.audience(client, site_id, f, t, dimension, limit, filters)
    rows = [[r.label, r.pageviews, r.visitors] for r in br.rows]
    return _csv([dimension, "pageviews", "visitors"], rows)


async def _pages_csv(
    client: AsyncClient,
    site_id: str,
    f: datetime,
    t: datetime,
    kind: str,
    limit: int,
    filters: dict[str, str],
) -> str:
    pg = await stats.pages(client, site_id, f, t, kind, limit, filters)
    rows = [[r.label, r.count, r.visitors] for r in pg.rows]
    return _csv(["path", pg.metric, "visitors"], rows)


async def _channels_csv(
    client: AsyncClient, site_id: str, f: datetime, t: datetime, filters: dict[str, str]
) -> str:
    ch = await stats.channels(client, site_id, f, t, filters)
    rows = [[r.channel, r.pageviews, r.visitors] for r in ch.channels]
    return _csv(["channel", "pageviews", "visitors"], rows)


async def _heatmap_csv(
    client: AsyncClient, site_id: str, f: datetime, t: datetime, tz: str, filters: dict[str, str]
) -> str:
    hm = await stats.heatmap(client, site_id, f, t, tz, filters)
    rows = [[c.dow, c.hour, c.pageviews, c.visitors] for c in hm.cells]
    return _csv(["dow", "hour", "pageviews", "visitors"], rows)


async def build_csv(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    dataset: str,
    dimension: str = "country",
    kind: str = "top",
    limit: int = 100,
    filters: dict[str, str] | None = None,
    tz: str = "UTC",
) -> tuple[str, str]:
    """Build one report's CSV. Returns (filename, content).

    `dataset` selects the report; `dimension` (audience) and `kind` (pages) refine
    it; `filters` slices every dataset. An unknown dataset is a 422 (validated at
    the boundary too).
    """
    if dataset not in DATASETS:
        raise ValidationError(f"Unknown dataset: {dataset}")
    filters = filters or {}
    if dataset == "overview":
        content = await _overview_csv(client, site_id, from_, to, filters)
        name = "overview"
    elif dataset == "timeseries":
        content = await _timeseries_csv(client, site_id, from_, to, filters)
        name = "timeseries"
    elif dataset == "sources":
        content = await _sources_csv(client, site_id, from_, to, limit, filters)
        name = "sources"
    elif dataset == "channels":
        content = await _channels_csv(client, site_id, from_, to, filters)
        name = "channels"
    elif dataset == "heatmap":
        content = await _heatmap_csv(client, site_id, from_, to, tz, filters)
        name = "heatmap"
    elif dataset == "screens":
        content = await _audience_csv(client, site_id, from_, to, "screen", limit, filters)
        name = "screens"
    elif dataset == "audience":
        content = await _audience_csv(client, site_id, from_, to, dimension, limit, filters)
        name = f"audience-{dimension}"
    else:  # pages
        content = await _pages_csv(client, site_id, from_, to, kind, limit, filters)
        name = f"pages-{kind}"
    filename = f"flowly-{name}-{from_:%Y%m%d}-{to:%Y%m%d}.csv"
    return filename, content
