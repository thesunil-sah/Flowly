"""Social OAuth endpoints — start the redirect, handle the callback.

Both return browser redirects (not JSON): `start` sends the user to the
provider; `callback` finishes on the web app's /auth/callback, passing tokens
in the URL fragment (kept out of query strings/server logs) or an error.
"""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppError
from app.db.postgres import get_session
from app.db.redis import get_redis
from app.services import auth as auth_service
from app.services import oauth as oauth_service

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def _web_callback(fragment: dict[str, str]) -> RedirectResponse:
    return RedirectResponse(f"{settings.web_base_url}/auth/callback#{urlencode(fragment)}")


@router.get("/{provider}/start")
async def start(provider: str, redis: RedisDep) -> RedirectResponse:
    try:
        config = oauth_service.get_provider(provider)
        state = await oauth_service.create_state(redis, provider)
    except AppError as exc:
        return _web_callback({"error": exc.message})
    return RedirectResponse(oauth_service.build_authorize_url(config, state))


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    state: str,
    session: SessionDep,
    redis: RedisDep,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    try:
        if error or not code:
            raise oauth_service.OAuthError("Sign-in was cancelled.")
        config = oauth_service.get_provider(provider)
        await oauth_service.consume_state(redis, provider, state)
        profile = await oauth_service.fetch_profile(config, code)
        account = await auth_service.oauth_login(session, profile)
        tokens = auth_service.issue_tokens(account.id)
    except AppError as exc:
        return _web_callback({"error": exc.message})
    return _web_callback(
        {"access_token": tokens.access_token, "refresh_token": tokens.refresh_token}
    )
