"""URL / host normalization — shared by ingestion and site onboarding.

`normalize_host` is the single canonical way to turn a raw URL *or* a bare
domain into a comparable host: lowercase, no scheme, no path, no port, no
leading `www.`. It is used two ways that MUST agree:

  - **Ingestion** (`services/ingest.py`) derives a traffic source from the
    referrer/origin — full URLs with a scheme.
  - **Onboarding** (`services/sites.py`) normalizes the domain a user types —
    usually a bare host with no scheme.

Because ingestion runs on the `/collect` hot path, which must never fail
(CLAUDE.md §9), this helper **never raises** — unparseable input returns `""`.
Callers that consider an empty host an error (e.g. site creation) raise on the
empty result themselves; the helper stays pure.
"""

from urllib.parse import urlparse


def normalize_host(raw: str | None) -> str:
    """Canonical host of a URL or bare domain; `""` if empty/unparseable.

    Examples (all -> `example.com`): `"https://www.example.com/x"`,
    `"EXAMPLE.com/"`, `"example.com:8080"`, `"http://user@example.com"`.
    Never raises — the ingestion hot path depends on that.
    """
    if not raw:
        return ""
    raw = raw.strip()
    if not raw:
        return ""
    # A bare host (no scheme) parses with an EMPTY netloc — every character
    # lands in `path` instead. Prepend `//` so urlparse treats the leading
    # segment as the authority. URLs that already carry `//` are left alone.
    to_parse = raw if "//" in raw else "//" + raw
    try:
        netloc = urlparse(to_parse).netloc.lower()
    except ValueError:
        return ""
    # Drop any userinfo (`user@`) and port; keep just the hostname.
    host = netloc.rsplit("@", 1)[-1].split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host
