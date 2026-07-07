"""Shared test fixtures.

Auth logic is exercised against in-memory SQLite + fake Redis so the suite runs
anywhere (local + CI) without external services. The migration test
(test_migration.py) separately runs the real Alembic script.
"""

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.postgres import get_session
from app.db.redis import get_redis
from app.main import app
from app.models.base import Base


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    # StaticPool keeps one shared in-memory DB across connections for the test.
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    """The fake Redis the `client` app uses — exposed so a test can seed usage
    counters (Phase 14 paywall) or presence and see the same store the app reads."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield fake
    await fake.aclose()


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    redis_client: fakeredis.aioredis.FakeRedis,
) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    async def override_redis() -> fakeredis.aioredis.FakeRedis:
        return redis_client

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_redis] = override_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
