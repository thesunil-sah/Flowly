"""POST /collect endpoint behaviour.

Ingest never touches ClickHouse (the batch writer does), so these run entirely
on the fakeredis `client` fixture. We assert on the stream state via the same
fake instance the app uses.
"""

import fakeredis.aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.redis import get_redis
from app.main import app
from app.services import visitor

STREAM = "stream:events"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

VALID_BODY = (
    '{"site_id":"demo","path":"/pricing","referrer":"https://google.com",'
    '"screen_w":1440,"language":"en-US","utm_source":"newsletter",'
    '"utm_medium":null,"utm_campaign":null}'
)


@pytest_asyncio.fixture
async def collect_client() -> tuple[AsyncClient, fakeredis.aioredis.FakeRedis]:
    """A client plus a handle to the exact fake Redis the app uses."""
    visitor._reset_cache()
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def override_redis() -> fakeredis.aioredis.FakeRedis:
        return fake

    app.dependency_overrides[get_redis] = override_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, fake
    app.dependency_overrides.clear()
    await fake.aclose()


def _headers(**extra: str) -> dict[str, str]:
    base = {"content-type": "text/plain", "user-agent": CHROME}
    base.update(extra)
    return base


async def test_valid_event_returns_202_and_enqueues(collect_client) -> None:
    client, fake = collect_client
    resp = await client.post(
        "/collect", content=VALID_BODY, headers=_headers(origin="https://demo.example")
    )
    assert resp.status_code == 202
    # Open CORS for the public tracker.
    assert resp.headers["access-control-allow-origin"] == "*"
    assert await fake.xlen(STREAM) == 1

    _id, fields = (await fake.xrange(STREAM))[0]
    # Stray "language" was ignored, core fields present, source from UTM.
    assert fields["site_id"] == "demo"
    assert fields["source"] == "newsletter"
    assert len(fields["visitor_hash"]) == 64


async def test_malformed_json_rejected(collect_client) -> None:
    client, fake = collect_client
    resp = await client.post("/collect", content="{not json", headers=_headers())
    assert resp.status_code == 422
    assert await fake.xlen(STREAM) == 0


async def test_missing_site_id_rejected(collect_client) -> None:
    client, fake = collect_client
    resp = await client.post("/collect", content='{"path":"/x"}', headers=_headers())
    assert resp.status_code == 422
    assert await fake.xlen(STREAM) == 0


async def test_bot_dropped_silently(collect_client) -> None:
    client, fake = collect_client
    resp = await client.post(
        "/collect", content=VALID_BODY, headers=_headers(**{"user-agent": "Googlebot/2.1"})
    )
    # Still 202 so the filter isn't detectable, but nothing enqueued.
    assert resp.status_code == 202
    assert await fake.xlen(STREAM) == 0


async def test_no_raw_ip_in_stream(collect_client) -> None:
    client, fake = collect_client
    await client.post(
        "/collect",
        content=VALID_BODY,
        headers=_headers(origin="https://demo.example", **{"x-forwarded-for": "203.0.113.9"}),
    )
    _id, fields = (await fake.xrange(STREAM))[0]
    assert "203.0.113.9" not in str(fields)


async def test_same_site_referrer_is_direct(collect_client) -> None:
    client, fake = collect_client
    body = (
        '{"site_id":"demo","path":"/about","referrer":"https://demo.example/home","screen_w":800}'
    )
    await client.post("/collect", content=body, headers=_headers(origin="https://demo.example"))
    _id, fields = (await fake.xrange(STREAM))[0]
    assert fields["source"] == "direct"
