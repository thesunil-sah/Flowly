"""Weekly digest — rendering + worker idempotency (§8)."""

from datetime import UTC, datetime

import fakeredis.aioredis

from app.services import digest, notifications
from app.services.digest import SiteDigest
from app.workers import digest as digest_worker

NOW = datetime(2026, 7, 6, 8, 0, tzinfo=UTC)


def test_render_digest_includes_active_sites() -> None:
    d = SiteDigest(
        domain="a.com",
        visitors=100,
        pageviews=250,
        visitors_change_pct=12.0,
        top_pages=[("/", 120)],
        top_sources=[("google", 40)],
    )
    subject, html, _text = digest.render_digest("bob", [d], NOW)
    assert "week in review" in subject.lower()
    assert "a.com" in html
    assert "100" in html  # visitor count rendered


def test_render_digest_skips_zero_traffic_sites() -> None:
    d = SiteDigest(domain="empty.com", visitors=0, pageviews=0, visitors_change_pct=None)
    _subject, html, _text = digest.render_digest("bob", [d], NOW)
    assert "empty.com" not in html


async def test_digest_worker_is_idempotent_per_week(session_factory, monkeypatch) -> None:
    from app.models.tables import Account, Site

    async with session_factory() as s:
        acc = Account(email="u@e.com", username="u", email_verified_at=NOW)
        s.add(acc)
        await s.flush()
        s.add(Site(account_id=acc.id, site_id="pub0", domain="a.com"))
        await s.commit()

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sent: list[str] = []

    async def fake_ch():
        return object()

    async def fake_build(client, site_id, domain, now):
        return SiteDigest(
            domain=domain,
            visitors=10,
            pageviews=20,
            visitors_change_pct=None,
            top_pages=[("/", 20)],
            top_sources=[("Direct", 10)],
        )

    async def fake_send(to, subject, text, html=None):
        sent.append(to)

    monkeypatch.setattr(digest_worker, "get_clickhouse", fake_ch)
    monkeypatch.setattr(digest_worker, "get_client", lambda: fake)
    monkeypatch.setattr(digest_worker, "async_session_factory", session_factory)
    monkeypatch.setattr(digest, "build_site_digest", fake_build)
    monkeypatch.setattr(notifications, "send_email", fake_send)

    first = await digest_worker.run(NOW)
    second = await digest_worker.run(NOW)  # same ISO week
    assert first == 1
    assert second == 0  # marker blocks the re-send
    assert len(sent) == 1
    await fake.aclose()


async def test_digest_worker_skips_zero_traffic_account(session_factory, monkeypatch) -> None:
    from app.models.tables import Account, Site

    async with session_factory() as s:
        acc = Account(email="q@e.com", username="q", email_verified_at=NOW)
        s.add(acc)
        await s.flush()
        s.add(Site(account_id=acc.id, site_id="pubq", domain="q.com"))
        await s.commit()

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sent: list[str] = []

    async def fake_ch():
        return object()

    async def fake_build(client, site_id, domain, now):
        return SiteDigest(domain=domain, visitors=0, pageviews=0, visitors_change_pct=None)

    async def fake_send(to, subject, text, html=None):
        sent.append(to)

    monkeypatch.setattr(digest_worker, "get_clickhouse", fake_ch)
    monkeypatch.setattr(digest_worker, "get_client", lambda: fake)
    monkeypatch.setattr(digest_worker, "async_session_factory", session_factory)
    monkeypatch.setattr(digest, "build_site_digest", fake_build)
    monkeypatch.setattr(notifications, "send_email", fake_send)

    assert await digest_worker.run(NOW) == 0
    assert sent == []
    await fake.aclose()
