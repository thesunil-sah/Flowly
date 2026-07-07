"""Weekly digest worker — one pass, then exit (cron-triggered, §8, Phase 8).

Run weekly (e.g. Monday 08:00 UTC) with:
    uv run python -m app.workers.digest

For each verified, non-opted-out account it builds a trailing-week digest across
that account's sites (reusing `services/digest.py`), sends it via the marketing
gate (which appends the unsubscribe footer), and records a per-ISO-week Redis
marker so a re-run in the same week can't double-send. Sites/accounts with no
traffic are skipped. A failed send for one account is logged and never aborts the
rest of the run.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis

from app.db.clickhouse import close_clickhouse, get_clickhouse
from app.db.postgres import async_session_factory, dispose_engine
from app.db.redis import close_redis, get_client
from app.services import billing, digest, notifications, sites

logger = logging.getLogger("flowly.digest")

# Marker TTL comfortably longer than a week so the current week's send is never
# re-fired, while old markers self-clean.
_MARKER_TTL_SECONDS = 10 * 24 * 3600


def _marker_key(account_id: UUID, now: datetime) -> str:
    """Per-account, per-ISO-week idempotency key (`digest:{id}:{YYYYWW}`)."""
    iso = now.isocalendar()
    return f"digest:{account_id}:{iso.year}{iso.week:02d}"


async def _already_sent(redis: Redis, account_id: UUID, now: datetime) -> bool:
    return await redis.exists(_marker_key(account_id, now)) > 0


async def _mark_sent(redis: Redis, account_id: UUID, now: datetime) -> None:
    await redis.set(_marker_key(account_id, now), "1", ex=_MARKER_TTL_SECONDS)


async def run(now: datetime | None = None) -> int:
    """Send this week's digests. Returns the number of accounts emailed."""
    now = now or datetime.now(UTC)
    ch = await get_clickhouse()
    redis = get_client()
    sent = 0
    async with async_session_factory() as session:
        accounts = await notifications.marketing_recipients(session)
        for account in accounts:
            if await _already_sent(redis, account.id, now):
                continue
            # A locked (over-limit free) account's digest follows the paywall —
            # the digest reads the same gated data, so skip it (Phase 14, §9).
            used = await billing.get_usage(redis, account.id, now)
            if billing.is_locked(account, used, now):
                continue
            owned = await sites.list_account_sites(session, account.id)
            if not owned:
                continue
            digests = [await digest.build_site_digest(ch, s.site_id, s.domain, now) for s in owned]
            if not any(d.has_traffic for d in digests):
                continue
            subject, html, text = digest.render_digest(account.username, digests, now)
            try:
                delivered = await notifications.send_marketing_email(account, subject, html, text)
            except Exception:
                logger.exception("digest send failed for account %s", account.id)
                continue
            if delivered:
                await _mark_sent(redis, account.id, now)
                sent += 1
    logger.info("digest run complete; %s accounts emailed", sent)
    return sent


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
