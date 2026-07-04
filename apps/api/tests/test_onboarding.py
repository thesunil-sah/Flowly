"""Onboarding sequence worker — step gating + idempotency (§8)."""

from datetime import UTC, datetime, timedelta

import fakeredis.aioredis

from app.models.tables import Account, OnboardingEmail, Site
from app.services import notifications, sites
from app.workers import onboarding as onboarding_worker

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _patch_clients(monkeypatch, session_factory, fake, connected: bool):
    async def fake_ch():
        return object()

    async def fake_connected(redis, ch, site_id):
        return connected

    monkeypatch.setattr(onboarding_worker, "get_clickhouse", fake_ch)
    monkeypatch.setattr(onboarding_worker, "get_client", lambda: fake)
    monkeypatch.setattr(onboarding_worker, "async_session_factory", session_factory)
    monkeypatch.setattr(sites, "first_event_seen", fake_connected)


async def _seed_account(session_factory, *, created_at: datetime, with_site: bool = True) -> None:
    async with session_factory() as s:
        acc = Account(email="u@e.com", username="u", email_verified_at=NOW, created_at=created_at)
        s.add(acc)
        await s.flush()
        if with_site:
            s.add(Site(account_id=acc.id, site_id="pub0", domain="a.com"))
        await s.commit()


async def _ledger_steps(session_factory) -> set[str]:
    from sqlalchemy import select

    async with session_factory() as s:
        rows = await s.scalars(select(OnboardingEmail))
        return {r.step for r in rows.all()}


async def test_welcome_sent_once(session_factory, monkeypatch) -> None:
    await _seed_account(session_factory, created_at=NOW, with_site=False)
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    subjects: list[str] = []

    async def fake_send(to, subject, text, html=None):
        subjects.append(subject)

    _patch_clients(monkeypatch, session_factory, fake, connected=False)
    monkeypatch.setattr(notifications, "send_email", fake_send)

    await onboarding_worker.run(NOW)
    await onboarding_worker.run(NOW)  # second pass must not resend
    assert subjects.count("Welcome to Flowly") == 1
    await fake.aclose()


async def test_connected_sends_live_and_marks_install_without_email(
    session_factory, monkeypatch
) -> None:
    await _seed_account(session_factory, created_at=NOW)
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    subjects: list[str] = []

    async def fake_send(to, subject, text, html=None):
        subjects.append(subject)

    _patch_clients(monkeypatch, session_factory, fake, connected=True)
    monkeypatch.setattr(notifications, "send_email", fake_send)

    await onboarding_worker.run(NOW)
    # welcome + live emailed; install recorded but NOT emailed (already live).
    assert "Welcome to Flowly" in subjects
    assert any(s.startswith("🎉") for s in subjects)
    assert "Finish setting up Flowly" not in subjects
    assert await _ledger_steps(session_factory) == {"welcome", "live", "install"}
    await fake.aclose()


async def test_install_nudge_sent_when_dark_after_delay(session_factory, monkeypatch) -> None:
    # Signed up 25h ago, still not collecting -> install nudge fires.
    await _seed_account(session_factory, created_at=NOW - timedelta(hours=25))
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    subjects: list[str] = []

    async def fake_send(to, subject, text, html=None):
        subjects.append(subject)

    _patch_clients(monkeypatch, session_factory, fake, connected=False)
    monkeypatch.setattr(notifications, "send_email", fake_send)

    await onboarding_worker.run(NOW)
    assert "Finish setting up Flowly" in subjects
    assert not any(s.startswith("🎉") for s in subjects)  # not live yet
    await fake.aclose()


async def test_install_nudge_suppressed_before_delay(session_factory, monkeypatch) -> None:
    # Signed up 1h ago, not connected -> too early for the nudge.
    await _seed_account(session_factory, created_at=NOW - timedelta(hours=1))
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    subjects: list[str] = []

    async def fake_send(to, subject, text, html=None):
        subjects.append(subject)

    _patch_clients(monkeypatch, session_factory, fake, connected=False)
    monkeypatch.setattr(notifications, "send_email", fake_send)

    await onboarding_worker.run(NOW)
    assert "Finish setting up Flowly" not in subjects
    assert await _ledger_steps(session_factory) == {"welcome"}
    await fake.aclose()
