"""Public contact-form handling (Phase F6).

A public, unauthenticated endpoint is an abuse magnet, so submissions are
double-guarded: a honeypot field (bots fill it, humans never see it) and a
per-IP rate limit. The message is delivered as **transactional** mail (a direct
`send_email`, never the marketing opt-out gate — it's a reply to a person who
just wrote in, not a broadcast). In local dev with no provider key `send_email`
just logs, so the flow is testable offline.
"""

import logging

from redis.asyncio import Redis

from app.config import settings
from app.core.ratelimit import enforce_rate_limit
from app.services.email import send_email

logger = logging.getLogger("flowly.contact")

# 3 messages / hour / IP — generous for a human, a wall for a script.
CONTACT_MAX = 3
CONTACT_WINDOW_SECONDS = 3600


async def submit_contact(
    redis: Redis, client_ip: str, name: str, email: str, message: str, honeypot: str
) -> None:
    """Rate-limit + honeypot-check a submission, then email it to support."""
    if honeypot.strip():
        # A bot filled the hidden field. Drop silently — return normally so the
        # bot can't distinguish acceptance from rejection.
        logger.info("contact honeypot triggered; dropping submission")
        return

    await enforce_rate_limit(
        redis, f"ratelimit:contact:{client_ip}", CONTACT_MAX, CONTACT_WINDOW_SECONDS
    )

    subject = f"[Flowly contact] {name}"
    body = f"From: {name} <{email}>\n\n{message}"
    # Transactional: delivered to the configured support inbox (CONTACT_EMAIL),
    # falling back to email_from (self-send) when unset. The sender's address is
    # in the body for replies.
    to = settings.contact_email or settings.email_from
    await send_email(to, subject, body)
