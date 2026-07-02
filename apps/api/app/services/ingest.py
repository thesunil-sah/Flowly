"""Ingestion orchestration — the `/collect` business logic (CLAUDE.md §3).

`ingest_event` runs the full hot path for one pageview: bot filter, rate-limit
backstop, cookieless hashing, geo + device enrichment, source derivation, and a
push onto the Redis ingest stream. It returns fast and never writes to
ClickHouse synchronously — the batch writer drains the stream.

Privacy invariant: the raw IP is used only to compute the visitor hash and geo,
then discarded. The row pushed to the stream is **IP-free**, so no raw IP is
ever at rest (the stream is a buffer at rest). Enriching here — before
buffering — is what makes that possible.

Contains no HTTP objects; the router passes primitives in and gets a value back.
"""

from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import uuid4

from redis.asyncio import Redis

from app.config import settings
from app.core.ratelimit import is_rate_limited
from app.models.events import CollectEvent
from app.services import geo, useragent, visitor

# The Redis Stream the batch writer drains. Shared with workers/batch_writer.py.
STREAM_KEY = "stream:events"


def _host(url: str) -> str:
    """Lowercased hostname of a URL, `www.` stripped; "" if unparseable."""
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    # Drop any port and a leading www. for stable comparison/labelling.
    host = netloc.split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def derive_source(utm_source: str | None, referrer: str, origin: str | None) -> str:
    """Traffic source: UTM wins, else external referrer host, else "direct".

    A referrer whose host matches the page's own `Origin` is same-site
    navigation and reported as `direct` (not the site's own domain).
    """
    if utm_source:
        return utm_source
    ref_host = _host(referrer)
    if not ref_host:
        return "direct"
    if ref_host == _host(origin or ""):
        return "direct"
    return ref_host


def build_stream_row(event: CollectEvent, ip: str, ua: str, origin: str | None) -> dict[str, str]:
    """Enrich one validated event into a flat, IP-free stream row (all strings).

    Redis stream fields are strings; `None` becomes `""`. The batch writer
    coerces `event_id`/`ts`/`screen_w` back to their ClickHouse types.
    """
    country, region = geo.lookup(ip)
    device, browser, os_name = useragent.parse(ua)
    return {
        "event_id": str(uuid4()),
        "site_id": event.site_id,
        "ts": datetime.now(UTC).isoformat(),
        "path": event.path,
        "referrer": event.referrer or "",
        "source": derive_source(event.utm_source, event.referrer, origin),
        "utm_source": event.utm_source or "",
        "utm_medium": event.utm_medium or "",
        "utm_campaign": event.utm_campaign or "",
        "country": country,
        "region": region,
        "device": device,
        "browser": browser,
        "os": os_name,
        # visitor_hash is added by the caller (needs the daily salt from Redis).
        "visitor_hash": "",
        "screen_w": str(event.screen_w),
    }


async def ingest_event(
    event: CollectEvent,
    ip: str,
    ua: str,
    origin: str | None,
    redis: Redis,
) -> str | None:
    """Process one pageview. Returns the event_id if buffered, else None (dropped).

    Drops (bot / over-rate-limit) are silent — the endpoint still returns 202.
    """
    if useragent.is_bot(ua):
        return None
    if await is_rate_limited(redis, event.site_id, ip):
        return None

    row = build_stream_row(event, ip, ua, origin)
    salt = await visitor.get_daily_salt(redis)
    row["visitor_hash"] = visitor.visitor_hash(ip, ua, event.site_id, salt)

    await redis.xadd(
        STREAM_KEY,
        row,
        maxlen=settings.stream_maxlen,
        approximate=True,
    )
    return row["event_id"]
