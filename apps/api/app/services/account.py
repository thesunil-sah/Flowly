"""Account self-service settings: password, email, preferences, deletion.

The settings surface (Phase F3). Like the rest of the auth layer this holds no
HTTP objects — it takes the session/redis/ClickHouse client from the router and
raises typed AppErrors. Every function operates on the *authenticated* account
(passed in from `require_user`), so there is no cross-account path here: an
account can only ever change or delete itself.
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from clickhouse_connect.driver import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ConflictError, ValidationError
from app.core.security import hash_password, verify_password
from app.models.tables import (
    Account,
    Identity,
    OnboardingEmail,
    ShareToken,
    Site,
    Subscription,
)
from app.services import billing, verification
from app.services.retention import delete_all_for_site

logger = logging.getLogger("flowly.account")

# Distinct Redis purpose for the change-email code so it can't be crossed with
# signup ("verify") or reset codes; needs a matching CODE_MESSAGES entry (email.py).
_EMAIL_CHANGE_PURPOSE = "email_change"


def _reauth(account: Account, password: str | None) -> None:
    """Re-authenticate a sensitive change with the current password.

    OAuth-only accounts have no password_hash — the bearer token is the only
    credential they have, so it stands alone. Password accounts must confirm.
    """
    if account.password_hash is None:
        return
    if not password or not verify_password(password, account.password_hash):
        raise AuthError("Incorrect password.")


async def change_password(
    session: AsyncSession, account: Account, current_password: str, new_password: str
) -> None:
    """Set a new password after verifying the current one."""
    if account.password_hash is None:
        # No password to change — the account authenticates via a linked provider.
        raise ValidationError("This account has no password. Sign in with your linked provider.")
    if not verify_password(current_password, account.password_hash):
        raise AuthError("Incorrect password.")
    account.password_hash = hash_password(new_password)


async def _email_taken(session: AsyncSession, email: str, exclude_id: object) -> bool:
    """Is `email` owned by a *different* account? (race-safe check for changes)."""
    other = await session.scalar(select(Account).where(Account.email == email))
    return other is not None and other.id != exclude_id


async def request_email_change(
    session: AsyncSession, redis: Redis, account: Account, new_email: str, password: str | None
) -> str:
    """Step 1: confirm identity + target, email a code to the NEW address.

    The code goes to the new address so completing the flow proves control of it
    (we never set an email the user can't receive at). Returns the code for
    local-dev surfacing. Raises if the address is unchanged or already taken.
    """
    if new_email == account.email:
        raise ValidationError("That is already your email address.")
    _reauth(account, password)
    if await _email_taken(session, new_email, account.id):
        raise ConflictError("An account with this email already exists.")
    return await verification.issue_code(redis, _EMAIL_CHANGE_PURPOSE, new_email)


async def verify_email_change(
    session: AsyncSession, redis: Redis, account: Account, new_email: str, code: str
) -> Account:
    """Step 2: verify the emailed code, then switch the account's email.

    Re-checks uniqueness (a clash could have appeared since step 1) and flushes
    so a raced duplicate surfaces as a clean 409, not a 500 at commit.
    """
    if new_email == account.email:
        raise ValidationError("That is already your email address.")
    if await _email_taken(session, new_email, account.id):
        raise ConflictError("An account with this email already exists.")
    await verification.verify_code(redis, _EMAIL_CHANGE_PURPOSE, new_email, code)

    account.email = new_email
    # The new address is now proven; keep the account verified.
    account.email_verified_at = datetime.now(UTC)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("An account with this email already exists.") from exc
    return account


async def set_email_preferences(
    session: AsyncSession, account: Account, email_opt_out: bool
) -> Account:
    """Toggle the marketing-email opt-out flag (the in-dashboard mirror of the
    signed unsubscribe link — same column, no token needed since we're authed)."""
    account.email_opt_out = email_opt_out
    return account


async def list_identities(session: AsyncSession, account_id: object) -> Sequence[Identity]:
    """The account's linked social logins, oldest first."""
    result = await session.scalars(
        select(Identity).where(Identity.account_id == account_id).order_by(Identity.created_at)
    )
    return result.all()


async def delete_account(
    session: AsyncSession,
    redis: Redis,
    ch_client: AsyncClient,
    account: Account,
    password: str | None,
) -> None:
    """Irreversibly delete the account: analytics events, then all Postgres rows.

    Re-authenticated with the password (skipped for OAuth-only accounts). Each
    site's ClickHouse events are erased via the retention machinery and its
    Redis site->account map is dropped — both best-effort, so a storage hiccup
    can't strand the account half-deleted; the Postgres rows (the source of
    identity + login) always go. Children are removed before the account to
    respect the FKs (none declare ON DELETE CASCADE).
    """
    _reauth(account, password)

    sites = (await session.scalars(select(Site).where(Site.account_id == account.id))).all()
    site_pks = [site.id for site in sites]

    for site in sites:
        try:
            await delete_all_for_site(ch_client, site.site_id)
        except Exception:
            logger.warning("event wipe failed for site %s during account delete", site.site_id)
        try:
            await billing.uncache_site_account(redis, site.site_id)
        except Exception:
            logger.debug("site->account uncache failed for %s", site.site_id, exc_info=True)

    # Delete children first (FK order): share tokens -> sites, then account-owned rows.
    if site_pks:
        await session.execute(delete(ShareToken).where(ShareToken.site_id.in_(site_pks)))
    await session.execute(delete(Site).where(Site.account_id == account.id))
    await session.execute(delete(Identity).where(Identity.account_id == account.id))
    await session.execute(delete(Subscription).where(Subscription.account_id == account.id))
    await session.execute(delete(OnboardingEmail).where(OnboardingEmail.account_id == account.id))
    await session.delete(account)
