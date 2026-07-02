"""Async SQLAlchemy engine + session factory for Postgres.

Client setup only — no business rules (CLAUDE.md §3). Services depend on
`get_session`. The engine is created at import time but connects lazily on
first use, so importing this module does not require a running Postgres
(keeps the zero-I/O `/health` route and its test DB-free).
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped AsyncSession.

    Commits on success, rolls back on error, always closes.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close the connection pool (call on app shutdown)."""
    await engine.dispose()
