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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Managed-Postgres sync DSNs are upgraded to the asyncpg driver.
        ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        # An explicit driver (or a non-Postgres URL) is left untouched.
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("sqlite+aiosqlite:///./test.db", "sqlite+aiosqlite:///./test.db"),
    ],
)
def test_database_url_gets_asyncpg_driver(raw: str, expected: str) -> None:
    assert Settings(database_url=raw).database_url == expected


def test_clickhouse_secure_defaults_off() -> None:
    # Plain local ClickHouse by default; ClickHouse Cloud flips CLICKHOUSE_SECURE.
    # `_env_file=None` tests the code default in isolation from a developer's .env
    # (which, once pointed at ClickHouse Cloud, sets CLICKHOUSE_SECURE=true).
    s = Settings(_env_file=None)
    assert s.clickhouse_secure is False
    assert s.clickhouse_port is None
