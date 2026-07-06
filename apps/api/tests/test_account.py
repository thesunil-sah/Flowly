"""/account — self-service settings (password, email, preferences, delete, F3).

Covers the unforgiving paths: auth is required everywhere, sensitive changes
re-check the password, an email change goes through code verification, and
account deletion wipes both Postgres rows and the site's ClickHouse events.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token, hash_password
from app.db.clickhouse import get_clickhouse
from app.main import app
from app.models.tables import Account, Identity, ShareToken, Site

PASSWORD = "correct-horse-battery"


class MockClickHouse:
    """ClickHouse double recording DDL/mutation commands (delete path)."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, dict[str, Any]]] = []

    async def command(self, sql: str, parameters: dict[str, Any] | None = None) -> None:
        self.commands.append((sql, parameters or {}))


def _install_clickhouse() -> MockClickHouse:
    ch = MockClickHouse()
    app.dependency_overrides[get_clickhouse] = lambda: ch
    return ch


async def _seed_password_account(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str = "user@example.com",
    with_site: bool = False,
) -> UUID:
    async with session_factory() as s:
        acct = Account(
            email=email,
            username="user",
            password_hash=hash_password(PASSWORD),
            email_verified_at=datetime.now(UTC),
        )
        s.add(acct)
        await s.flush()
        acct_id = acct.id
        if with_site:
            s.add(Site(account_id=acct_id, site_id="site-abc", domain="a.com"))
        await s.commit()
    return acct_id


def _auth(account_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(account_id)}"}


# --- auth guard -----------------------------------------------------------
async def test_account_routes_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/account/identities")).status_code == 401
    assert (
        await client.put("/account/email-preferences", json={"email_opt_out": True})
    ).status_code == 401
    assert (
        await client.post(
            "/account/change-password",
            json={"current_password": "x", "new_password": "yyyyyyyy"},
        )
    ).status_code == 401
    assert (await client.post("/account/delete", json={"password": PASSWORD})).status_code == 401


# --- change password ------------------------------------------------------
async def test_change_password_wrong_current_is_401(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory)
    resp = await client.post(
        "/account/change-password",
        json={"current_password": "wrong-password", "new_password": "brand-new-pass"},
        headers=_auth(acct_id),
    )
    assert resp.status_code == 401


async def test_change_password_success_then_login_with_new(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory)
    resp = await client.post(
        "/account/change-password",
        json={"current_password": PASSWORD, "new_password": "a-fresh-password"},
        headers=_auth(acct_id),
    )
    assert resp.status_code == 204
    # Old password no longer logs in; new one does.
    old = await client.post(
        "/auth/login", json={"identifier": "user@example.com", "password": PASSWORD}
    )
    assert old.status_code == 401
    new = await client.post(
        "/auth/login", json={"identifier": "user@example.com", "password": "a-fresh-password"}
    )
    assert new.status_code == 200


async def test_change_password_on_oauth_only_account_is_422(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as s:
        acct = Account(
            email="oauth@example.com",
            username="oauthuser",
            password_hash=None,
            email_verified_at=datetime.now(UTC),
        )
        s.add(acct)
        await s.flush()
        acct_id = acct.id
        await s.commit()
    resp = await client.post(
        "/account/change-password",
        json={"current_password": "anything", "new_password": "some-new-pass"},
        headers=_auth(acct_id),
    )
    assert resp.status_code == 422


# --- email preferences ----------------------------------------------------
async def test_email_preferences_toggle_reflected_in_me(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory)
    resp = await client.put(
        "/account/email-preferences", json={"email_opt_out": True}, headers=_auth(acct_id)
    )
    assert resp.status_code == 200
    assert resp.json()["email_opt_out"] is True
    me = await client.get("/auth/me", headers=_auth(acct_id))
    assert me.json()["email_opt_out"] is True
    assert me.json()["has_password"] is True


# --- change email ---------------------------------------------------------
async def test_change_email_wrong_password_is_401(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory)
    resp = await client.post(
        "/account/change-email",
        json={"new_email": "new@example.com", "password": "nope"},
        headers=_auth(acct_id),
    )
    assert resp.status_code == 401


async def test_change_email_full_flow_updates_email(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory)
    start = await client.post(
        "/account/change-email",
        json={"new_email": "New@Example.com", "password": PASSWORD},
        headers=_auth(acct_id),
    )
    assert start.status_code == 200
    code = start.json()["dev_code"]  # local dev surfaces the code
    assert code is not None
    done = await client.post(
        "/account/verify-email-change",
        json={"new_email": "new@example.com", "code": code},
        headers=_auth(acct_id),
    )
    assert done.status_code == 200
    assert done.json()["email"] == "new@example.com"


async def test_change_email_to_taken_address_is_409(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory)
    async with session_factory() as s:
        s.add(Account(email="taken@example.com", username="taken"))
        await s.commit()
    resp = await client.post(
        "/account/change-email",
        json={"new_email": "taken@example.com", "password": PASSWORD},
        headers=_auth(acct_id),
    )
    assert resp.status_code == 409


# --- identities -----------------------------------------------------------
async def test_list_identities_returns_linked_providers(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory)
    async with session_factory() as s:
        s.add(Identity(account_id=acct_id, provider="google", provider_user_id="g-123"))
        await s.commit()
    resp = await client.get("/account/identities", headers=_auth(acct_id))
    assert resp.status_code == 200
    body = resp.json()
    assert [row["provider"] for row in body] == ["google"]
    assert "provider_user_id" not in body[0]  # never exposed


# --- delete account -------------------------------------------------------
async def test_delete_account_wrong_password_is_401(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory)
    _install_clickhouse()
    resp = await client.post("/account/delete", json={"password": "wrong"}, headers=_auth(acct_id))
    assert resp.status_code == 401


async def test_delete_account_wipes_postgres_and_clickhouse(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    acct_id = await _seed_password_account(session_factory, with_site=True)
    # A share token hangs off the site — it must be removed before the site (FK).
    async with session_factory() as s:
        site = await s.scalar(select(Site).where(Site.account_id == acct_id))
        assert site is not None
        s.add(ShareToken(token="share-xyz", site_id=site.id))
        s.add(Identity(account_id=acct_id, provider="github", provider_user_id="gh-1"))
        await s.commit()

    ch = _install_clickhouse()
    resp = await client.post("/account/delete", json={"password": PASSWORD}, headers=_auth(acct_id))
    assert resp.status_code == 204

    # The site's events were wiped, site-scoped (§9).
    assert any("ALTER TABLE events DELETE" in sql for sql, _ in ch.commands)
    assert any(params.get("site_id") == "site-abc" for _, params in ch.commands)

    # Postgres rows are gone: account, its sites, its identities.
    async with session_factory() as s:
        assert await s.scalar(select(Account).where(Account.id == acct_id)) is None
        assert (await s.scalars(select(Site).where(Site.account_id == acct_id))).first() is None
        assert (
            await s.scalars(select(Identity).where(Identity.account_id == acct_id))
        ).first() is None

    # The stale access token no longer resolves to an account.
    assert (await client.get("/auth/me", headers=_auth(acct_id))).status_code == 401


async def test_delete_oauth_only_account_needs_no_password(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as s:
        acct = Account(
            email="oauthdel@example.com",
            username="oauthdel",
            password_hash=None,
            email_verified_at=datetime.now(UTC),
        )
        s.add(acct)
        await s.flush()
        acct_id = acct.id
        await s.commit()
    _install_clickhouse()
    resp = await client.post("/account/delete", json={}, headers=_auth(acct_id))
    assert resp.status_code == 204
    async with session_factory() as s:
        assert await s.scalar(select(Account).where(Account.id == acct_id)) is None
