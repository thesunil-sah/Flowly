from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.clickhouse import close_clickhouse
from app.db.postgres import dispose_engine
from app.db.redis import close_redis
from app.routers import (
    account,
    assistant,
    auth,
    billing,
    collect,
    contact,
    email,
    goals,
    health,
    live,
    oauth,
    public,
    searchconsole,
    sites,
    stats,
)


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
    # Authed self-service account settings (profile/password/email/delete), F3.
    app.include_router(account.router)
    # Authed dashboard surfaces (live counter/feed), under the locked CORS above.
    app.include_router(live.router)
    # Authed site onboarding: add a site, get its snippet, verify the install.
    app.include_router(sites.router)
    # Authed, ownership-scoped historical reports (queries ClickHouse).
    app.include_router(stats.router)
    # Premium (Phase 15): custom-event reports + conversion goals — paid-gated.
    app.include_router(goals.router)
    # Authed Search Console connect/reports + public Google OAuth callback (F13).
    app.include_router(searchconsole.router)
    # Public, token-scoped read-only shared dashboards (§8) — no auth, one site.
    app.include_router(public.router)
    # Billing: authed checkout/portal/usage under the locked CORS + a public,
    # signature-verified Stripe webhook (server-to-server, no CORS concern).
    app.include_router(billing.router)
    # Public one-click unsubscribe (signed-token authed) for growth email (§8).
    app.include_router(email.router)
    # Public contact form (honeypot + per-IP rate limit), transactional mail.
    app.include_router(contact.router)
    # Public support chatbot: hardcoded FAQ intents + rate-limited AI fallback.
    app.include_router(assistant.router)
    # Public, open-CORS ingestion endpoint (its own ACAO:* header, set per
    # response — the global CORS middleware above stays locked to the dashboard).
    app.include_router(collect.router)
    return app


app = create_app()
