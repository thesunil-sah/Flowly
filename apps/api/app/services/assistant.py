"""Support chatbot (Phase F7): hardcoded intents first, cheap AI fallback.

A public endpoint is an abuse magnet (§ guardrails), so this is deliberately
minimal: the five known intents are answered from hardcoded canonical text (no
model call, works with no API key), and only genuinely unmatched questions fall
through to a small/cheap model (Claude Haiku) with a tightly-scoped system
prompt. With no `ANTHROPIC_API_KEY` the fallback is a canned "contact us" line —
the bot degrades gracefully rather than failing. The AI call has **zero access
to any user or analytics data**: it only ever sees the visitor's message and a
fixed set of public product facts.

The canonical answers here mirror the frontend FAQ single source
(`apps/web/content/faq.ts`) — kept in sync by hand since Python can't import the
TS module; the widget also surfaces those FAQ questions as suggested prompts.
"""

import logging

from redis.asyncio import Redis

from app.config import settings
from app.core.ratelimit import enforce_rate_limit

logger = logging.getLogger("flowly.assistant")

# Per-IP limit for the public AI endpoint: generous for a human, a wall for a bot.
ASSISTANT_MAX = 30
ASSISTANT_WINDOW_SECONDS = 3600

# --- Hardcoded intents (canonical answers) --------------------------------
_ANSWERS: dict[str, str] = {
    "what_is": (
        "Flowly is privacy-first, cookieless web analytics. You add one tiny (~1 KB) "
        "script to your site and get live visitor counts plus reports on visitors, "
        "sources, pages, geography, and devices — with no cookies, no personal data, "
        "and no consent banner."
    ),
    "pricing": (
        "Your first 1,000 pageviews each month are free. After that it's metered and "
        "the rate falls as you grow: $0.99 per 1k up to 10k, $0.10 per 1k up to 100k, "
        "$0.05 per 1k up to 1M, then $0.03 per 1k — for example 100,000 views is "
        "$17.91/month. Upgrading starts a 7-day free trial, and all your sites (up to 5) "
        "count together. See the pricing page at /pricing."
    ),
    "features": (
        "Flowly gives you real-time live visitors, historical reports (visitors, "
        "sources, pages, geography, devices), public revocable share links, CSV export, "
        "and up to 5 sites per account — all cookieless."
    ),
    "policy": (
        "Flowly is cookieless and stores no personal data: no cookies, no raw IP "
        "addresses, no persistent identifiers. Unique visitors are counted with a hash "
        "that rotates every 24 hours, so nobody is tracked across days or sites — which "
        "is why no consent banner is needed."
    ),
    "contact": (
        "You can reach us any time on our contact page at /contact — send a message by "
        "email or WhatsApp and we'll get back to you."
    ),
}

# Keyword phrases per intent (substring match on the lowercased message). Order
# matters only for tie-breaking: earlier intents win an equal score.
_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "what_is",
        (
            "what is flowly",
            "what's flowly",
            "what does flowly",
            "about flowly",
            "who are you",
            "explain flowly",
            "tell me about",
            "what is this",
        ),
    ),
    (
        "pricing",
        (
            "pric",
            "cost",
            "how much",
            "plan",
            "free",
            "trial",
            "billing",
            "pay",
            "subscription",
            "expensive",
            "charge",
            "$",
        ),
    ),
    (
        "features",
        (
            "feature",
            "what can",
            "report",
            "real-time",
            "realtime",
            "live visitor",
            "dashboard",
            "export",
            "share link",
            "capabilit",
            "integrat",
        ),
    ),
    (
        "policy",
        (
            "privacy",
            "cookie",
            "gdpr",
            "consent",
            "personal data",
            "raw ip",
            "anonym",
            "track",
            "compliance",
            "retention",
        ),
    ),
    (
        "contact",
        (
            "contact",
            "support",
            "help",
            "reach",
            "get in touch",
            "talk to",
            "human",
            "whatsapp",
            "email you",
        ),
    ),
]

_CONTACT_FALLBACK = (
    "I'm not sure about that one. For anything I can't answer, reach us on the contact "
    "page at /contact and a human will help you out."
)

_SYSTEM_PROMPT = (
    "You are the support assistant for Flowly, a privacy-first, cookieless web analytics "
    "product. Answer ONLY questions about Flowly. Facts you may rely on: Flowly adds one "
    "~1 KB script to a website and shows live visitors plus reports (visitors, sources, "
    "pages, geography, devices); it uses no cookies, stores no personal data or raw IP "
    "addresses, rotates an anonymous visitor hash every 24 hours, and needs no consent "
    "banner; the first 1,000 pageviews per month are free, then usage is metered with "
    "rates that fall as volume grows and a 7-day trial on upgrade; up to 5 sites per "
    "account. Rules: keep answers to at most 3 sentences; NEVER invent specific prices, "
    "features, or policies — if you are unsure, point the user to the pricing page "
    "(/pricing) or the contact page (/contact); if the question is not about Flowly, "
    "politely say you can only help with Flowly and suggest the contact page. You have no "
    "access to any account or analytics data."
)


def match_intent(message: str) -> tuple[str, str] | None:
    """Best-matching (intent, canonical answer) for a message, or None.

    Pure + deterministic so it's unit-testable without Redis or an API key.
    """
    text = message.lower()
    best_intent: str | None = None
    best_score = 0
    for intent, keywords in _INTENT_KEYWORDS:
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_intent = intent
    if best_intent is None:
        return None
    return best_intent, _ANSWERS[best_intent]


# --- AI fallback (cheap model, key-gated, best-effort) --------------------
_ai_client = None


def _get_ai_client():
    """Lazily build a cached AsyncAnthropic client; None when no key is set."""
    global _ai_client
    if not settings.anthropic_api_key:
        return None
    if _ai_client is None:
        from anthropic import AsyncAnthropic

        _ai_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _ai_client


async def _ai_answer(message: str) -> str | None:
    """Ask the cheap model, scoped to Flowly facts. None on no-key or any error."""
    client = _get_ai_client()
    if client is None:
        return None
    try:
        # Haiku 4.5: plain messages.create — no thinking/effort params. Low
        # max_tokens + single-message context are part of the abuse guardrail.
        resp = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        text = " ".join(p.strip() for p in parts if p).strip()
        return text or None
    except Exception:
        logger.warning("assistant AI fallback failed", exc_info=True)
        return None


async def answer(redis: Redis, client_ip: str, message: str) -> tuple[str, str]:
    """Answer a support question. Returns (reply, source).

    Rate-limited per IP. Hardcoded intents first (no model call); unmatched
    questions try the cheap AI model, else a canned contact fallback.
    """
    await enforce_rate_limit(
        redis, f"ratelimit:assistant:{client_ip}", ASSISTANT_MAX, ASSISTANT_WINDOW_SECONDS
    )

    matched = match_intent(message)
    if matched is not None:
        return matched[1], "faq"

    ai = await _ai_answer(message)
    if ai is not None:
        return ai, "ai"

    return _CONTACT_FALLBACK, "fallback"
