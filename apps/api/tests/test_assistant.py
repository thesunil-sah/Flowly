"""/assistant/chat — support chatbot (Phase F7): intents, fallback, rate limit."""

from httpx import AsyncClient

from app.services import assistant as assistant_service


# --- pure intent matching (no Redis / no key) -----------------------------
def test_intent_matching_picks_expected_intent() -> None:
    assert assistant_service.match_intent("What is Flowly?")[0] == "what_is"
    assert assistant_service.match_intent("how much does it cost?")[0] == "pricing"
    assert assistant_service.match_intent("do you use cookies or store my IP?")[0] == "policy"
    assert assistant_service.match_intent("how do I contact support?")[0] == "contact"
    # A question with no keywords matches nothing → AI/fallback path.
    assert assistant_service.match_intent("asdfghjkl zxcvbnm") is None


# --- endpoint -------------------------------------------------------------
async def test_matched_intent_returns_faq_answer(client: AsyncClient) -> None:
    resp = await client.post("/assistant/chat", json={"message": "What is Flowly?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "faq"
    assert "analytics" in body["reply"].lower()


async def test_pricing_intent(client: AsyncClient) -> None:
    resp = await client.post("/assistant/chat", json={"message": "what does it cost per month?"})
    body = resp.json()
    assert body["source"] == "faq"
    assert "1,000" in body["reply"] or "$" in body["reply"]


async def test_offtopic_without_key_falls_back_to_contact(client: AsyncClient) -> None:
    # No ANTHROPIC_API_KEY in tests → unmatched questions get the canned fallback,
    # never an unbounded AI answer (refuses to answer off-topic).
    resp = await client.post("/assistant/chat", json={"message": "who won the world cup?"})
    body = resp.json()
    assert body["source"] == "fallback"
    assert "/contact" in body["reply"]


async def test_empty_message_is_422(client: AsyncClient) -> None:
    resp = await client.post("/assistant/chat", json={"message": ""})
    assert resp.status_code == 422


async def test_rate_limited_after_max(client: AsyncClient) -> None:
    for _ in range(assistant_service.ASSISTANT_MAX):
        assert (await client.post("/assistant/chat", json={"message": "hi"})).status_code == 200
    blocked = await client.post("/assistant/chat", json={"message": "hi"})
    assert blocked.status_code == 429
