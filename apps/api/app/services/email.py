"""Email delivery.

With no provider key configured (`EMAIL_API_KEY` empty) this falls back to a
dev stub that logs the message — so every flow is fully testable locally.
The real transactional provider is **Resend** (CLAUDE.md §5): a single HTTPS
POST via the already-present httpx, confined to `_send_via_provider`.

Messages carry an optional HTML body. Transactional mail (verify/reset codes)
stays plain text; the growth emails (digest, onboarding) send HTML. The
non-transactional gate (opt-out) lives in `services/notifications.py`, not here —
this module only delivers.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger("flowly.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"
_SEND_TIMEOUT_S = 10.0

CODE_MESSAGES = {
    "verify": "Your Flowly verification code is {code}. It expires in 10 minutes.",
    "reset": "Your Flowly password-reset code is {code}. It expires in 10 minutes.",
    "email_change": (
        "Confirm your new Flowly email with code {code}. It expires in 10 minutes. "
        "If you didn't request this, ignore this message."
    ),
}

# Subject per code purpose; falls back to a generic line for any new purpose.
CODE_SUBJECTS = {
    "verify": "Verify your email",
    "reset": "Reset your password",
    "email_change": "Confirm your new email",
}


async def _send_via_provider(to: str, subject: str, text: str, html: str | None) -> None:
    """Deliver one email through Resend. Raises on a non-2xx response.

    Callers on background workers wrap this best-effort so one failed send can't
    abort a batch; transactional callers let the error surface.
    """
    payload: dict[str, object] = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html is not None:
        payload["html"] = html
    async with httpx.AsyncClient(timeout=_SEND_TIMEOUT_S) as client:
        resp = await client.post(
            RESEND_ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {settings.email_api_key}"},
        )
    resp.raise_for_status()


async def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    """Send an email (HTML optional). Logs instead of sending in local dev.

    In local dev (or with no provider key) never send — just log — so the
    verification/reset/digest flows work without an email provider.
    """
    if settings.environment == "local" or not settings.email_api_key:
        logger.info("[email:dev-stub] to=%s subject=%s | %s", to, subject, text)
        return
    await _send_via_provider(to, subject, text, html)


async def send_code_email(to: str, code: str, purpose: str) -> None:
    subject = CODE_SUBJECTS.get(purpose, "Your Flowly code")
    body = CODE_MESSAGES[purpose].format(code=code)
    await send_email(to, subject, body)


async def send_uptime_down_email(to: str, domain: str, cause: str) -> None:
    """Alert the owner that their site went down (Phase 12).

    Transactional — a service alert about the customer's *own* site, so it goes
    straight through `send_email` and never through the marketing opt-out gate
    (`services/notifications.py`); like verify/reset, opting out can't suppress it.
    """
    subject = f"⚠️ {domain} looks down"
    text = (
        f"We couldn't reach {domain} ({cause}). "
        "We'll email you again as soon as it's back up.\n\n"
        "— Flowly uptime monitoring"
    )
    await send_email(to, subject, text)


async def send_uptime_up_email(to: str, domain: str) -> None:
    """Notify the owner that their site recovered (Phase 12). Transactional."""
    subject = f"✅ {domain} is back up"
    text = f"{domain} is responding again. The incident is resolved.\n\n— Flowly uptime monitoring"
    await send_email(to, subject, text)
