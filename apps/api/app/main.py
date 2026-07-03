from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.clickhouse import close_clickhouse
from app.db.postgres import dispose_engine
from app.db.redis import close_redis
from app.routers import auth, collect, health, live, oauth, stats


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # No startup DB ping: `/health` must stay zero-I/O and pass with no Postgres.
    # Clients connect lazily on first use.
    yield
    await dispose_engine()
    await close_redis()
    await close_clickhouse()


def create_app() -> FastAPI:
    app = FastAPI(title="Flowly API", version="0.1.0", lifespan=lifespan)

    # Dashboard API is private: CORS is locked to the web origin. (The public,
    # open-CORS `/collect` endpoint arrives in Phase 3 as a separate concern.)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(oauth.router)
    # Authed dashboard surfaces (live counter/feed + site list), under the
    # locked CORS above.
    app.include_router(live.router)
    # Authed, ownership-scoped historical reports (queries ClickHouse).
    app.include_router(stats.router)
    # Public, open-CORS ingestion endpoint (its own ACAO:* header, set per
    # response — the global CORS middleware above stays locked to the dashboard).
    app.include_router(collect.router)
    return app


app = create_app()
