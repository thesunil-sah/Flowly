"""OAuth account create/link logic (services.auth.oauth_login).

The provider HTTP layer isn't exercised here; these cover the security-critical
upsert: reuse identity, link by verified email, refuse unverified link, create.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import ConflictError
from app.core.security import hash_password
from app.models.tables import Account, Identity
from app.services.auth import oauth_login
from app.services.oauth import OAuthError, OAuthProfile


def _profile(**kw) -> OAuthProfile:
    base = dict(
        provider="google",
        provider_user_id="gid-1",
        email="alice@example.com",
        email_verified=True,
        username_hint="alice",
    )
    base.update(kw)
    return OAuthProfile(**base)


async def test_creates_new_account_and_identity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        account = await oauth_login(s, _profile())
        await s.commit()
        assert account.username == "alice"
        assert account.password_hash is None  # passwordless
        assert account.email_verified_at is not None  # provider-verified
        ident = await s.scalar(select(Identity).where(Identity.account_id == account.id))
        assert ident is not None and ident.provider == "google"


async def test_second_login_reuses_same_account(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        first = await oauth_login(s, _profile())
        await s.commit()
        first_id = first.id
    async with session_factory() as s:
        again = await oauth_login(s, _profile())
        await s.commit()
        assert again.id == first_id
        count = len((await s.scalars(select(Account))).all())
        assert count == 1


async def test_links_to_existing_account_when_email_verified(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        existing = Account(
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("pw-12345678"),
            email_verified_at=None,
            plan="pro",
            status="trialing",
        )
        s.add(existing)
        await s.commit()
        existing_id = existing.id
    async with session_factory() as s:
        linked = await oauth_login(s, _profile(username_hint="somethingelse"))
        await s.commit()
        assert linked.id == existing_id  # same account, now with a google identity
        ident = await s.scalar(select(Identity).where(Identity.account_id == existing_id))
        assert ident is not None


async def test_refuses_link_when_provider_email_unverified(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        s.add(
            Account(
                username="alice",
                email="alice@example.com",
                password_hash=hash_password("pw-12345678"),
                plan="pro",
                status="trialing",
            )
        )
        await s.commit()
    async with session_factory() as s:
        with pytest.raises(ConflictError):
            await oauth_login(s, _profile(email_verified=False))


async def test_no_email_from_provider_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        with pytest.raises(OAuthError):
            await oauth_login(s, _profile(email=None, email_verified=False))


async def test_username_collision_is_resolved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        s.add(
            Account(
                username="alice",
                email="taken@example.com",
                password_hash=hash_password("pw-12345678"),
                plan="pro",
                status="trialing",
            )
        )
        await s.commit()
    async with session_factory() as s:
        # New google user whose handle "alice" is taken -> gets a suffixed name.
        account = await oauth_login(s, _profile(email="alice2@example.com"))
        await s.commit()
        assert account.username != "alice"
        assert account.username.startswith("alice")
