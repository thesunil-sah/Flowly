"""Config validators — WEB_BASE_URL canonicalization.

Both the CORS middleware and the live-socket origin check exact-match against
this value, so a stray trailing slash or mixed case must not survive load.
"""

import pytest

from app.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://localhost:3000/", "http://localhost:3000"),
        ("HTTP://Localhost:3000", "http://localhost:3000"),
        ("  https://app.flowly.io/  ", "https://app.flowly.io"),
        ("https://app.flowly.io", "https://app.flowly.io"),
    ],
)
def test_web_base_url_is_canonicalized(raw: str, expected: str) -> None:
    assert Settings(web_base_url=raw).web_base_url == expected


def test_scheme_is_preserved() -> None:
    # Normalization must not touch the scheme — http vs https is a real setting.
    assert Settings(web_base_url="https://app.flowly.io").web_base_url.startswith("https://")
