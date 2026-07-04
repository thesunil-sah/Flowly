"""Onboarding sequence worker — one pass, then exit (cron-triggered, §8).

Run hourly:
    uv run python -m app.workers.onboarding

For each verified, non-opted-out account it advances the sequence:
  - `welcome` — once, on the first pass after verification.
  - `live`    — once the first event lands on any of the account's sites.
  - `install` — a nudge if still not collecting `INSTALL_NUDGE_HOURS` after signup
                (and marked handled without emailing if the account is already
                live, so a late nudge never goes out).
Every step is idempotent via the `onboarding_emails` ledger; a failed send is
logged and retried next hour (the ledger row is only written after a send).
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from clickhouse_connect.driver import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.clickhouse import close_clickhouse, get_clickhouse
from app.db.postgres import async_session_factory, dispose_engine
from app.db.redis import close_redis, get_client
from app.models.tables import Account
from app.services import notifications, onboarding, sites

logger = logging.getLogger("flowly.onboarding")


async def _send_step(
    session: AsyncSession, account: Account, step: str, rendered: tuple[str, str, str]
) -> bool:
    """Send one sequence step through the marketing gate, then ledger it.

    Returns True if recorded (sent or suppressed-by-opt-out). Only a delivery
    error returns False (so the step retries next run, unrecorded).
    """
    if await onboarding.already_sent(session, account.id, step):
        return True
    subject, html, text = rendered
    try:
        await notifications.send_marketing_email(account, subject, html, text)
    except Exception:
        logger.exception("onboarding %s send failed for account %s", step, account.id)
        return False
    return await onboarding.record_step(session, account.id, step)


async def _advance_account(
    session: AsyncSession, redis: Redis, ch: AsyncClient, account: Account, now: datetime
) -> None:
    owned = await sites.list_account_sites(session, account.id)
    connected = False
    for site in owned:
        if await sites.first_event_seen(redis, ch, site.site_id):
            connected = True
            break

    # welcome — always the first email.
    await _send_step(session, account, onboarding.STEP_WELCOME, onboarding.render_welcome(account))

    # live — the moment the first event lands anywhere.
    if connected and not await onboarding.already_sent(session, account.id, onboarding.STEP_LIVE):
        domain = onboarding.install_cta_domain(owned) or ""
        await _send_step(
            session, account, onboarding.STEP_LIVE, onboarding.render_live(account, domain)
        )

    # install — nudge only if still dark after the delay; if already live, mark
    # it handled without emailing so a late nudge can never go out.
    if not await onboarding.already_sent(session, account.id, onboarding.STEP_INSTALL):
        # created_at is a UTC timestamptz; coerce a naive read to UTC so the age
        # comparison never raises on mixed awareness (§4).
        created = account.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if connected:
            await onboarding.record_step(session, account.id, onboarding.STEP_INSTALL)
        elif now - created >= timedelta(hours=onboarding.INSTALL_NUDGE_HOURS):
            await _send_step(
                session, account, onboarding.STEP_INSTALL, onboarding.render_install(account)
            )


async def run(now: datetime | None = None) -> None:
    """Advance the onboarding sequence for every eligible account."""
    now = now or datetime.now(UTC)
    ch = await get_clickhouse()
    redis = get_client()
    async with async_session_factory() as session:
        accounts = await notifications.marketing_recipients(session)
        for account in accounts:
            try:
                await _advance_account(session, redis, ch, account, now)
            except Exception:
                logger.exception("onboarding pass failed for account %s", account.id)
    logger.info("onboarding run complete; %s accounts checked", len(accounts))


async def _main() -> None:
    try:
        await run()
    finally:
        await close_clickhouse()
        await close_redis()
        await dispose_engine()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())


if __name__ == "__main__":
    main()
