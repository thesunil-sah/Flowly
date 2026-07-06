"""/contact — public contact form (Phase F6): honeypot, rate limit, delivery."""

import app.services.contact as contact_service
from httpx import AsyncClient

VALID = {"name": "Ada", "email": "ada@example.com", "message": "Hello there, I have a question."}


def _capture_send(monkeypatch) -> list[tuple[str, str, str]]:
    sent: list[tuple[str, str, str]] = []

    async def fake_send(to: str, subject: str, text: str, html: str | None = None) -> None:
        sent.append((to, subject, text))

    monkeypatch.setattr(contact_service, "send_email", fake_send)
    return sent


async def test_valid_submission_sends_email(client: AsyncClient, monkeypatch) -> None:
    sent = _capture_send(monkeypatch)
    resp = await client.post("/contact", json=VALID)
    assert resp.status_code == 204
    assert len(sent) == 1
    # The sender's address rides in the body (for replies), never the To.
    assert "ada@example.com" in sent[0][2]


async def test_honeypot_drops_silently(client: AsyncClient, monkeypatch) -> None:
    sent = _capture_send(monkeypatch)
    resp = await client.post("/contact", json={**VALID, "company": "spam-bot-corp"})
    assert resp.status_code == 204  # looks like success to the bot
    assert sent == []  # but nothing was sent


async def test_invalid_payload_is_422(client: AsyncClient, monkeypatch) -> None:
    _capture_send(monkeypatch)
    resp = await client.post("/contact", json={"name": "", "email": "nope", "message": ""})
    assert resp.status_code == 422


async def test_rate_limited_after_max(client: AsyncClient, monkeypatch) -> None:
    _capture_send(monkeypatch)
    # CONTACT_MAX allowed, the next one is blocked (same client IP in tests).
    for _ in range(contact_service.CONTACT_MAX):
        assert (await client.post("/contact", json=VALID)).status_code == 204
    blocked = await client.post("/contact", json=VALID)
    assert blocked.status_code == 429
