"""Unit tests for password hashing + JWT primitives (no DB/Redis needed)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.config import settings
from app.core.exceptions import AuthError
from app.core.security import (
    access_token_expiry,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_roundtrip() -> None:
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"  # never plaintext
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong password", h) is False


def test_access_token_roundtrip() -> None:
    account_id = uuid4()
    token = create_access_token(account_id)
    assert decode_token(token, "access") == account_id


def test_access_token_expiry_matches_ttl() -> None:
    token = create_access_token(uuid4())
    remaining = (access_token_expiry(token) - datetime.now(UTC)).total_seconds()
    # Expiry is ~access_token_ttl from now (allow a small clock delta).
    assert settings.access_token_ttl - 5 < remaining <= settings.access_token_ttl


def test_refresh_token_roundtrip() -> None:
    account_id = uuid4()
    token = create_refresh_token(account_id)
    assert decode_token(token, "refresh") == account_id


def test_wrong_token_type_rejected() -> None:
    account_id = uuid4()
    access = create_access_token(account_id)
    refresh = create_refresh_token(account_id)
    with pytest.raises(AuthError):
        decode_token(access, "refresh")
    with pytest.raises(AuthError):
        decode_token(refresh, "access")


def test_expired_token_rejected() -> None:
    past = datetime.now(UTC) - timedelta(seconds=10)
    token = jwt.encode(
        {"sub": str(uuid4()), "type": "access", "exp": int(past.timestamp())},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(AuthError):
        decode_token(token, "access")


def test_tampered_token_rejected() -> None:
    token = create_access_token(uuid4())
    with pytest.raises(AuthError):
        decode_token(token + "x", "access")
