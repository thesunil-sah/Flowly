"""Uptime pinger worker — one pass, then exit (cron-triggered, Phase 12).

Run on a short schedule (e.g. every 5 minutes) with:
    uv run python -m app.workers.uptime

Each pass checks every registered site's domain once and folds the result into
its monitor + incident state (`services/uptime.py`), emailing the owner when a
site goes down and again when it recovers. Gated behind `UPTIME_ENABLED` so no
customer site is ever probed until an operator turns it on. A failure on one site
is logged and never aborts the rest of the sweep.
"""

import asyncio
import logging
from datetime import UTC, datetime

from app.config import settings
from app.db.postgres import async_session_factory, dispose_engine
from app.services import uptime

logger = logging.getLogger("flowly.uptime")


async def run(now: datetime | None = None) -> int:
    """Check all sites once. Returns the number of sites processed."""
    if not settings.uptime_enabled:
        logger.info("uptime monitoring disabled (UPTIME_ENABLED=false); skipping run")
        return 0
    now = now or datetime.now(UTC)
    async with async_session_factory() as session:
        return await uptime.sweep(session, now)


async def _main() -> None:
    try:
        await run()
    finally:
        await dispose_engine()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())


if __name__ == "__main__":
    main()
