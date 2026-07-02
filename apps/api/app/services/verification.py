"""Six-digit code lifecycle for email verification + password reset.

Codes live in Redis with a TTL. Sending is cooldown-limited; verification is
attempt-limited (to blunt brute force of a 6-digit space). `purpose` is
"verify" (confirm email) or "reset" (password reset).
"""

import secrets

from redis.asyncio import Redis

from app.core.exceptions import AuthError, RateLimitError
from app.services.email import send_code_email

CODE_TTL = 600  # 10 minutes
RESEND_COOLDOWN = 60  # seconds between sends to one address
MAX_VERIFY_ATTEMPTS = 5


def _code_key(purpose: str, email: str) -> str:
    return f"code:{purpose}:{email}"


def _attempts_key(purpose: str, email: str) -> str:
    return f"code:{purpose}:{email}:attempts"


def _cooldown_key(purpose: str, email: str) -> str:
    return f"code:{purpose}:{email}:cooldown"


def generate_code() -> str:
    # Uniform 000000–999999, zero-padded.
    return f"{secrets.randbelow(1_000_000):06d}"


async def issue_code(redis: Redis, purpose: str, email: str) -> str:
    """Create + store a code and email it. Cooldown-limited per address.

    Returns the code so the router can surface it in local dev only.
    """
    if await redis.exists(_cooldown_key(purpose, email)):
        raise RateLimitError("A code was just sent. Please wait a moment before retrying.")

    code = generate_code()
    await redis.set(_code_key(purpose, email), code, ex=CODE_TTL)
    await redis.delete(_attempts_key(purpose, email))
    await redis.set(_cooldown_key(purpose, email), "1", ex=RESEND_COOLDOWN)
    await send_code_email(email, code, purpose)
    return code


async def verify_code(redis: Redis, purpose: str, email: str, code: str) -> None:
    """Validate a submitted code; raise AuthError on miss/expiry, RateLimitError
    once attempts are exhausted. Consumes the code on success."""
    stored = await redis.get(_code_key(purpose, email))
    if stored is None:
        raise AuthError("This code has expired. Request a new one.")

    attempts = await redis.incr(_attempts_key(purpose, email))
    if attempts == 1:
        await redis.expire(_attempts_key(purpose, email), CODE_TTL)
    if attempts > MAX_VERIFY_ATTEMPTS:
        await redis.delete(_code_key(purpose, email), _attempts_key(purpose, email))
        raise RateLimitError("Too many attempts. Request a new code.")

    if not secrets.compare_digest(stored, code):
        raise AuthError("Invalid code.")

    await redis.delete(_code_key(purpose, email), _attempts_key(purpose, email))
