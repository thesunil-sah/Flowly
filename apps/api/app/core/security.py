"""Security primitives: password hashing, JWT issue/verify, and `require_user`.

This is the auth surface (CLAUDE.md §9). Passwords are argon2-hashed; tokens are
short-lived signed JWTs; every authed route depends on `require_user`, which
resolves a verified token to exactly one account (tenant scope). Never log
passwords, hashes, or tokens.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerifyMismatchError
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AuthError
from app.db.postgres import get_session
from app.models.tables import Account

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh", "reset"]

# Short-lived token minted after a password-reset code is verified; it authorizes
# exactly one password change.
RESET_TOKEN_TTL = 600  # 10 minutes

# auto_error=False so a missing/blank header raises our uniform AuthError (401)
# instead of FastAPI's default 403.
_bearer = HTTPBearer(auto_error=False)


# --- Passwords ------------------------------------------------------------
def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain)
    except (VerifyMismatchError, Argon2Error):
        return False


# --- Tokens ---------------------------------------------------------------
def _create_token(account_id: UUID, token_type: TokenType, ttl_seconds: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(account_id),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(account_id: UUID) -> str:
    return _create_token(account_id, "access", settings.access_token_ttl)


def create_refresh_token(account_id: UUID) -> str:
    return _create_token(account_id, "refresh", settings.refresh_token_ttl)


def create_reset_token(account_id: UUID) -> str:
    return _create_token(account_id, "reset", RESET_TOKEN_TTL)


def decode_token(token: str, expected_type: TokenType) -> UUID:
    """Verify signature + expiry AND the token type; return the account id.

    Rejects an access token used where a refresh is expected (and vice-versa).
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthError() from exc

    if payload.get("type") != expected_type:
        raise AuthError()
    sub = payload.get("sub")
    if not sub:
        raise AuthError()
    try:
        return UUID(sub)
    except (ValueError, TypeError) as exc:
        raise AuthError() from exc


# --- Dependency -----------------------------------------------------------
async def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    """Resolve a valid access token to its Account (the tenant scope).

    Missing/invalid/expired token or unknown account -> 401.
    """
    if credentials is None or not credentials.credentials:
        raise AuthError()
    account_id = decode_token(credentials.credentials, "access")
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise AuthError()
    return account


CurrentUser = Annotated[Account, Depends(require_user)]
