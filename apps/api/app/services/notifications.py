"""Non-transactional (marketing) email — the opt-out gate + unsubscribe (§8).

Growth email (weekly digest, onboarding sequence) is *opt-out-able*; transactional
email (verify/reset codes) is not and never routes through here. Every send goes
via `send_marketing_email`, which:
  1. refuses to send to an opted-out account, and
  2. appends a one-click unsubscribe footer carrying a signed token.

`apply_unsubscribe` is the token's only effect: flip `account.email_opt_out`.
Keeping this gate in one place means no worker can accidentally email someone who
opted out.
"""

import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AuthError
from app.core.security import create_unsubscribe_token, decode_token
from app.models.tables import Account
from app.services.email import send_email

logger = logging.getLogger("flowly.notifications")


async def marketing_recipients(session: AsyncSession) -> Sequence[Account]:
    """Accounts eligible for growth email: verified and not opted out (§8).

    The opt-out is re-checked at send time too (`send_marketing_email`); filtering
    here just avoids building a digest we'd only throw away.
    """
    result = await session.scalars(
        select(Account).where(
            Account.email_verified_at.is_not(None),
            Account.email_opt_out.is_(False),
        )
    )
    return result.all()


def unsubscribe_url(account: Account) -> str:
    """The signed one-click unsubscribe link for this account's emails."""
    token = create_unsubscribe_token(account.id)
    return f"{settings.api_base_url}/email/unsubscribe?token={token}"


def _with_footer(html: str, text: str, unsub_url: str) -> tuple[str, str]:
    """Append the unsubscribe footer to both the HTML and text bodies (§8)."""
    html_footer = (
        '<hr style="margin-top:32px;border:none;border-top:1px solid #eee"/>'
        '<p style="color:#888;font-size:12px">'
        "You're receiving this because you have a Flowly account. "
        f'<a href="{unsub_url}">Unsubscribe from these emails</a>.'
        "</p>"
    )
    text_footer = f"\n\n---\nUnsubscribe from these emails: {unsub_url}"
    return html + html_footer, text + text_footer


async def send_marketing_email(account: Account, subject: str, html: str, text: str) -> bool:
    """Send a non-transactional email, honoring the account's opt-out (§8).

    Returns True if the email was dispatched, False if suppressed by opt-out.
    Delivery errors propagate; background callers wrap this best-effort so one
    bad send can't abort a batch.
    """
    if account.email_opt_out:
        logger.debug("marketing email suppressed (opted out): account=%s", account.id)
        return False
    html_body, text_body = _with_footer(html, text, unsubscribe_url(account))
    await send_email(account.email, subject, text_body, html_body)
    return True


async def apply_unsubscribe(session: AsyncSession, token: str) -> Account:
    """Opt the token's account out of non-transactional email. Idempotent.

    Raises AuthError on a missing/invalid/expired token or unknown account.
    """
    account_id = decode_token(token, "unsubscribe")
    account = await session.get(Account, account_id)
    if account is None:
        raise AuthError()
    account.email_opt_out = True
    await session.commit()
    return account
