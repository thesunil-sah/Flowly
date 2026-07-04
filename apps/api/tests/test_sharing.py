"""services/sharing.py — share-link lifecycle + resolution (§8).

Locks the security-relevant behavior: a live token resolves to exactly its site,
rotating mints a new token and kills the old one, and revocation stops the link.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.tables import Account, Site
from app.services import sharing


async def _make_site(session: AsyncSession, site_id: str = "pub0", domain: str = "a.com") -> Site:
    acc = Account(email=f"{site_id}@e.com", username=site_id)
    session.add(acc)
    await session.flush()
    site = Site(account_id=acc.id, site_id=site_id, domain=domain)
    session.add(site)
    await session.commit()
    return site


async def test_create_share_resolves_to_its_site(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        site = await _make_site(s)
        token = await sharing.create_share(s, site)
        resolved = await sharing.resolve_share(s, token.token)
        assert resolved is not None
        assert resolved.site_id == "pub0"


async def test_rotate_revokes_the_previous_link(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        site = await _make_site(s)
        t1 = await sharing.create_share(s, site)
        t2 = await sharing.create_share(s, site)
        assert t1.token != t2.token
        assert await sharing.resolve_share(s, t1.token) is None  # old link dead
        assert (await sharing.resolve_share(s, t2.token)).site_id == "pub0"
        active = await sharing.active_share(s, site)
        assert active is not None and active.token == t2.token


async def test_revoke_disables_the_link(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        site = await _make_site(s)
        token = await sharing.create_share(s, site)
        await sharing.revoke_shares(s, site)
        assert await sharing.resolve_share(s, token.token) is None
        assert await sharing.active_share(s, site) is None


async def test_resolve_unknown_token_is_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as s:
        assert await sharing.resolve_share(s, "does-not-exist") is None


async def test_token_maps_only_to_its_own_site(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Two sites, two tokens: each token resolves strictly to its own site.
    async with session_factory() as s:
        site_a = await _make_site(s, "pubA", "a.com")
        site_b = await _make_site(s, "pubB", "b.com")
        ta = await sharing.create_share(s, site_a)
        tb = await sharing.create_share(s, site_b)
        assert (await sharing.resolve_share(s, ta.token)).site_id == "pubA"
        assert (await sharing.resolve_share(s, tb.token)).site_id == "pubB"
