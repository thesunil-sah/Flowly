"""Usage-report worker — push metered usage to Stripe, then exit (Phase 14).

Run periodically (e.g. hourly) with:
    uv run python -m app.workers.usage_report

Redis is the real-time source of truth for usage (the `usage:{account_id}:
{YYYYMM}` counter incremented on the ingest hot path); Stripe's Billing Meter
needs it to bill the graduated tiers. This worker pushes each metered account's
DELTA since the last push (`services/billing.report_usage_to_stripe`) — meter
events are additive, so re-runs never double-count. Best-effort per account.
Inert (no-op) until `STRIPE_PRICE_METERED` + a real Stripe key are configured.
"""

import asyncio
import logging
from datetime import UTC, datetime

from app.db.postgres import async_session_factory, dispose_engine
from app.db.redis import close_redis, get_client
from app.services import billing

logger = logging.getLogger("flowly.usage_report")


async def run(now: datetime | None = None) -> int:
    """Push all metered accounts' usage deltas to Stripe. Returns accounts pushed."""
    now = now or datetime.now(UTC)
    redis = get_client()
    async with async_session_factory() as session:
        return await billing.report_usage_to_stripe(session, redis, now)


async def _main() -> None:
    try:
        await run()
    finally:
        await close_redis()
        await dispose_engine()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())


if __name__ == "__main__":
    main()
