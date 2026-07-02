"""Social OAuth (Google, GitHub) — authorization-code flow.

The API is the auth authority: it drives the redirect, exchanges the code,
normalizes the provider profile, and mints Flowly's own JWTs (in services/auth).
A random `state` (stored in Redis, short TTL) protects the callback from CSRF.
The provider HTTP layer lives here; account create/link logic lives in
services/auth.oauth_login.
"""

import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from redis.asyncio import Redis

from app.config import settings
from app.core.exceptions import AppError

STATE_TTL = 300  # seconds
_HTTP_TIMEOUT = 10.0


class OAuthError(AppError):
    status_code = 400
    message = "Social sign-in failed. Please try again."


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    authorize_url: str
    token_url: str
    scope: str
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class OAuthProfile:
    provider: str
    provider_user_id: str
    email: str | None
    email_verified: bool
    username_hint: str


def _providers() -> dict[str, ProviderConfig]:
    return {
        "google": ProviderConfig(
            name="google",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scope="openid email profile",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        ),
        "github": ProviderConfig(
            name="github",
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scope="read:user user:email",
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
        ),
    }


def get_provider(name: str) -> ProviderConfig:
    provider = _providers().get(name)
    if provider is None or not provider.client_id or not provider.client_secret:
        raise OAuthError("This sign-in provider is not available.")
    return provider


def callback_url(provider: str) -> str:
    return f"{settings.api_base_url}/auth/oauth/{provider}/callback"


async def create_state(redis: Redis, provider: str) -> str:
    state = secrets.token_urlsafe(24)
    await redis.set(f"oauth:state:{state}", provider, ex=STATE_TTL)
    return state


async def consume_state(redis: Redis, provider: str, state: str) -> None:
    key = f"oauth:state:{state}"
    stored = await redis.get(key)
    if stored != provider:
        raise OAuthError("Invalid or expired sign-in state.")
    await redis.delete(key)


def build_authorize_url(provider: ProviderConfig, state: str) -> str:
    params = {
        "client_id": provider.client_id,
        "redirect_uri": callback_url(provider.name),
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
    }
    if provider.name == "google":
        params["access_type"] = "online"
        params["prompt"] = "select_account"
    return f"{provider.authorize_url}?{urlencode(params)}"


async def _exchange_code(provider: ProviderConfig, code: str) -> str:
    data = {
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
        "code": code,
        "redirect_uri": callback_url(provider.name),
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            provider.token_url, data=data, headers={"Accept": "application/json"}
        )
    if resp.status_code != 200:
        raise OAuthError()
    token = resp.json().get("access_token")
    if not token:
        raise OAuthError()
    return token


async def _google_profile(token: str) -> OAuthProfile:
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code != 200:
        raise OAuthError()
    d = resp.json()
    email = d.get("email")
    return OAuthProfile(
        provider="google",
        provider_user_id=str(d["sub"]),
        email=email or None,
        email_verified=bool(d.get("email_verified")),
        username_hint=(email or d.get("name") or "user").split("@")[0],
    )


async def _github_profile(token: str) -> OAuthProfile:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        user_resp = await client.get("https://api.github.com/user", headers=headers)
        emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
    if user_resp.status_code != 200:
        raise OAuthError()
    user = user_resp.json()

    email: str | None = None
    verified = False
    if emails_resp.status_code == 200:
        emails = emails_resp.json()
        primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
        any_verified = next((e for e in emails if e.get("verified")), None)
        chosen = primary or any_verified
        if chosen:
            email, verified = chosen["email"], True

    return OAuthProfile(
        provider="github",
        provider_user_id=str(user["id"]),
        email=email,
        email_verified=verified,
        username_hint=user.get("login") or "user",
    )


async def fetch_profile(provider: ProviderConfig, code: str) -> OAuthProfile:
    token = await _exchange_code(provider, code)
    if provider.name == "google":
        return await _google_profile(token)
    return await _github_profile(token)
