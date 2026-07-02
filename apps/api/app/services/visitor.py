"""Cookieless visitor identification (CLAUDE.md — privacy is the product).

`visitor_hash` = SHA-256 of ``pepper + daily_salt + site_id + ip + ua``:

  - **Deterministic** (stdlib `hashlib`, not argon2) so the same visitor maps to
    the same id within a day — that's what makes unique-visitor counts work.
  - **Salt rotates every 24h** (`salt:{YYYYMMDD}` in Redis), so the id cannot be
    linked across days once the salt expires — no persistent fingerprint.
  - **site_id is mixed in**, so the same person on two sites gets different ids
    (tenant isolation).
  - The **pepper** (`VISITOR_SALT_SECRET`) adds a secret not stored in Redis, so
    a Redis dump alone can't reconstruct hashes.

The raw IP is an input only; it is never stored or logged. The daily salt is
random per day (not derivable from the date) and created atomically so
concurrent first-requests converge on one value.
"""

import hashlib
import secrets
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.config import settings

# Live a little over 24h so a salt minted just before UTC midnight still covers
# its whole day; a fresh key is minted each new UTC date regardless.
_SALT_TTL_SECONDS = 60 * 60 * 25
_SALT_BYTES = 16

# Per-process cache of (date_str, salt) to avoid a Redis round-trip per event.
_cached: tuple[str, str] | None = None


def _today() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")


def _salt_key(date_str: str) -> str:
    return f"salt:{date_str}"


async def get_daily_salt(redis: Redis) -> str:
    """Return today's rotating salt, creating it atomically on first use."""
    global _cached
    date_str = _today()
    if _cached is not None and _cached[0] == date_str:
        return _cached[1]

    key = _salt_key(date_str)
    # SET NX: only the first caller writes; everyone else reads that value, so
    # concurrent creators converge on a single salt for the day.
    candidate = secrets.token_hex(_SALT_BYTES)
    created = await redis.set(key, candidate, ex=_SALT_TTL_SECONDS, nx=True)
    salt = candidate if created else await redis.get(key)
    # Extremely unlikely race: key expired between SET and GET — fall back to
    # our candidate rather than returning None.
    salt = salt or candidate
    _cached = (date_str, salt)
    return salt


def visitor_hash(ip: str, ua: str, site_id: str, salt: str) -> str:
    """Deterministic, daily-scoped, per-site anonymous visitor id (hex)."""
    pepper = settings.visitor_salt_secret
    material = f"{pepper}|{salt}|{site_id}|{ip}|{ua}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _reset_cache() -> None:
    """Test hook: clear the in-process salt cache."""
    global _cached
    _cached = None
