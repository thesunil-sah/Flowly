"""normalize_host — shared by ingestion (full URLs) and onboarding (bare hosts).

The bare-host cases are the ones that matter for site onboarding: a user types
`example.com`, not `https://example.com`, and a naive `urlparse().netloc` returns
`""` for that. These lock the scheme-less handling and the never-raise contract.
"""

import pytest

from app.core.urls import normalize_host


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Bare hosts (the onboarding input) — all normalize to the same host.
        ("example.com", "example.com"),
        ("EXAMPLE.com", "example.com"),
        ("example.com/", "example.com"),
        ("example.com/path?q=1", "example.com"),
        ("www.example.com", "example.com"),
        ("example.com:8080", "example.com"),
        ("  example.com  ", "example.com"),
        # Full URLs (the ingestion input) — behavior preserved.
        ("https://www.example.com/x", "example.com"),
        ("http://example.com", "example.com"),
        ("https://demo.example/x", "demo.example"),
        ("http://user@example.com/x", "example.com"),
        # Empty / junk -> "" (never raises; ingestion hot path depends on this).
        ("", ""),
        (None, ""),
        ("   ", ""),
    ],
)
def test_normalize_host(raw: str | None, expected: str) -> None:
    assert normalize_host(raw) == expected
