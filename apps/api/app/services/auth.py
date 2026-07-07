"""Auth business logic: signup, email verification, login, password reset.

Depends on the session/redis passed from the router and on core/security;
contains no HTTP objects (CLAUDE.md §3/§4). Raises typed AppErrors; the
router/handlers map them to HTTP.
"""

import re
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AuthError, ConflictError, EmailNotVerifiedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.schemas import TokenResponse
from app.models.tables import Account, Identity
from app.services import verification
from app.services.oauth import OAuthError, OAuthProfile

# A fixed dummy hash so login runs an argon2 verify even when the identifier is
# unknown — equalizing timing so we don't leak which accounts exist.
_DUMMY_HASH = hash_password("dummy-password-for-timing-parity")


def issue_tokens(account_id: UUID) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(account_id),
        refresh_token=create_refresh_token(account_id),
        expires_in=settings.access_token_ttl,
    )


async def _get_by_email(session: AsyncSession, email: str) -> Account | None:
    return await session.scalar(select(Account).where(Account.email == email))


async def _find_signup_clash(session: AsyncSession, email: str, username: str) -> Account | None:
    return await session.scalar(
        select(Account).where(or_(Account.email == email, Account.username == username))
    )


async def signup(
    session: AsyncSession, redis: Redis, username: str, email: str, password: str
) -> str:
    """Create an unverified account and email a verification code.

    Returns the code (for local-dev surfacing). Raises ConflictError if the
    email or username is taken.
    """
    clash = await _find_signup_clash(session, email, username)
    if clash is not None:
        if clash.email == email:
            raise ConflictError("An account with this email already exists.")
        raise ConflictError("That username is already taken.")

    account = Account(
        username=username,
        email=email,
        password_hash=hash_password(password),
        email_verified_at=None,
        # Phase 14: accounts start free — the 7-day trial now begins at upgrade
        # (Checkout), once per account, not at signup.
        plan="free",
        status="free",
        trial_ends_at=None,
    )
    session.add(account)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Lost the race with a concurrent signup that passed the pre-check too:
        # the DB unique constraint is the real arbiter. Surface a clean 409
        # instead of letting the IntegrityError bubble up as a 500.
        raise ConflictError("An account with this email or username already exists.") from exc
    return await verification.issue_code(redis, "verify", email)


async def resend_verification(session: AsyncSession, redis: Redis, email: str) -> str | None:
    """Re-issue a verification code if the account exists and is unverified.

    Returns the code (local-dev surfacing) or None. Silent about which case
    applied (no account enumeration at the router).
    """
    account = await _get_by_email(session, email)
    if account is not None and account.email_verified_at is None:
        return await verification.issue_code(redis, "verify", email)
    return None


async def verify_email(session: AsyncSession, redis: Redis, email: str, code: str) -> None:
    """Confirm the code and mark the email verified."""
    account = await _get_by_email(session, email)
    if account is None:
        raise AuthError("Invalid code.")  # uniform with a bad code
    await verification.verify_code(redis, "verify", email, code)
    if account.email_verified_at is None:
        account.email_verified_at = datetime.now(UTC)


async def login(session: AsyncSession, identifier: str, password: str) -> Account:
    """Verify credentials by email OR username. Unknown identifier and wrong
    password both raise AuthError; an unverified account raises 403."""
    account = await session.scalar(
        select(Account).where(or_(Account.email == identifier, Account.username == identifier))
    )
    # OAuth-only accounts have no password_hash — verify against a dummy so the
    # attempt fails without leaking that the account exists (or is passwordless).
    password_hash = account.password_hash if (account and account.password_hash) else _DUMMY_HASH
    valid = verify_password(password, password_hash)
    if account is None or account.password_hash is None or not valid:
        raise AuthError()
    if account.email_verified_at is None:
        raise EmailNotVerifiedError()
    return account


async def _unique_username(session: AsyncSession, hint: str) -> str:
    base = re.sub(r"[^a-z0-9_]", "", hint.lower())[:32] or "user"
    if len(base) < 3:
        base = f"{base}user"[:32]
    candidate, i = base, 0
    while await session.scalar(select(Account.id).where(Account.username == candidate)) is not None:
        i += 1
        suffix = str(i)
        candidate = base[: 32 - len(suffix)] + suffix
    return candidate


async def oauth_login(session: AsyncSession, profile: OAuthProfile) -> Account:
    """Resolve a social profile to an account: reuse a linked identity, link to
    an existing account by verified email, or create a new one."""
    identity = await session.scalar(
        select(Identity).where(
            Identity.provider == profile.provider,
            Identity.provider_user_id == profile.provider_user_id,
        )
    )
    if identity is not None:
        account = await session.get(Account, identity.account_id)
        if account is None:  # pragma: no cover - referential integrity
            raise AuthError()
        return account

    existing = await _get_by_email(session, profile.email) if profile.email else None
    if existing is not None:
        # Link only when the provider vouches the email, else it's a takeover risk.
        if not profile.email_verified:
            raise ConflictError(
                "This email is already registered. Sign in with your password to link it."
            )
        session.add(
            Identity(
                account_id=existing.id,
                provider=profile.provider,
                provider_user_id=profile.provider_user_id,
            )
        )
        return existing

    if not profile.email:
        raise OAuthError("Your provider did not share an email address.")

    account = Account(
        username=await _unique_username(session, profile.username_hint),
        email=profile.email,
        password_hash=None,
        email_verified_at=datetime.now(UTC) if profile.email_verified else None,
        # Phase 14: start free; the trial begins at upgrade, not signup.
        plan="free",
        status="free",
        trial_ends_at=None,
    )
    session.add(account)
    await session.flush()
    session.add(
        Identity(
            account_id=account.id,
            provider=profile.provider,
            provider_user_id=profile.provider_user_id,
        )
    )
    return account


async def forgot_password(session: AsyncSession, redis: Redis, email: str) -> str | None:
    """Email a reset code if the account exists (silent otherwise).

    Returns the code (local-dev surfacing) or None.
    """
    account = await _get_by_email(session, email)
    if account is not None:
        return await verification.issue_code(redis, "reset", email)
    return None


async def verify_reset_code(session: AsyncSession, redis: Redis, email: str, code: str) -> str:
    """Confirm a reset code and mint a short-lived reset token."""
    account = await _get_by_email(session, email)
    if account is None:
        raise AuthError("Invalid code.")
    await verification.verify_code(redis, "reset", email, code)
    return create_reset_token(account.id)


async def reset_password(session: AsyncSession, reset_token: str, new_password: str) -> None:
    """Set a new password given a valid reset token."""
    account_id = decode_token(reset_token, "reset")
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None:
        raise AuthError()
    account.password_hash = hash_password(new_password)
    # Completing a reset proves control of the mailbox; verify if not already.
    if account.email_verified_at is None:
        account.email_verified_at = datetime.now(UTC)


async def refresh(refresh_token: str) -> TokenResponse:
    """Rotate tokens from a valid refresh token (new access + new refresh)."""
    account_id = decode_token(refresh_token, "refresh")
    return issue_tokens(account_id)
