"""/billing routes — auth gating, mocked Stripe checkout/portal, and the webhook.

The webhook is the unforgiving path (§10): a bad signature must 400 and a
redelivered event must apply exactly once. Stripe SDK network calls
(`create_async`) and the signature verifier are monkeypatched — no live Stripe.
Phase 14: one metered plan, checkout takes no tier, trial is once per account.
"""

from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import FREE_MONTHLY_VIEWS
from app.core.security import create_access_token
from app.models.tables import Account, ProcessedStripeEvent, Subscription
from app.services import billing


async def _owner(session_factory: async_sessionmaker[AsyncSession], **over: object) -> UUID:
    async with session_factory() as s:
        acc = Account(email="own@example.com", username="own", **over)
        s.add(acc)
        await s.commit()
        return acc.id


def _auth(account_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(account_id)}"}


# --- auth gating ---------------------------------------------------------
async def test_checkout_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/billing/checkout")
    assert resp.status_code == 401


async def test_portal_requires_auth(client: AsyncClient) -> None:
    assert (await client.post("/billing/portal")).status_code == 401


async def test_usage_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/billing/usage")).status_code == 401


# --- usage ---------------------------------------------------------------
async def test_usage_returns_summary_shape(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner = await _owner(session_factory, plan="free", status="free")
    resp = await client.get("/billing/usage", headers=_auth(owner))
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "free" and body["quota"] == FREE_MONTHLY_VIEWS
    assert body["used"] == 0 and body["status"] == "ok"


# --- checkout (mocked Stripe) -------------------------------------------
def _capture_checkout(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Stub Checkout creation; return the list its kwargs are recorded into."""
    calls: list[dict[str, Any]] = []

    async def _fake_create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return type("S", (), {"url": "https://checkout.stripe.test/xyz"})()

    monkeypatch.setattr(billing.stripe.checkout.Session, "create_async", _fake_create)
    return calls


async def test_checkout_returns_stripe_url_with_trial_for_new_account(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing.settings, "stripe_price_metered", "price_metered")
    calls = _capture_checkout(monkeypatch)
    owner = await _owner(session_factory, plan="free", status="free")
    resp = await client.post("/billing/checkout", headers=_auth(owner))
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://checkout.stripe.test/xyz"
    # A first-time subscriber gets the 7-day trial (trial repositioned to upgrade).
    assert calls[0]["subscription_data"]["trial_period_days"] == billing.TRIAL_DAYS


async def test_checkout_no_trial_for_account_that_already_trialed(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    monkeypatch.setattr(billing.settings, "stripe_price_metered", "price_metered")
    calls = _capture_checkout(monkeypatch)
    # An account that already consumed its trial (trial_ends_at set) subscribes now
    # with NO second trial — one trial per account.
    owner = await _owner(
        session_factory,
        plan="free",
        status="canceled",
        trial_ends_at=datetime.now(UTC) - timedelta(days=30),
    )
    resp = await client.post("/billing/checkout", headers=_auth(owner))
    assert resp.status_code == 200
    assert "trial_period_days" not in calls[0]["subscription_data"]


async def test_checkout_402_when_billing_not_configured(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # No STRIPE_PRICE_METERED set (default "") → billing inert → 402, not a 500.
    owner = await _owner(session_factory, plan="free", status="free")
    resp = await client.post("/billing/checkout", headers=_auth(owner))
    assert resp.status_code == 402


async def test_checkout_blocked_when_already_subscribed(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An active account re-running Checkout would mint a second live Stripe
    # subscription (double billing) — it must be sent to the portal instead.
    monkeypatch.setattr(billing.settings, "stripe_price_metered", "price_metered")
    owner = await _owner(session_factory, plan="metered", status="active")
    resp = await client.post("/billing/checkout", headers=_auth(owner))
    assert resp.status_code == 402  # BillingError — manage via portal


async def test_checkout_blocked_while_trialing(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A trialing account is already `metered` (entitled). Re-running Checkout
    # would mint a SECOND live subscription → double billing. The guard must
    # gate on effective entitlement, not just active/past_due.
    from datetime import UTC, datetime, timedelta

    monkeypatch.setattr(billing.settings, "stripe_price_metered", "price_metered")
    owner = await _owner(
        session_factory,
        plan="metered",
        status="trialing",
        trial_ends_at=datetime.now(UTC) + timedelta(days=3),
    )
    resp = await client.post("/billing/checkout", headers=_auth(owner))
    assert resp.status_code == 402  # blocked — use the portal, don't double-subscribe


async def test_portal_without_subscription_is_402(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner = await _owner(session_factory)
    resp = await client.post("/billing/portal", headers=_auth(owner))
    assert resp.status_code == 402  # BillingError — no Stripe customer yet


# --- webhook -------------------------------------------------------------
def _mock_verify(monkeypatch: pytest.MonkeyPatch, event: dict | None) -> None:
    """Replace signature verification: return `event`, or raise if None (bad sig)."""

    def _verify(payload: bytes, signature: str | None) -> Any:
        if event is None:
            raise billing.stripe.SignatureVerificationError("bad sig", signature)
        return event

    monkeypatch.setattr(billing, "verify_webhook", _verify)


async def test_webhook_bad_signature_is_400(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_verify(monkeypatch, None)
    resp = await client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert resp.status_code == 400


async def test_webhook_processes_then_dedupes(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(billing.settings, "stripe_price_metered", "price_metered")
    owner = await _owner(session_factory, plan="free", status="free")
    event = {
        "id": "evt_123",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "active",
                "cancel_at_period_end": False,
                "current_period_end": 1_793_000_000,
                "metadata": {"account_id": str(owner)},
                "items": {"data": [{"price": {"id": "price_metered"}}]},
            }
        },
    }
    _mock_verify(monkeypatch, event)

    first = await client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert first.status_code == 200 and first.json()["status"] == "ok"

    # Redelivery of the SAME event id must be a no-op (exactly-once).
    second = await client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert second.status_code == 200 and second.json()["status"] == "ignored"

    async with session_factory() as s:
        acc = await s.get(Account, owner)
        assert acc.plan == "metered" and acc.status == "active"  # entitlement from webhook only
        subs = (await s.scalars(select(Subscription).where(Subscription.account_id == owner))).all()
        assert len(subs) == 1  # processed once, not twice
        ledger = (await s.scalars(select(ProcessedStripeEvent))).all()
        assert [e.event_id for e in ledger] == ["evt_123"]
