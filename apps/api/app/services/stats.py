"""Historical dashboard metrics — ClickHouse query builders + shaping (§3).

Two layers live here, deliberately separated so the SQL is testable without a
running ClickHouse:

  - **Builders** (`build_*`) are pure: `(site_id, range, …) -> (sql, params)`.
    Every user-supplied value goes into `params` as a clickhouse-connect
    server-side parameter (`{site_id:String}`, `{from:DateTime}`); nothing is
    string-formatted into SQL, so there is no injection surface (§9). The only
    values interpolated into SQL text are internal allowlisted identifiers
    (column/function names) and the integer session-timeout constant.
  - **Service functions** run a builder via `db.clickhouse.query_rows`, then do
    the arithmetic/formatting that doesn't belong in SQL — bounce ratio,
    compare deltas, zero-filling gaps — and return Pydantic response models.

The central fact: the `events` table has **no session column**. Sessions,
bounce, and duration are derived at query time from `visitor_hash` + `ts` gaps
(a 30-minute timeout). `_SESSIONIZED_CTE` is that derivation, shared by every
session-aware query.

Reads only — never writes ClickHouse, never touches Redis (the live counter is
Phase 4's job). All timestamps are UTC end-to-end; display-time localization is
the frontend's concern (§4).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from clickhouse_connect.driver import AsyncClient

from app.core.exceptions import ValidationError
from app.db.clickhouse import query_rows
from app.models.schemas import (
    BreakdownOut,
    BreakdownRow,
    ChannelRow,
    ChannelsOut,
    HeatmapCell,
    HeatmapOut,
    MetricDelta,
    OverviewOut,
    PageRow,
    PagesOut,
    SourcesOut,
    TimeseriesOut,
    TimeseriesPoint,
    UtmRow,
)
from app.services import channels as channels_svc

# A visitor's events split into a new session after this idle gap (glossary §2).
SESSION_TIMEOUT_SECONDS = 1800

DEFAULT_LIMIT = 10
MAX_LIMIT = 100

# Audience dimension -> events column. The dict IS the allowlist: a value not a
# key here is rejected before any SQL is built, so the column name interpolated
# into SQL is always one of these fixed internal strings (never user text).
_AUDIENCE_COLUMNS: dict[str, str] = {
    "country": "country",
    "device": "device",
    "browser": "browser",
    "os": "os",
    "city": "city",
    "language": "language",
}
_PAGE_KINDS = ("top", "entry", "exit")

# Filterable dimensions (Phase 10 dashboard-wide filters). Same guard idiom as
# `_AUDIENCE_COLUMNS`: the dict IS the allowlist, so the only column name ever
# interpolated into SQL is one of these fixed internal strings — a filter *value*
# is always a server-side param, never string-formatted (§9).
_FILTER_COLUMNS: dict[str, str] = {
    "country": "country",
    "device": "device",
    "browser": "browser",
    "os": "os",
    "source": "source",
    "path": "path",
}

# Time-series bucket function, chosen from the range length (not user input).
_HOUR_FN = "toStartOfHour"
_DAY_FN = "toStartOfDay"

# Screen-width buckets (Phase 10 audience report). A `screen_w` of 0 means the
# tracker didn't report one. This is an internal constant expression (no user
# input) so it's safe to interpolate as the breakdown "column".
_SCREEN_BUCKET_SQL = (
    "multiIf("
    "screen_w = 0, 'Unknown', "
    "screen_w <= 640, 'Mobile', "
    "screen_w <= 1024, 'Tablet', "
    "screen_w <= 1440, 'Laptop', "
    "'Desktop')"
)

# Site + time-range predicate shared by every query. Braces are clickhouse-
# connect parameter placeholders — kept literal (no f-string) so they survive to
# the driver, which binds them server-side.
_BASE_WHERE = "site_id = {site_id:String} AND ts >= {from:DateTime} AND ts < {to:DateTime}"

# Per-visitor sessionization. `lagInFrame` gives each event its visitor's
# previous timestamp; a gap over the timeout (or the first event, whose lag
# defaults to 1970 -> a huge gap) starts a new session; a running sum of those
# starts numbers the sessions. The timeout is an int constant, baked as a
# literal (not a param) via replace so no f-string touches the {…} placeholders.
# `{base_where}` is substituted per call with the base predicate PLUS any active
# filter clause, so sessions/bounce/entry/exit honor the dashboard filters too.
_SESSIONIZED_TEMPLATE = """
WITH
_in_range AS (
    SELECT visitor_hash, path, ts,
        lagInFrame(ts) OVER w AS prev_ts
    FROM events
    WHERE {base_where}
    WINDOW w AS (
        PARTITION BY visitor_hash ORDER BY ts
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )
),
_flagged AS (
    SELECT visitor_hash, path, ts,
        dateDiff('second', prev_ts, ts) > __TIMEOUT__ AS is_start
    FROM _in_range
),
sessionized AS (
    SELECT visitor_hash, path, ts, is_start,
        sum(is_start) OVER (
            PARTITION BY visitor_hash ORDER BY ts
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS session_num
    FROM _flagged
)
""".replace("__TIMEOUT__", str(SESSION_TIMEOUT_SECONDS))


def _sessionized_cte(filter_sql: str = "") -> str:
    """The sessionization CTE with the base predicate + any filter clause baked
    into `_in_range`'s WHERE. `filter_sql` is a pre-built ` AND col = {p:String}`
    string from `_filter_clause` (params bound separately); empty when unfiltered.
    """
    return _SESSIONIZED_TEMPLATE.replace("{base_where}", _BASE_WHERE + filter_sql)


# --- Param helpers --------------------------------------------------------
def _aware_utc(dt: datetime) -> datetime:
    """Return a tz-aware UTC datetime, treating a naive value as already-UTC.

    clickhouse-connect returns `toStartOf*` buckets as **naive** datetimes that
    represent UTC (the column is DateTime('UTC')). `.astimezone(UTC)` on a naive
    value would wrongly assume system-local time and shift the instant — so
    attach UTC instead. (Getting this wrong makes every bucket lookup miss and
    the whole series read as zero.)
    """
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _range_params(site_id: str, from_: datetime, to: datetime) -> dict[str, Any]:
    # Bind tz-AWARE UTC datetimes. A naive datetime is rendered as a bare
    # string that ClickHouse parses in the *server* timezone, silently shifting
    # the window by the server's UTC offset (e.g. -1h on a BST server: the
    # newest hour of events vanishes from any "until now" query). An aware
    # value survives binding as the same instant regardless of server tz.
    return {"site_id": site_id, "from": _aware_utc(from_), "to": _aware_utc(to)}


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


def _filter_clause(filters: dict[str, str] | None) -> tuple[str, dict[str, Any]]:
    """Turn a filter dict into a ` AND col = {f_col:String}` SQL fragment + params.

    Each value is bound as a server-side param under a namespaced key (`f_country`
    …) so it can't collide with `site_id`/`from`/`to`/`limit`. The column name is
    looked up in the `_FILTER_COLUMNS` allowlist — an unknown key is a 422, never
    interpolated. Returns `("", {})` when there is nothing to filter.
    """
    if not filters:
        return "", {}
    parts: list[str] = []
    params: dict[str, Any] = {}
    for key, value in filters.items():
        column = _FILTER_COLUMNS.get(key)
        if column is None:
            raise ValidationError(f"Unknown filter: {key}")
        pkey = f"f_{key}"
        parts.append(f" AND {column} = {{{pkey}:String}}")
        params[pkey] = value
    return "".join(parts), params


# --- Builders (pure: return (sql, params)) --------------------------------
def build_overview(
    site_id: str, from_: datetime, to: datetime, filters: dict[str, str] | None = None
) -> tuple[str, dict[str, Any]]:
    """One row of raw counts for the metric cards (rates derived in Python)."""
    fsql, fparams = _filter_clause(filters)
    sql = (
        _sessionized_cte(fsql)
        + """,
    _per_session AS (
        SELECT visitor_hash, session_num,
            count(*) AS pv,
            dateDiff('second', min(ts), max(ts)) AS duration
        FROM sessionized
        GROUP BY visitor_hash, session_num
    )
    SELECT
        toInt64(sum(pv))              AS pageviews,
        toInt64(uniqExact(visitor_hash)) AS visitors,
        toInt64(count())              AS sessions,
        toInt64(countIf(pv = 1))      AS bounces,
        toInt64(sum(duration))        AS total_duration
    FROM _per_session
    """
    )
    return sql, _range_params(site_id, from_, to) | fparams


def build_timeseries(
    site_id: str,
    from_: datetime,
    to: datetime,
    bucket_fn: str,
    filters: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Pageviews + visitors per time bucket (gaps zero-filled in Python)."""
    fsql, fparams = _filter_clause(filters)
    sql = (
        f"SELECT {bucket_fn}(ts) AS bucket, "
        "toInt64(count()) AS pageviews, "
        "toInt64(uniqExact(visitor_hash)) AS visitors "
        "FROM events WHERE " + _BASE_WHERE + fsql + " GROUP BY bucket ORDER BY bucket"
    )
    return sql, _range_params(site_id, from_, to) | fparams


def build_breakdown(
    site_id: str,
    from_: datetime,
    to: datetime,
    column: str,
    limit: int,
    filters: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Top values of one column by visitors (sources / audience dimensions)."""
    fsql, fparams = _filter_clause(filters)
    sql = (
        f"SELECT {column} AS label, "
        "toInt64(count()) AS pageviews, "
        "toInt64(uniqExact(visitor_hash)) AS visitors "
        "FROM events WHERE " + _BASE_WHERE + fsql + " GROUP BY label "
        "ORDER BY visitors DESC, pageviews DESC, label ASC LIMIT {limit:UInt32}"
    )
    params = _range_params(site_id, from_, to) | fparams | {"limit": _clamp_limit(limit)}
    return sql, params


def build_utm(
    site_id: str,
    from_: datetime,
    to: datetime,
    limit: int,
    filters: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """UTM-tagged traffic grouped by the campaign triple (blank utm_source excluded)."""
    fsql, fparams = _filter_clause(filters)
    sql = (
        "SELECT utm_source, utm_medium, utm_campaign, "
        "toInt64(count()) AS pageviews, "
        "toInt64(uniqExact(visitor_hash)) AS visitors "
        "FROM events WHERE " + _BASE_WHERE + fsql + " AND utm_source != '' "
        "GROUP BY utm_source, utm_medium, utm_campaign "
        "ORDER BY visitors DESC, pageviews DESC LIMIT {limit:UInt32}"
    )
    params = _range_params(site_id, from_, to) | fparams | {"limit": _clamp_limit(limit)}
    return sql, params


def _host_array(hosts: tuple[str, ...]) -> str:
    """A ClickHouse array literal of host markers. Inputs are internal constants
    from `services/channels` (never user text), so literal formatting is safe."""
    return "[" + ", ".join(f"'{h}'" for h in hosts) + "]"


def _channel_expr() -> str:
    """The `multiIf` that maps each row's referrer to a channel label. Built from
    the shared `services/channels` host lists; AI is tested before search."""
    return (
        "multiIf("
        "referrer = '', 'direct', "
        f"multiSearchAnyCaseInsensitive(domain(referrer), {_host_array(channels_svc.AI_HOSTS)}) != 0, 'ai', "
        f"multiSearchAnyCaseInsensitive(domain(referrer), {_host_array(channels_svc.SEARCH_HOSTS)}) != 0, 'search', "
        f"multiSearchAnyCaseInsensitive(domain(referrer), {_host_array(channels_svc.SOCIAL_HOSTS)}) != 0, 'social', "
        "'referral')"
    )


def build_channels(
    site_id: str, from_: datetime, to: datetime, filters: dict[str, str] | None = None
) -> tuple[str, dict[str, Any]]:
    """The 5-way channel split (direct/search/social/ai/referral) by visitors."""
    fsql, fparams = _filter_clause(filters)
    sql = (
        f"SELECT {_channel_expr()} AS label, "
        "toInt64(count()) AS pageviews, "
        "toInt64(uniqExact(visitor_hash)) AS visitors "
        "FROM events WHERE " + _BASE_WHERE + fsql + " GROUP BY label "
        "ORDER BY visitors DESC, pageviews DESC, label ASC"
    )
    return sql, _range_params(site_id, from_, to) | fparams


def build_channel_referrers(
    site_id: str,
    from_: datetime,
    to: datetime,
    channel: str,
    limit: int,
    filters: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Referrer-host breakdown *within* one channel (search/social/ai drill-down).

    `channel` is validated against `channels.DRILLDOWN_CHANNELS` (an allowlist),
    so the host-list predicate baked into SQL is always an internal constant.
    """
    hosts = channels_svc.DRILLDOWN_CHANNELS.get(channel)
    if hosts is None:
        raise ValidationError(f"Unknown channel: {channel}")
    fsql, fparams = _filter_clause(filters)
    predicate = f"multiSearchAnyCaseInsensitive(domain(referrer), {_host_array(hosts)}) != 0"
    sql = (
        "SELECT domainWithoutWWW(referrer) AS label, "
        "toInt64(count()) AS pageviews, "
        "toInt64(uniqExact(visitor_hash)) AS visitors "
        "FROM events WHERE " + _BASE_WHERE + fsql + f" AND referrer != '' AND {predicate} "
        "GROUP BY label ORDER BY visitors DESC, pageviews DESC, label ASC LIMIT {limit:UInt32}"
    )
    params = _range_params(site_id, from_, to) | fparams | {"limit": _clamp_limit(limit)}
    return sql, params


def build_heatmap(
    site_id: str,
    from_: datetime,
    to: datetime,
    tz: str,
    filters: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Pageviews per (day-of-week, hour) in the viewer's timezone.

    §4 exception (deliberate): storage is UTC, but a time-of-day report is
    meaningless in UTC for a non-UTC audience, so we aggregate in the viewer's
    IANA tz via ClickHouse's `toHour(ts, tz)` / `toDayOfWeek(ts, tz)` — correct
    even for half-hour offsets, unlike rotating a UTC grid client-side. `tz` is a
    bound server-side param. `dow` is 1=Monday … 7=Sunday.
    """
    fsql, fparams = _filter_clause(filters)
    # NB: toDayOfWeek's 2nd arg is `week_mode` (0 → Mon=1…Sun=7); the timezone is
    # its 3rd arg. toHour's 2nd arg IS the timezone. They differ — don't unify.
    sql = (
        "SELECT toDayOfWeek(ts, 0, {tz:String}) AS dow, "
        "toHour(ts, {tz:String}) AS hour, "
        "toInt64(count()) AS pageviews, "
        "toInt64(uniqExact(visitor_hash)) AS visitors "
        "FROM events WHERE " + _BASE_WHERE + fsql + " GROUP BY dow, hour"
    )
    return sql, _range_params(site_id, from_, to) | fparams | {"tz": tz}


# Per-pageview engagement over the session CTE: `next_ts` is the visitor's next
# event *within the same session* (default 1970 when it's the session's last
# event -> counted as 0s on-page); `sess_pv` is that session's pageview count so
# a page viewed in a single-pageview session counts toward its bounce rate.
_ENGAGEMENT_SELECT = """
, _timed AS (
    SELECT path, visitor_hash, ts,
        leadInFrame(ts) OVER wnext AS next_ts,
        count(*) OVER wsess AS sess_pv
    FROM sessionized
    WINDOW
        wnext AS (
            PARTITION BY visitor_hash, session_num ORDER BY ts
            ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
        ),
        wsess AS (PARTITION BY visitor_hash, session_num)
)
SELECT path AS label,
    toInt64(count()) AS count,
    toInt64(uniqExact(visitor_hash)) AS visitors,
    toInt64(round(avg(if(next_ts > ts, dateDiff('second', ts, next_ts), 0)))) AS avg_duration,
    round(countIf(sess_pv = 1) / count() * 100, 1) AS bounce_rate
FROM _timed
GROUP BY label
ORDER BY avg_duration DESC, count DESC, label ASC LIMIT {limit:UInt32}
"""


def build_pages(
    site_id: str,
    from_: datetime,
    to: datetime,
    kind: str,
    limit: int,
    filters: dict[str, str] | None = None,
    sort: str = "traffic",
) -> tuple[str, dict[str, Any]]:
    """Top / entry / exit pages. Entry+exit derive from the session CTE.

    `sort="engagement"` ranks all pages by avg time-on-page (with per-page bounce
    rate), ignoring `kind` — it's a whole-site engagement view, not entry/exit.
    """
    fsql, fparams = _filter_clause(filters)
    params = _range_params(site_id, from_, to) | fparams | {"limit": _clamp_limit(limit)}
    if sort == "engagement":
        return _sessionized_cte(fsql) + _ENGAGEMENT_SELECT, params
    limit_clause = " ORDER BY count DESC, label ASC LIMIT {limit:UInt32}"
    if kind == "top":
        sql = (
            "SELECT path AS label, toInt64(count()) AS count, "
            "toInt64(uniqExact(visitor_hash)) AS visitors "
            "FROM events WHERE " + _BASE_WHERE + fsql + " GROUP BY label" + limit_clause
        )
    elif kind == "entry":
        # The first event of each session is flagged is_start.
        sql = _sessionized_cte(fsql) + (
            " SELECT path AS label, toInt64(count()) AS count, "
            "toInt64(uniqExact(visitor_hash)) AS visitors "
            "FROM sessionized WHERE is_start GROUP BY label" + limit_clause
        )
    else:  # exit
        sql = _sessionized_cte(fsql) + (
            ", _last AS ("
            " SELECT visitor_hash, session_num, argMax(path, ts) AS exit_path"
            " FROM sessionized GROUP BY visitor_hash, session_num"
            ") SELECT exit_path AS label, toInt64(count()) AS count, "
            "toInt64(uniqExact(visitor_hash)) AS visitors "
            "FROM _last GROUP BY label" + limit_clause
        )
    return sql, params


# --- Zero-fill + metric shaping -------------------------------------------
def _floor_bucket(dt: datetime, is_hour: bool) -> datetime:
    dt = dt.astimezone(UTC)
    if is_hour:
        return dt.replace(minute=0, second=0, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _walk_buckets(from_: datetime, to: datetime, is_hour: bool) -> list[datetime]:
    """Every bucket start in [from, to), so the chart x-axis has no gaps."""
    step = timedelta(hours=1) if is_hour else timedelta(days=1)
    bucket = _floor_bucket(from_, is_hour)
    out: list[datetime] = []
    while bucket < to:
        out.append(bucket)
        bucket += step
    return out


def _delta(value: float, previous: float | None) -> MetricDelta:
    change: float | None = None
    if previous:  # None or 0 -> no percentage (avoid divide-by-zero / infinity)
        change = round((value - previous) / previous * 100, 1)
    return MetricDelta(value=value, previous=previous, change_pct=change)


def _metrics_from_row(row: dict[str, Any]) -> dict[str, float]:
    """Raw counts -> the five display metrics (bounce %, avg duration derived)."""
    sessions = int(row["sessions"])
    bounces = int(row["bounces"])
    total_duration = int(row["total_duration"])
    return {
        "pageviews": int(row["pageviews"]),
        "visitors": int(row["visitors"]),
        "sessions": sessions,
        "bounce_rate": round(bounces / sessions * 100, 1) if sessions else 0.0,
        "avg_duration": round(total_duration / sessions) if sessions else 0,
    }


# --- Service functions (run builder -> shape response) --------------------
def _previous_window(from_: datetime, to: datetime) -> tuple[datetime, datetime]:
    span = to - from_
    return from_ - span, from_


async def overview(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    compare: bool,
    filters: dict[str, str] | None = None,
) -> OverviewOut:
    sql, params = build_overview(site_id, from_, to, filters)
    current = _metrics_from_row((await query_rows(client, sql, params))[0])

    previous: dict[str, float] | None = None
    if compare:
        pfrom, pto = _previous_window(from_, to)
        psql, pparams = build_overview(site_id, pfrom, pto, filters)
        previous = _metrics_from_row((await query_rows(client, psql, pparams))[0])

    def field(name: str) -> MetricDelta:
        return _delta(current[name], previous[name] if previous else None)

    return OverviewOut(
        pageviews=field("pageviews"),
        visitors=field("visitors"),
        sessions=field("sessions"),
        bounce_rate=field("bounce_rate"),
        avg_duration=field("avg_duration"),
    )


def _pick_bucket(from_: datetime, to: datetime) -> tuple[str, bool]:
    """Hour buckets for short ranges (≤ 2 days), day buckets otherwise."""
    is_hour = (to - from_) <= timedelta(days=2)
    return (_HOUR_FN if is_hour else _DAY_FN), is_hour


async def timeseries(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    filters: dict[str, str] | None = None,
) -> TimeseriesOut:
    bucket_fn, is_hour = _pick_bucket(from_, to)
    sql, params = build_timeseries(site_id, from_, to, bucket_fn, filters)
    rows = await query_rows(client, sql, params)
    # Key by the UTC instant so the DB buckets (naive-UTC) match our generated ones.
    by_bucket = {_aware_utc(r["bucket"]): r for r in rows}
    points = [
        TimeseriesPoint(
            bucket=bucket,
            pageviews=int(by_bucket[bucket]["pageviews"]) if bucket in by_bucket else 0,
            visitors=int(by_bucket[bucket]["visitors"]) if bucket in by_bucket else 0,
        )
        for bucket in _walk_buckets(from_, to, is_hour)
    ]
    return TimeseriesOut(interval="hour" if is_hour else "day", points=points)


def _breakdown_rows(rows: list[dict[str, Any]]) -> list[BreakdownRow]:
    return [
        BreakdownRow(
            label=str(r["label"]),
            pageviews=int(r["pageviews"]),
            visitors=int(r["visitors"]),
        )
        for r in rows
    ]


async def audience(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    dimension: str,
    limit: int,
    filters: dict[str, str] | None = None,
) -> BreakdownOut:
    # "screen" isn't a column but a width-bucket expression; everything else is a
    # bare allowlisted column. Both go through the same breakdown builder.
    if dimension == "screen":
        column = _SCREEN_BUCKET_SQL
    else:
        column = _AUDIENCE_COLUMNS.get(dimension)
        if column is None:
            raise ValidationError(f"Unknown dimension: {dimension}")
    sql, params = build_breakdown(site_id, from_, to, column, limit, filters)
    return BreakdownOut(
        dimension=dimension, rows=_breakdown_rows(await query_rows(client, sql, params))
    )


async def sources(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    limit: int,
    filters: dict[str, str] | None = None,
) -> SourcesOut:
    ssql, sparams = build_breakdown(site_id, from_, to, "source", limit, filters)
    usql, uparams = build_utm(site_id, from_, to, limit, filters)
    source_rows = _breakdown_rows(await query_rows(client, ssql, sparams))
    utm_rows = [
        UtmRow(
            utm_source=str(r["utm_source"]),
            utm_medium=str(r["utm_medium"]),
            utm_campaign=str(r["utm_campaign"]),
            pageviews=int(r["pageviews"]),
            visitors=int(r["visitors"]),
        )
        for r in await query_rows(client, usql, uparams)
    ]
    return SourcesOut(sources=source_rows, utm=utm_rows)


async def channels(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    filters: dict[str, str] | None = None,
) -> ChannelsOut:
    sql, params = build_channels(site_id, from_, to, filters)
    rows = [
        ChannelRow(
            channel=str(r["label"]),
            pageviews=int(r["pageviews"]),
            visitors=int(r["visitors"]),
        )
        for r in await query_rows(client, sql, params)
    ]
    return ChannelsOut(channels=rows)


async def channel_referrers(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    channel: str,
    limit: int,
    filters: dict[str, str] | None = None,
) -> BreakdownOut:
    """Referrer hosts within one channel (search/social/ai drill-down)."""
    sql, params = build_channel_referrers(site_id, from_, to, channel, limit, filters)
    return BreakdownOut(
        dimension=channel, rows=_breakdown_rows(await query_rows(client, sql, params))
    )


async def heatmap(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    tz: str,
    filters: dict[str, str] | None = None,
) -> HeatmapOut:
    sql, params = build_heatmap(site_id, from_, to, tz, filters)
    # Key the sparse DB rows by (dow, hour), then emit a dense 7×24 grid so the
    # frontend never has to reason about missing cells. dow 1=Mon … 7=Sun.
    by_cell = {(int(r["dow"]), int(r["hour"])): r for r in await query_rows(client, sql, params)}
    cells = [
        HeatmapCell(
            dow=dow,
            hour=hour,
            pageviews=int(by_cell[(dow, hour)]["pageviews"]) if (dow, hour) in by_cell else 0,
            visitors=int(by_cell[(dow, hour)]["visitors"]) if (dow, hour) in by_cell else 0,
        )
        for dow in range(1, 8)
        for hour in range(24)
    ]
    return HeatmapOut(timezone=tz, cells=cells)


async def pages(
    client: AsyncClient,
    site_id: str,
    from_: datetime,
    to: datetime,
    kind: str,
    limit: int,
    filters: dict[str, str] | None = None,
    sort: str = "traffic",
) -> PagesOut:
    if kind not in _PAGE_KINDS:
        raise ValidationError(f"Unknown page kind: {kind}")
    sql, params = build_pages(site_id, from_, to, kind, limit, filters, sort)
    rows = [
        PageRow(
            label=str(r["label"]),
            count=int(r["count"]),
            visitors=int(r["visitors"]),
            # Present only on the engagement ranking; None for traffic sorts.
            avg_duration=int(r["avg_duration"]) if "avg_duration" in r else None,
            bounce_rate=float(r["bounce_rate"]) if "bounce_rate" in r else None,
        )
        for r in await query_rows(client, sql, params)
    ]
    # Engagement ranks all pageviews; `top` counts pageviews; entry/exit count
    # sessions landing/leaving on a path.
    metric = "pageviews" if (kind == "top" or sort == "engagement") else "sessions"
    return PagesOut(kind=kind, metric=metric, rows=rows)
