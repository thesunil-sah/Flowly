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
DATASETS = ("overview", "timeseries", "sources", "audience", "pages")


def _csv(header: list[str], rows: list[list[object]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


async def _overview_csv(client: AsyncClient, site_id: str, f: datetime, t: datetime) -> str:
    ov = await stats.overview(client, site_id, f, t, True)
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


async def _timeseries_csv(client: AsyncClient, site_id: str, f: datetime, t: datetime) -> str:
    ts = await stats.timeseries(client, site_id, f, t)
    rows = [[p.bucket.isoformat(), p.pageviews, p.visitors] for p in ts.points]
    return _csv(["bucket", "pageviews", "visitors"], rows)


async def _sources_csv(
    client: AsyncClient, site_id: str, f: datetime, t: datetime, limit: int
) -> str:
    src = await stats.sources(client, site_id, f, t, limit)
    rows = [[r.label, r.pageviews, r.visitors] for r in src.sources]
    return _csv(["source", "pageviews", "visitors"], rows)


async def _audience_csv(
    client: AsyncClient, site_id: str, f: datetime, t: datetime, dimension: str, limit: int
) -> str:
    br = await stats.audience(client, site_id, f, t, dimension, limit)
    rows = [[r.label, r.pageviews, r.visitors] for r in br.rows]
    return _csv([dimension, "pageviews", "visitors"], rows)


async def _pages_csv(
    client: AsyncClient, site_id: str, f: datetime, t: datetime, kind: str, limit: int
) -> str:
    pg = await stats.pages(client, site_id, f, t, kind, limit)
    rows = [[r.label, r.count, r.visitors] for r in pg.rows]
    return _csv(["path", pg.metric, "visitors"], rows)


async def build_csv(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    dataset: str,
    dimension: str = "country",
    kind: str = "top",
    limit: int = 100,
) -> tuple[str, str]:
    """Build one report's CSV. Returns (filename, content).

    `dataset` selects the report; `dimension` (audience) and `kind` (pages) refine
    it. An unknown dataset is a 422 (validated at the boundary too).
    """
    if dataset not in DATASETS:
        raise ValidationError(f"Unknown dataset: {dataset}")
    if dataset == "overview":
        content = await _overview_csv(client, site_id, from_, to)
        name = "overview"
    elif dataset == "timeseries":
        content = await _timeseries_csv(client, site_id, from_, to)
        name = "timeseries"
    elif dataset == "sources":
        content = await _sources_csv(client, site_id, from_, to, limit)
        name = "sources"
    elif dataset == "audience":
        content = await _audience_csv(client, site_id, from_, to, dimension, limit)
        name = f"audience-{dimension}"
    else:  # pages
        content = await _pages_csv(client, site_id, from_, to, kind, limit)
        name = f"pages-{kind}"
    filename = f"flowly-{name}-{from_:%Y%m%d}-{to:%Y%m%d}.csv"
    return filename, content
