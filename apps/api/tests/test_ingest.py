"""Ingest orchestration: enrichment, source derivation, and the stream row."""

import asyncio

import app.db.redis as redis_mod
import fakeredis.aioredis
import pytest_asyncio

from app.models.events import CollectEvent
from app.services import ingest, live, visitor
from app.services.ingest import derive_source

UA = "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
STREAM = "stream:events"


@pytest_asyncio.fixture
async def redis() -> fakeredis.aioredis.FakeRedis:
    visitor._reset_cache()
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


def _event(**over: object) -> CollectEvent:
    base = {"site_id": "demo", "path": "/p", "referrer": "", "screen_w": 1440}
    base.update(over)
    return CollectEvent.model_validate(base)


def test_derive_source_utm_wins() -> None:
    assert derive_source("newsletter", "https://google.com", "https://demo.example") == "newsletter"


def test_derive_source_external_referrer() -> None:
    assert (
        derive_source(None, "https://www.google.com/search", "https://demo.example") == "google.com"
    )


def test_derive_source_same_site_is_direct() -> None:
    assert derive_source(None, "https://demo.example/x", "https://demo.example") == "direct"


def test_derive_source_no_referrer_is_direct() -> None:
    assert derive_source(None, "", None) == "direct"


async def test_ingest_enriches_and_enqueues(redis) -> None:
    eid = await ingest.ingest_event(
        _event(utm_source="nl"), "9.9.9.9", UA, "https://demo.example", redis
    )
    assert eid is not None
    _id, fields = (await redis.xrange(STREAM))[0]
    assert fields["event_id"] == eid
    assert fields["device"] == "desktop"
    assert fields["browser"] == "Chrome"
    assert fields["os"] == "Windows"
    assert fields["source"] == "nl"
    assert fields["screen_w"] == "1440"
    assert len(fields["visitor_hash"]) == 64


async def test_ingest_row_has_no_raw_ip(redis) -> None:
    await ingest.ingest_event(_event(), "198.51.100.7", UA, None, redis)
    _id, fields = (await redis.xrange(STREAM))[0]
    assert "198.51.100.7" not in str(fields)


async def test_ingest_event_ids_are_unique(redis) -> None:
    a = await ingest.ingest_event(_event(), "9.9.9.9", UA, None, redis)
    b = await ingest.ingest_event(_event(), "9.9.9.9", UA, None, redis)
    assert a != b


async def test_bot_is_dropped(redis) -> None:
    result = await ingest.ingest_event(_event(), "9.9.9.9", "Googlebot/2.1", None, redis)
    assert result is None
    assert await redis.xlen(STREAM) == 0


async def test_over_rate_limit_is_dropped(redis, monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "collect_rate_limit", 2)
    for _ in range(2):
        assert await ingest.ingest_event(_event(), "9.9.9.9", UA, None, redis) is not None
    # Third from the same (site, IP) is over the limit -> dropped silently.
    assert await ingest.ingest_event(_event(), "9.9.9.9", UA, None, redis) is None
    assert await redis.xlen(STREAM) == 2


async def test_ingest_marks_active_and_publishes(redis, monkeypatch) -> None:
    # subscribe_events reads the shared client; point it at the same fake so the
    # publish from ingest_event reaches this subscriber.
    monkeypatch.setattr(redis_mod, "_client", redis)
    received: list[dict[str, object]] = []
    ready = asyncio.Event()

    async def _on_ready() -> None:
        ready.set()

    async def consume() -> None:
        async for event in live.subscribe_events("demo", on_ready=_on_ready):
            received.append(event)
            break

    task = asyncio.create_task(consume())
    await asyncio.wait_for(ready.wait(), 2)
    await ingest.ingest_event(_event(), "203.0.113.5", UA, "https://demo.example", redis)
    await asyncio.wait_for(task, 2)

    # Visitor recorded in the presence set...
    assert await redis.zcard("active:demo") == 1
    # ...and the forwarded payload is IP-free and carries no visitor_hash.
    payload = received[0]
    assert payload["path"] == "/p"
    assert "visitor_hash" not in payload
    assert "203.0.113.5" not in str(payload)
