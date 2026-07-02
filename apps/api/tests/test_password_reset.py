"""Forgot-password → verify code → reset → login-with-new-password flow."""

from httpx import AsyncClient

USERNAME = "carol"
EMAIL = "carol@example.com"
PASSWORD = "orig-password-1"
NEW_PASSWORD = "brand-new-pass-2"


async def _signup_and_verify(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/signup", json={"username": USERNAME, "email": EMAIL, "password": PASSWORD}
    )
    await client.post("/auth/verify-email", json={"email": EMAIL, "code": resp.json()["dev_code"]})


async def test_full_reset_flow(client: AsyncClient) -> None:
    await _signup_and_verify(client)

    forgot = await client.post("/auth/forgot-password", json={"email": EMAIL})
    assert forgot.status_code == 200
    code = forgot.json()["dev_code"]
    assert code and len(code) == 6

    verified = await client.post("/auth/verify-reset-code", json={"email": EMAIL, "code": code})
    assert verified.status_code == 200
    reset_token = verified.json()["reset_token"]

    done = await client.post(
        "/auth/reset-password", json={"reset_token": reset_token, "password": NEW_PASSWORD}
    )
    assert done.status_code == 200

    # Old password no longer works; new one does.
    old = await client.post("/auth/login", json={"identifier": EMAIL, "password": PASSWORD})
    assert old.status_code == 401
    new = await client.post("/auth/login", json={"identifier": EMAIL, "password": NEW_PASSWORD})
    assert new.status_code == 200


async def test_forgot_password_unknown_email_is_generic(client: AsyncClient) -> None:
    # No account: still 200, no dev_code (nothing sent) — no enumeration.
    resp = await client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    assert resp.json()["dev_code"] is None


async def test_reset_password_bad_token_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/reset-password", json={"reset_token": "not-a-token", "password": NEW_PASSWORD}
    )
    assert resp.status_code == 401


async def test_wrong_reset_code_rejected(client: AsyncClient) -> None:
    await _signup_and_verify(client)
    await client.post("/auth/forgot-password", json={"email": EMAIL})
    bad = await client.post("/auth/verify-reset-code", json={"email": EMAIL, "code": "000000"})
    assert bad.status_code in (401, 429)
