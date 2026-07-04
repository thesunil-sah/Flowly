"""Retention worker — delete events past each site's per-plan window (§9).

Run daily:
    uv run python -m app.workers.retention

For every site it resolves the owner's **effective plan** (a lapsed trial is
`free`), computes the cutoff (`config.RETENTION_DAYS`), and issues a site-scoped
`ALTER TABLE events DELETE` for anything older. This is destructive and
irreversible by design — deleting expired data is the privacy promise (§9) — so
each deletion is logged with its site and cutoff. A failure on one site is logged
and never aborts the rest of the sweep.
"""

import asyncio
import logging
from datetime import UTC, datetime

from app.db.clickhouse import close_clickhouse, get_clickhouse
from app.db.postgres import async_session_factory, dispose_engine
from app.models.tables import Account
from app.services import billing, retention, sites

logger = logging.getLogger("flowly.retention")


async def run(now: datetime | None = None) -> int:
    """Apply retention to every site. Returns the number of sites processed."""
    now = now or datetime.now(UTC)
    ch = await get_clickhouse()
    processed = 0
    async with async_session_factory() as session:
        for site in await sites.list_all_sites(session):
            account = await session.get(Account, site.account_id)
            if account is None:  # pragma: no cover - referential integrity
                continue
            plan = billing.effective_plan(account, now)
            try:
                cutoff = await retention.delete_expired_for_site(ch, site.site_id, plan, now)
            except Exception:
                logger.exception("retention delete failed for site %s", site.site_id)
                continue
            logger.info(
                "retention: site=%s plan=%s deleted events before %s",
                site.site_id,
                plan,
                cutoff.isoformat(),
            )
            processed += 1
    logger.info("retention run complete; %s sites processed", processed)
    return processed


async def _main() -> None:
    try:
        await run()
    finally:
        await close_clickhouse()
        await dispose_engine()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())


if __name__ == "__main__":
    main()
