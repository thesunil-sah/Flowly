"""Search Console sync worker — one pass, then exit (cron daily, Phase 13).

Run daily with:
    uv run python -m app.workers.searchconsole

Re-pulls the trailing `GSC_SYNC_DAYS` of Search Analytics for every connected
site (`services/searchconsole.sync_all`), idempotent per (site, day). A failure
on one site (expired token, GSC hiccup) is logged and never aborts the rest;
tokens are never logged (§9).
"""

import asyncio
import logging
from datetime import UTC, datetime

from app.db.postgres import async_session_factory, dispose_engine
from app.services import searchconsole

logger = logging.getLogger("flowly.searchconsole")


async def run(now: datetime | None = None) -> int:
    """Sync all connected sites once. Returns connections synced."""
    now = now or datetime.now(UTC)
    async with async_session_factory() as session:
        return await searchconsole.sync_all(session, now)


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
