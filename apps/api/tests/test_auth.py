"""Signup → verify → login → refresh → /me flow (CLAUDE.md §8).

ENVIRONMENT defaults to "local", so signup/forgot responses carry `dev_code`,
which the tests use to complete the code steps.
"""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.tables import Account

USERNAME = "alice"
EMAIL = "alice@example.com"
PASSWORD = "s3cret-password"


async def _signup(client: AsyncClient, *, username=USERNAME, email=EMAIL, password=PASSWORD):
    return await client.post(
        "/auth/signup", json={"username": username, "email": email, "password": password}
    )


async def _verify(client: AsyncClient, email: str, code: str):
    return await client.post("/auth/verify-email", json={"email": email, "code": code})


async def _signup_and_verify(client: AsyncClient, **kw):
    resp = await _signup(client, **kw)
    code = resp.json()["dev_code"]
    email = kw.get("email", EMAIL)
    await _verify(client, email, code)
    return resp


async def test_signup_creates_unverified_account_with_hash(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    resp = await _signup(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "verification_sent"
    assert body["dev_code"] and len(body["dev_code"]) == 6

    async with session_factory() as s:
        account = await s.scalar(select(Account).where(Account.email == EMAIL))
    assert account is not None
    assert account.username == USERNAME
    assert account.email_verified_at is None  # unverified until code entered
    assert account.password_hash.startswith("$argon2")
    assert PASSWORD not in account.password_hash


async def test_login_blocked_until_verified(client: AsyncClient) -> None:
    await _signup(client)
    blocked = await client.post("/auth/login", json={"identifier": EMAIL, "password": PASSWORD})
    assert blocked.status_code == 403  # EmailNotVerifiedError


async def test_verify_then_login_with_email_or_username(client: AsyncClient) -> None:
    await _signup_and_verify(client)

    by_email = await client.post("/auth/login", json={"identifier": EMAIL, "password": PASSWORD})
    assert by_email.status_code == 200
    assert by_email.json()["access_token"]

    by_username = await client.post(
        "/auth/login", json={"identifier": USERNAME, "password": PASSWORD}
    )
    assert by_username.status_code == 200


async def test_wrong_verification_code_rejected(client: AsyncClient) -> None:
    await _signup(client)
    bad = await _verify(client, EMAIL, "000000")
    # 401 (bad code) or 429 (attempts exhausted) — never a success.
    assert bad.status_code in (401, 429)


async def test_duplicate_email_and_username_conflict(client: AsyncClient) -> None:
    await _signup(client)
    dup_email = await _signup(client, username="bob")
    assert dup_email.status_code == 409
    dup_username = await _signup(client, email="bob@example.com")
    assert dup_username.status_code == 409


async def test_email_case_insensitive(client: AsyncClient) -> None:
    await _signup(client, email="Alice@Example.com")
    dup = await _signup(client, username="alice2", email="  alice@example.COM ")
    assert dup.status_code == 409


async def test_login_wrong_password_and_unknown_identifier_identical(client: AsyncClient) -> None:
    await _signup_and_verify(client)
    wrong = await client.post("/auth/login", json={"identifier": EMAIL, "password": "nope-nope1"})
    unknown = await client.post(
        "/auth/login", json={"identifier": "ghost", "password": "whatever1"}
    )
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_refresh_and_me(client: AsyncClient) -> None:
    await _signup_and_verify(client)
    tokens = (
        await client.post("/auth/login", json={"identifier": EMAIL, "password": PASSWORD})
    ).json()

    r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL
    assert me.json()["username"] == USERNAME

    assert (await client.get("/auth/me")).status_code == 401


async def test_signup_validation(client: AsyncClient) -> None:
    # short password
    assert (await _signup(client, password="short")).status_code == 422
    # bad username (non-alphanumeric)
    assert (await _signup(client, username="a b!")).status_code == 422
    # too-long password
    assert (await _signup(client, password="x" * 129)).status_code == 422
