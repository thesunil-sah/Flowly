"""Public dashboard share links (§8, Phase 8).

A share link exposes ONE site's dashboard read-only to anyone holding the URL.
The token is therefore a bearer-grade secret (unlike the public, non-secret
`site_id`): minted with `secrets.token_urlsafe`, stored, and revocable.

Design (chosen: open link, revocable):
  - `create_share` mints a fresh token and revokes any prior active ones, so a
    site has at most one live link and "rotate" is just a re-create.
  - Revocation is soft (`revoked_at`); `resolve_share` only ever returns a site
    for a token whose row is present and not revoked.
The account-facing mutations are ownership-checked in the router *before* calling
here (the caller passes an already-owned Site); `resolve_share` is the public
read path and deliberately takes only the token.
"""

import secrets
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tables import ShareToken, Site

# token_urlsafe(24) -> 32 URL-safe chars (192 bits) — no realistic collision;
# the UNIQUE index is the guarantee. Comfortably within String(64).
_TOKEN_BYTES = 24


def _new_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def share_url(token: str) -> str:
    """The viewer-facing URL for a share token (served by the web app)."""
    return f"{settings.web_base_url}/share/{token}"


async def _active_tokens(session: AsyncSession, site_pk: object) -> Sequence[ShareToken]:
    result = await session.scalars(
        select(ShareToken).where(ShareToken.site_id == site_pk, ShareToken.revoked_at.is_(None))
    )
    return result.all()


async def active_share(session: AsyncSession, site: Site) -> ShareToken | None:
    """The site's current live share link, if any (newest wins)."""
    tokens = await _active_tokens(session, site.id)
    return max(tokens, key=lambda t: t.created_at) if tokens else None


async def create_share(session: AsyncSession, site: Site) -> ShareToken:
    """Mint a fresh share link for an (already-owned) site, revoking prior ones.

    At most one link is ever live per site, so this doubles as "rotate": callers
    that want a new URL just call it again.
    """
    now = datetime.now(UTC)
    for existing in await _active_tokens(session, site.id):
        existing.revoked_at = now
    token = ShareToken(token=_new_token(), site_id=site.id)
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token


async def revoke_shares(session: AsyncSession, site: Site) -> None:
    """Disable all of a site's share links (the public link stops resolving)."""
    now = datetime.now(UTC)
    for existing in await _active_tokens(session, site.id):
        existing.revoked_at = now
    await session.commit()


async def resolve_share(session: AsyncSession, token: str) -> Site | None:
    """Public read path: token -> its Site, iff the token is live (not revoked).

    Returns None for an unknown or revoked token so the router can 404 without
    revealing which case applied. Never widens beyond the single linked site.
    """
    share = await session.scalar(
        select(ShareToken).where(ShareToken.token == token, ShareToken.revoked_at.is_(None))
    )
    if share is None:
        return None
    return await session.get(Site, share.site_id)
