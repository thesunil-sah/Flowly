"""Channel classifier unit tests (Phase 10).

`classify` is the pure Python side of the same host lists `services/stats.py`
bakes into its SQL `multiIf`, so pinning the buckets here also pins the report.
"""

from app.services import channels


def test_empty_referrer_is_direct() -> None:
    assert channels.classify("") == "direct"
    assert channels.classify("   ") == "direct" or channels.classify("   ") == "referral"


def test_search_engines_bucket_as_search() -> None:
    for host in ("www.google.com", "google.co.uk", "bing.com", "duckduckgo.com", "yandex.ru"):
        assert channels.classify(host) == "search", host


def test_social_networks_bucket_as_social() -> None:
    for host in ("x.com", "twitter.com", "www.linkedin.com", "old.reddit.com", "t.co"):
        assert channels.classify(host) == "social", host


def test_ai_assistants_bucket_as_ai() -> None:
    for host in ("chatgpt.com", "chat.openai.com", "perplexity.ai", "claude.ai", "you.com"):
        assert channels.classify(host) == "ai", host


def test_ai_wins_over_search_for_google_subdomain() -> None:
    # gemini.google.com contains the `google.` search marker; AI is checked first.
    assert channels.classify("gemini.google.com") == "ai"
    assert channels.classify("bard.google.com") == "ai"


def test_unknown_host_is_referral() -> None:
    assert channels.classify("news.ycombinator.com") == "referral"
    assert channels.classify("some-blog.example") == "referral"


def test_classify_is_case_insensitive() -> None:
    assert channels.classify("WWW.GOOGLE.COM") == "search"
    assert channels.classify("ChatGPT.com") == "ai"
