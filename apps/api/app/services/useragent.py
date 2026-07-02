"""Zero-dependency User-Agent classification for ingestion.

Two jobs, both intentionally lightweight (CLAUDE.md §5 keeps this dependency-free):
  - `is_bot(ua)`  — drop crawlers/monitors before they are counted (accuracy).
  - `parse(ua)`   — best-effort `(device, browser, os)` for the audience reports.

This is heuristic, not a full UA database: it covers the overwhelming majority
of real browser traffic and fails soft (returns "" for anything unrecognised)
rather than ever raising. If accuracy proves insufficient we can swap in a
maintained library later (noted in the Phase 3 plan) without touching callers.
"""

import re

# Substrings that mark automated clients. Matched case-insensitively against the
# full UA. Kept broad on purpose — a false "bot" is cheaper than counting one.
_BOT_MARKERS = (
    "bot",
    "crawl",
    "spider",
    "slurp",
    "mediapartners",
    "adsbot",
    "bingpreview",
    "facebookexternalhit",
    "embedly",
    "quora link preview",
    "pinterest",
    "vkshare",
    "w3c_validator",
    "redditbot",
    "applebot",
    "whatsapp",
    "flipboard",
    "tumblr",
    "headlesschrome",
    "phantomjs",
    "python-requests",
    "python-httpx",
    "curl/",
    "wget/",
    "go-http-client",
    "axios/",
    "okhttp",
    "java/",
    "libwww-perl",
    "lighthouse",
    "pingdom",
    "uptimerobot",
    "gtmetrix",
    "monitis",
    "datadog",
    "newrelicpinger",
)

# Ordered browser probes: first match wins. Order matters — Edge/Opera/Chrome
# all contain "chrome"-ish tokens, so the more specific ones come first.
_BROWSERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Edge", re.compile(r"edg(?:a|ios|e)?/", re.I)),
    ("Opera", re.compile(r"opr/|opera", re.I)),
    ("Samsung Internet", re.compile(r"samsungbrowser", re.I)),
    ("Firefox", re.compile(r"firefox/|fxios/", re.I)),
    # Chrome before Safari: Chrome UAs also contain "Safari".
    ("Chrome", re.compile(r"chrome/|crios/|chromium", re.I)),
    ("Safari", re.compile(r"safari/", re.I)),
    ("Internet Explorer", re.compile(r"msie |trident/", re.I)),
)

# Ordered OS probes: first match wins. iOS/Android before the desktop families.
_OSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Android", re.compile(r"android", re.I)),
    ("iOS", re.compile(r"iphone|ipad|ipod", re.I)),
    ("Windows", re.compile(r"windows nt|windows phone", re.I)),
    ("macOS", re.compile(r"mac os x|macintosh", re.I)),
    ("Chrome OS", re.compile(r"cros ", re.I)),
    ("Linux", re.compile(r"linux", re.I)),
)

_MOBILE = re.compile(r"mobile|iphone|ipod|android.*mobile|windows phone", re.I)
_TABLET = re.compile(r"ipad|tablet|android(?!.*mobile)", re.I)


def is_bot(ua: str) -> bool:
    """True if the UA looks like a crawler, monitor, or non-browser client.

    An empty UA is treated as a bot: real browsers always send one.
    """
    if not ua:
        return True
    lowered = ua.lower()
    return any(marker in lowered for marker in _BOT_MARKERS)


def _device(ua: str) -> str:
    if _TABLET.search(ua):
        return "tablet"
    if _MOBILE.search(ua):
        return "mobile"
    return "desktop"


def _first_match(ua: str, probes: tuple[tuple[str, re.Pattern[str]], ...]) -> str:
    for label, pattern in probes:
        if pattern.search(ua):
            return label
    return ""


def parse(ua: str) -> tuple[str, str, str]:
    """Return best-effort ``(device, browser, os)``; "" for anything unknown."""
    if not ua:
        return ("", "", "")
    return (_device(ua), _first_match(ua, _BROWSERS), _first_match(ua, _OSES))
