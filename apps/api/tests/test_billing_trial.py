"""billing.on_event_committed — the trial-ending nudge (§7/§8).

The post-commit hook must email only on `trial_will_end`, resolve the account
from the event, and never affect entitlement.
"""

from app.models.tables import Account
from app.services import billing


async def test_trial_will_end_sends_email(session_factory, monkeypatch) -> None:
    async with session_factory() as s:
        acc = Account(email="t@e.com", username="t")
        s.add(acc)
        await s.commit()
        acc_id = acc.id

    sent: list[tuple[str, str]] = []

    async def fake_send(to, subject, text, html=None):
        sent.append((to, subject))

    monkeypatch.setattr(billing, "send_email", fake_send)
    event = {
        "type": "customer.subscription.trial_will_end",
        "data": {"object": {"metadata": {"account_id": str(acc_id)}}},
    }
    async with session_factory() as s:
        await billing.on_event_committed(s, event)
    assert len(sent) == 1
    assert "trial" in sent[0][1].lower()


async def test_other_events_send_no_email(session_factory, monkeypatch) -> None:
    sent: list[int] = []

    async def fake_send(to, subject, text, html=None):
        sent.append(1)

    monkeypatch.setattr(billing, "send_email", fake_send)
    event = {"type": "customer.subscription.updated", "data": {"object": {}}}
    async with session_factory() as s:
        await billing.on_event_committed(s, event)
    assert sent == []
