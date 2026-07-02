"""Email delivery.

With no provider key configured (`EMAIL_API_KEY` empty) this falls back to a
dev stub that logs the message — so the verification/reset flows are fully
testable locally. Wiring a real transactional provider (Resend/Postmark per
CLAUDE.md §5) is a change confined to `_send_via_provider`.
"""

import logging

from app.config import settings

logger = logging.getLogger("flowly.email")

CODE_MESSAGES = {
    "verify": "Your Flowly verification code is {code}. It expires in 10 minutes.",
    "reset": "Your Flowly password-reset code is {code}. It expires in 10 minutes.",
}


async def _send_via_provider(to: str, subject: str, body: str) -> None:
    # Placeholder for Resend/Postmark. Intentionally unimplemented until a
    # provider + verified sender are configured; the dev stub covers local use.
    raise NotImplementedError("No email provider configured (set EMAIL_API_KEY).")


async def send_email(to: str, subject: str, body: str) -> None:
    # In local dev (or with no provider key) never send — just log, so the
    # verification/reset flows work without an email provider.
    if settings.environment == "local" or not settings.email_api_key:
        logger.info("[email:dev-stub] to=%s subject=%s | %s", to, subject, body)
        return
    await _send_via_provider(to, subject, body)


async def send_code_email(to: str, code: str, purpose: str) -> None:
    subject = "Verify your email" if purpose == "verify" else "Reset your password"
    body = CODE_MESSAGES[purpose].format(code=code)
    await send_email(to, subject, body)
