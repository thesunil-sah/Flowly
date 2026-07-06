"""Channel classification for referral traffic (Phase 10).

Buckets a referrer host into a marketing channel: **direct** (no referrer),
**search** engines, **social** networks, **AI** assistants (a 2026-relevant
report — LLM referrals now show up in real traffic), or **referral** (anything
else). The host lists here are the single source of truth, shared by:

  - `classify()` — the pure Python classifier (unit-tested), and
  - `services/stats.py::build_channels` — a ClickHouse `multiIf` built from these
    same lists so the bucketing aggregates in the database.

Each entry is a hostname substring matched against the referrer's host (case-
insensitive). These are internal constants, never user input — so `build_channels`
may safely bake them into SQL text (the §9 no-string-formatting rule is about
user *values*). AI is checked before search so `gemini.google.com` isn't caught
by the `google.` search marker.
"""

# Ordered by check priority (AI before search — see module docstring).
AI_HOSTS: tuple[str, ...] = (
    "chatgpt.com",
    "chat.openai.com",
    "perplexity.ai",
    "claude.ai",
    "gemini.google.com",
    "bard.google.com",
    "copilot.microsoft.com",
    "you.com",
)
SEARCH_HOSTS: tuple[str, ...] = (
    "google.",
    "bing.com",
    "duckduckgo.com",
    "yahoo.",
    "yandex.",
    "ecosia.org",
    "brave.com",
    "baidu.com",
)
SOCIAL_HOSTS: tuple[str, ...] = (
    "x.com",
    "twitter.com",
    "t.co",
    "linkedin.com",
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "t.me",
    "tiktok.com",
    "pinterest.com",
    "mastodon.",
)

CHANNELS: tuple[str, ...] = ("direct", "search", "social", "ai", "referral")
# Channels that have a per-referrer drill-down (direct/referral don't).
DRILLDOWN_CHANNELS: dict[str, tuple[str, ...]] = {
    "ai": AI_HOSTS,
    "search": SEARCH_HOSTS,
    "social": SOCIAL_HOSTS,
}


def classify(referrer_host: str) -> str:
    """Bucket a referrer hostname into one of `CHANNELS`.

    An empty host is `direct`. AI is matched first, then search, then social;
    anything with a host but no match is `referral`.
    """
    host = (referrer_host or "").lower()
    if not host:
        return "direct"
    for markers, name in ((AI_HOSTS, "ai"), (SEARCH_HOSTS, "search"), (SOCIAL_HOSTS, "social")):
        if any(marker in host for marker in markers):
            return name
    return "referral"
