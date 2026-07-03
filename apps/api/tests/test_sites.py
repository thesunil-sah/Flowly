"""GET /sites — authed and ownership-scoped."""

from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token
from app.models.tables import Account, Site


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    """Create an owner with two sites plus a foreign account with one site."""
    async with session_factory() as s:
        owner = Account(email="owner@example.com", username="owner")
        s.add(owner)
        await s.flush()
        owner_id = owner.id
        s.add(Site(account_id=owner_id, site_id="pub0", domain="a.com"))
        s.add(Site(account_id=owner_id, site_id="pub1", domain="b.com"))

        other = Account(email="other@example.com", username="other")
        s.add(other)
        await s.flush()
        s.add(Site(account_id=other.id, site_id="foreign", domain="c.com"))
        await s.commit()
    return owner_id


async def test_list_sites_is_ownership_scoped(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_id = await _seed(session_factory)
    token = create_access_token(owner_id)
    resp = await client.get("/sites", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    site_ids = {row["site_id"] for row in resp.json()}
    assert site_ids == {"pub0", "pub1"}  # foreign site excluded


async def test_list_sites_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/sites")
    assert resp.status_code == 401
