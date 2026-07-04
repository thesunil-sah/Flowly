"""Billing endpoints — checkout, portal, usage, and the Stripe webhook (§10).

Thin as ever: parse, depend, call `services/billing.py`, return a schema. The
three account-facing routes are authed (dashboard-locked CORS). The webhook is
**public** (Stripe calls it server-to-server) and authenticated by its *signature*
— it verifies the signature, dedupes by event id for exactly-once processing, and
applies the effect + records the id in one transaction. Entitlement changes only
ever happen inside the webhook, never from a Checkout redirect.
"""

import logging
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import CurrentUser
from app.db.postgres import get_session
from app.db.redis import get_redis
from app.models.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    MessageResponse,
    PortalResponse,
    UsageSummary,
)
from app.models.tables import ProcessedStripeEvent
from app.services import billing

logger = logging.getLogger("flowly.billing")

router = APIRouter(prefix="/billing", tags=["billing"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


class WebhookSignatureError(AppError):
    """A webhook body failed Stripe signature verification (→ 400, never process)."""

    status_code = 400
    message = "Invalid webhook signature."


@router.post("/checkout")
async def checkout(
    data: CheckoutRequest, account: CurrentUser, session: SessionDep
) -> CheckoutResponse:
    """A Stripe Checkout URL for the chosen tier + interval."""
    url = await billing.create_checkout_session(session, account, data.tier, data.interval)
    return CheckoutResponse(url=url)


@router.post("/portal")
async def portal(account: CurrentUser, session: SessionDep) -> PortalResponse:
    """A Stripe Customer Portal URL (manage / cancel). 402 if no subscription."""
    url = await billing.create_portal_session(session, account)
    return PortalResponse(url=url)


@router.get("/usage")
async def usage(account: CurrentUser, redis: RedisDep) -> UsageSummary:
    """Current-month usage vs the account's effective plan quota."""
    summary = await billing.usage_summary(redis, account)
    return UsageSummary(**summary)


@router.post("/webhook")
async def webhook(request: Request, session: SessionDep) -> MessageResponse:
    """Stripe webhook: verify signature, dedupe by event id, apply once.

    Public + server-to-server; the signature is the auth. A bad signature → 400.
    A redelivered event (Stripe is at-least-once) is a no-op via the
    processed-events ledger. Applying the effect and recording the id share one
    transaction, so the two can't drift.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = billing.verify_webhook(payload, signature)
    except (stripe.SignatureVerificationError, ValueError) as exc:
        raise WebhookSignatureError() from exc

    event_id = event["id"]
    if await session.get(ProcessedStripeEvent, event_id) is not None:
        return MessageResponse(status="ignored")  # already processed — ack, skip

    await billing.apply_subscription_event(session, event)
    session.add(ProcessedStripeEvent(event_id=event_id, type=event["type"]))
    try:
        await session.commit()
    except IntegrityError:
        # Raced with a concurrent delivery of the same event; the PK collision
        # means the other request already processed it. Ack idempotently.
        await session.rollback()
        return MessageResponse(status="ignored")
    # Post-commit best-effort side effects (e.g. the trial-ending nudge). Never
    # affects entitlement and never fails the webhook.
    await billing.on_event_committed(session, event)
    return MessageResponse(status="ok")
