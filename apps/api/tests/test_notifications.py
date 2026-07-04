"""Non-transactional email gate + unsubscribe (§8).

Locks the promises that keep us on the right side of consent: an opted-out
account is never emailed, every marketing email carries an unsubscribe link, and
the signed unsubscribe token flips exactly one flag.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import AuthError
from app.core.security import create_access_token, create_unsubscribe_token
from app.models.tables import Account
from app.services import notifications

NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _transient_account(opt_out: bool = False) -> Account:
    return Account(id=UUID(int=1), email="u@example.com", username="u", email_opt_out=opt_out)


async def test_marketing_suppressed_when_opted_out(monkeypatch) -> None:
    sent: list[str] = []

    async def fake_send(to, subject, text, html=None):
        sent.append(to)

    monkeypatch.setattr(notifications, "send_email", fake_send)
    result = await notifications.send_marketing_email(
        _transient_account(opt_out=True), "s", "<p>h</p>", "t"
    )
    assert result is False
    assert sent == []  # never dispatched


async def test_marketing_sends_with_unsubscribe_footer(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_send(to, subject, text, html=None):
        captured["text"] = text
        captured["html"] = html or ""

    monkeypatch.setattr(notifications, "send_email", fake_send)
    ok = await notifications.send_marketing_email(
        _transient_account(opt_out=False), "s", "<p>h</p>", "hello"
    )
    assert ok is True
    assert "unsubscribe" in captured["text"].lower()
    assert "/email/unsubscribe?token=" in captured["html"]


async def test_apply_unsubscribe_sets_flag(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        acc = Account(email="u@example.com", username="u")
        s.add(acc)
        await s.commit()
        acc_id = acc.id
    token = create_unsubscribe_token(acc_id)
    async with session_factory() as s:
        account = await notifications.apply_unsubscribe(s, token)
        assert account.email_opt_out is True


async def test_apply_unsubscribe_rejects_wrong_token_type(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # An access token must not double as an unsubscribe token.
    bad = create_access_token(UUID(int=9))
    async with session_factory() as s:
        with pytest.raises(AuthError):
            await notifications.apply_unsubscribe(s, bad)


async def test_marketing_recipients_excludes_unverified_and_opted_out(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        s.add(Account(email="ok@e.com", username="ok", email_verified_at=NOW))
        s.add(Account(email="unverified@e.com", username="unv", email_verified_at=None))
        s.add(
            Account(email="opted@e.com", username="opt", email_verified_at=NOW, email_opt_out=True)
        )
        await s.commit()
    async with session_factory() as s:
        recipients = await notifications.marketing_recipients(s)
        assert {r.username for r in recipients} == {"ok"}


async def test_unsubscribe_endpoint_flips_flag(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as s:
        acc = Account(email="u@example.com", username="u")
        s.add(acc)
        await s.commit()
        acc_id = acc.id
    token = create_unsubscribe_token(acc_id)
    resp = await client.get(f"/email/unsubscribe?token={token}")
    assert resp.status_code == 200
    async with session_factory() as s:
        acc = await s.get(Account, acc_id)
        assert acc.email_opt_out is True


async def test_unsubscribe_endpoint_bad_token_is_400(client: AsyncClient) -> None:
    resp = await client.get("/email/unsubscribe?token=not-a-real-token")
    assert resp.status_code == 400
