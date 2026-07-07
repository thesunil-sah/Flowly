"""Phase 13 Search Console — property match, connect flow, sync idempotency,
report aggregation, ownership, and token-never-leaked.
"""

from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token
from app.models.tables import Account, SearchConsoleConnection, SearchMetric, Site
from app.services import gscapi, searchconsole
from app.workers import searchconsole as sc_worker

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


# --- Property matching ----------------------------------------------------
def test_match_property_prefers_sc_domain() -> None:
    props = ["https://example.com/", "sc-domain:example.com"]
    assert gscapi.match_property("example.com", props) == "sc-domain:example.com"


def test_match_property_url_prefix_and_www() -> None:
    assert gscapi.match_property("example.com", ["https://www.example.com/"]) == (
        "https://www.example.com/"
    )
    assert gscapi.match_property("www.example.com", ["sc-domain:example.com"]) == (
        "sc-domain:example.com"
    )


def test_match_property_no_match_returns_none() -> None:
    assert gscapi.match_property("example.com", ["sc-domain:other.com"]) is None


# --- Connect state --------------------------------------------------------
async def test_connect_state_roundtrip() -> None:
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    acc = UUID("00000000-0000-0000-0000-0000000000aa")
    state = await searchconsole.create_connect_state(redis, acc, "pub0")
    got_acc, got_site = await searchconsole.consume_connect_state(redis, state)
    assert got_acc == acc and got_site == "pub0"
    # Consumed once — a replay fails.
    with pytest.raises(Exception):
        await searchconsole.consume_connect_state(redis, state)
    await redis.aclose()


# --- Sync -----------------------------------------------------------------
class _FakeGsc:
    """Stand-in for the Google API layer — no network."""

    def __init__(self, rows_by_day: dict[date, list[gscapi.GscRow]] | None = None) -> None:
        self.rows_by_day = rows_by_day or {}
        self.token_calls = 0

    async def refresh_access_token(self, refresh_token: str) -> str:
        self.token_calls += 1
        return "access-token"

    async def query(self, access_token: str, property_url: str, day: date, limit: int):
        return self.rows_by_day.get(day, [])


async def _seed_connection(
    factory: async_sessionmaker[AsyncSession], domain: str = "example.com"
) -> UUID:
    async with factory() as s:
        acc = Account(email="o@e.com", username="o", email_verified_at=NOW)
        s.add(acc)
        await s.flush()
        site = Site(account_id=acc.id, site_id="pub0", domain=domain)
        s.add(site)
        await s.flush()
        s.add(
            SearchConsoleConnection(
                site_id=site.id, property_url="sc-domain:example.com", refresh_token="rt-secret"
            )
        )
        await s.commit()
        return site.id


async def test_sync_writes_rows_and_is_idempotent_per_day(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    site_id = await _seed_connection(session_factory)
    day = NOW.date() - timedelta(days=searchconsole._GSC_LAG_DAYS)
    fake = _FakeGsc({day: [gscapi.GscRow("shoes", "https://example.com/s", 3, 40, 4.0)]})
    monkeypatch.setattr(gscapi, "refresh_access_token", fake.refresh_access_token)
    monkeypatch.setattr(gscapi, "query_search_analytics", fake.query)
    # Keep the sweep small + deterministic.
    monkeypatch.setattr(searchconsole.settings, "gsc_sync_days", 1)

    async with session_factory() as s:
        conn = await s.scalar(select(SearchConsoleConnection))
        await searchconsole.sync_site(s, conn, NOW)
        await searchconsole.sync_site(s, conn, NOW)  # re-run same day
        count = await s.scalar(
            select(func.count()).select_from(SearchMetric).where(SearchMetric.site_id == site_id)
        )
        # Delete-then-insert per day → still exactly one row, not two.
        assert count == 1
        conn2 = await s.scalar(select(SearchConsoleConnection))
        assert conn2.last_synced_at is not None


async def test_sync_truncates_overlong_query_and_page(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    site_id = await _seed_connection(session_factory)
    day = NOW.date() - timedelta(days=searchconsole._GSC_LAG_DAYS)
    # GSC can hand back a page URL longer than the column — must not abort the
    # insert (would zero out the whole day on Postgres).
    long_row = gscapi.GscRow("q" * 900, "https://x/" + "p" * 4000, 1, 10, 2.0)
    fake = _FakeGsc({day: [long_row]})
    monkeypatch.setattr(gscapi, "refresh_access_token", fake.refresh_access_token)
    monkeypatch.setattr(gscapi, "query_search_analytics", fake.query)
    monkeypatch.setattr(searchconsole.settings, "gsc_sync_days", 1)

    async with session_factory() as s:
        conn = await s.scalar(select(SearchConsoleConnection))
        await searchconsole.sync_site(s, conn, NOW)
        metric = await s.scalar(select(SearchMetric).where(SearchMetric.site_id == site_id))
        assert metric is not None
        assert len(metric.query) == searchconsole._QUERY_MAXLEN
        assert len(metric.page) == searchconsole._PAGE_MAXLEN


async def test_manual_sync_only_pulls_bounded_window(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_connection(session_factory)
    queried: list[date] = []

    async def record_query(access_token: str, property_url: str, day: date, limit: int):
        queried.append(day)
        return []

    async def fake_refresh(rt: str) -> str:
        return "at"

    monkeypatch.setattr(gscapi, "refresh_access_token", fake_refresh)
    monkeypatch.setattr(gscapi, "query_search_analytics", record_query)
    # Full window is large; the manual window must stay small regardless.
    monkeypatch.setattr(searchconsole.settings, "gsc_sync_days", 30)

    async with session_factory() as s:
        conn = await s.scalar(select(SearchConsoleConnection))
        await searchconsole.sync_site(s, conn, NOW, days=searchconsole.MANUAL_SYNC_DAYS)
    assert len(queried) == searchconsole.MANUAL_SYNC_DAYS


async def test_sync_all_best_effort_survives_one_failure(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_connection(session_factory)

    async def boom(refresh_token: str) -> str:
        raise gscapi.GscError("expired")

    monkeypatch.setattr(gscapi, "refresh_access_token", boom)
    async with session_factory() as s:
        synced = await searchconsole.sync_all(s, NOW)  # must not raise
    assert synced == 0


# --- Reports --------------------------------------------------------------
async def _seed_metrics(factory: async_sessionmaker[AsyncSession]) -> tuple[UUID, UUID]:
    async with factory() as s:
        acc = Account(email="o@e.com", username="o")
        s.add(acc)
        await s.flush()
        site = Site(account_id=acc.id, site_id="pub0", domain="example.com")
        s.add(site)
        await s.flush()
        d1, d2 = date(2026, 7, 1), date(2026, 7, 2)
        s.add_all(
            [
                # "shoes" across two days: weighted pos = (3*100 + 5*100)/200 = 4.0
                SearchMetric(
                    site_id=site.id,
                    date=d1,
                    query="shoes",
                    page="/s",
                    clicks=10,
                    impressions=100,
                    position=3.0,
                ),
                SearchMetric(
                    site_id=site.id,
                    date=d2,
                    query="shoes",
                    page="/s",
                    clicks=5,
                    impressions=100,
                    position=5.0,
                ),
                # "boots": page-two rank + high impressions → an opportunity
                SearchMetric(
                    site_id=site.id,
                    date=d1,
                    query="boots",
                    page="/b",
                    clicks=1,
                    impressions=500,
                    position=8.0,
                ),
                # "hats": ranks #2 → NOT an opportunity (already on page one)
                SearchMetric(
                    site_id=site.id,
                    date=d1,
                    query="hats",
                    page="/h",
                    clicks=50,
                    impressions=600,
                    position=2.0,
                ),
            ]
        )
        await s.commit()
        return acc.id, site.id


async def test_keyword_report_aggregates_and_weights_position(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _acc, site_id = await _seed_metrics(session_factory)
    async with session_factory() as s:
        rows = await searchconsole.keyword_report(
            s, site_id, date(2026, 7, 1), date(2026, 7, 2), 25
        )
    by = {r["label"]: r for r in rows}
    assert by["shoes"]["clicks"] == 15
    assert by["shoes"]["impressions"] == 200
    assert by["shoes"]["position"] == 4.0  # impression-weighted
    assert by["shoes"]["ctr"] == round(15 / 200, 4)
    # Ranked by clicks: hats (50) first.
    assert rows[0]["label"] == "hats"


async def test_opportunity_report_filters_position_band(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _acc, site_id = await _seed_metrics(session_factory)
    async with session_factory() as s:
        rows = await searchconsole.opportunity_report(
            s, site_id, date(2026, 7, 1), date(2026, 7, 2), 25
        )
    labels = {r["label"] for r in rows}
    assert "boots" in labels  # position 8 → just off page one
    assert "hats" not in labels  # position 2 → already ranking well
    assert "shoes" not in labels  # position 4 → already top-5


# --- Endpoints (ownership + no token leak) --------------------------------
async def test_keywords_endpoint_ownership_scoped(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as s:
        owner = Account(email="own@e.com", username="own")
        other = Account(email="oth@e.com", username="oth")
        s.add_all([owner, other])
        await s.flush()
        s.add(Site(account_id=owner.id, site_id="mine", domain="a.com"))
        s.add(Site(account_id=other.id, site_id="theirs", domain="b.com"))
        await s.commit()
        owner_id = owner.id

    headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
    assert (await client.get("/searchconsole/mine/keywords", headers=headers)).status_code == 200
    leak = await client.get("/searchconsole/theirs/keywords", headers=headers)
    assert leak.status_code == 404


async def test_connection_endpoint_never_returns_refresh_token(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as s:
        acc = Account(email="o@e.com", username="o")
        s.add(acc)
        await s.flush()
        site = Site(account_id=acc.id, site_id="mine", domain="a.com")
        s.add(site)
        await s.flush()
        s.add(
            SearchConsoleConnection(
                site_id=site.id, property_url="sc-domain:a.com", refresh_token="TOP-SECRET-RT"
            )
        )
        await s.commit()
        owner_id = acc.id

    headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
    resp = await client.get("/searchconsole/mine/connection", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True and body["property_url"] == "sc-domain:a.com"
    assert "TOP-SECRET-RT" not in resp.text  # refresh token never leaves the server


async def test_connect_then_callback_stores_connection(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with session_factory() as s:
        acc = Account(email="o@e.com", username="o")
        s.add(acc)
        await s.flush()
        s.add(Site(account_id=acc.id, site_id="mine", domain="example.com"))
        await s.commit()
        owner_id = acc.id

    # Configure Google creds + stub the whole Google round-trip.
    monkeypatch.setattr(searchconsole.settings, "google_client_id", "cid")
    monkeypatch.setattr(searchconsole.settings, "google_client_secret", "csecret")
    monkeypatch.setattr(gscapi.settings, "google_client_id", "cid")

    async def fake_exchange(code: str) -> str:
        return "rt-secret"

    async def fake_refresh(rt: str) -> str:
        return "at"

    async def fake_list(at: str) -> list[str]:
        return ["sc-domain:example.com"]

    monkeypatch.setattr(gscapi, "exchange_code", fake_exchange)
    monkeypatch.setattr(gscapi, "refresh_access_token", fake_refresh)
    monkeypatch.setattr(gscapi, "list_properties", fake_list)

    headers = {"Authorization": f"Bearer {create_access_token(owner_id)}"}
    start = await client.post("/searchconsole/mine/connect", headers=headers)
    assert start.status_code == 200
    state = parse_qs(urlparse(start.json()["authorize_url"]).query)["state"][0]

    cb = await client.get(f"/searchconsole/callback?code=abc&state={state}")
    assert cb.status_code in (302, 307)
    assert "gsc=connected" in cb.headers["location"]

    async with session_factory() as s:
        conn = await s.scalar(select(SearchConsoleConnection))
        assert conn is not None and conn.property_url == "sc-domain:example.com"


async def test_disconnect_wipes_connection_and_metrics(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    site_id = await _seed_connection(session_factory)
    async with session_factory() as s:
        s.add(
            SearchMetric(
                site_id=site_id,
                date=date(2026, 7, 1),
                query="q",
                page="/p",
                clicks=1,
                impressions=1,
                position=1.0,
            )
        )
        await s.commit()
        site = await s.get(Site, site_id)
        await searchconsole.disconnect(s, site)
        assert await s.scalar(select(func.count()).select_from(SearchConsoleConnection)) == 0
        assert await s.scalar(select(func.count()).select_from(SearchMetric)) == 0


async def test_worker_run_syncs_all(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_connection(session_factory)
    day = NOW.date() - timedelta(days=searchconsole._GSC_LAG_DAYS)
    fake = _FakeGsc({day: [gscapi.GscRow("q", "/p", 1, 10, 2.0)]})
    monkeypatch.setattr(gscapi, "refresh_access_token", fake.refresh_access_token)
    monkeypatch.setattr(gscapi, "query_search_analytics", fake.query)
    monkeypatch.setattr(searchconsole.settings, "gsc_sync_days", 1)
    monkeypatch.setattr(sc_worker, "async_session_factory", session_factory)

    synced = await sc_worker.run(NOW)
    assert synced == 1
