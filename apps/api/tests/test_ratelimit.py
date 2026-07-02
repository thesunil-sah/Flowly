"""Login rate-limit test — 5 attempts / window, then 429 (D10)."""

from httpx import AsyncClient

from app.core.ratelimit import LOGIN_MAX_ATTEMPTS


async def test_login_rate_limited(client: AsyncClient) -> None:
    payload = {"identifier": "brute@example.com", "password": "wrong-password"}
    # The limiter runs before credential checks, so failed logins still count.
    for _ in range(LOGIN_MAX_ATTEMPTS):
        resp = await client.post("/auth/login", json=payload)
        assert resp.status_code == 401
    # One past the limit is blocked.
    blocked = await client.post("/auth/login", json=payload)
    assert blocked.status_code == 429
