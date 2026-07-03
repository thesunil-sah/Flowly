"""Live traffic — the site list + the real-time WebSocket (CLAUDE.md §3).

Two authed, ownership-scoped surfaces on the private dashboard API:

  - ``GET /sites``          the caller's sites (so the dashboard can pick one).
  - ``WS  /live/{site_id}`` the live stream: a count snapshot, then per-event
    pushes and a periodic count heartbeat.

The router stays thin: it authenticates, verifies ownership, and forwards
whatever `services/live.py` yields. A browser WebSocket can't send an
`Authorization` header, so the access token arrives as a `?token=` query param
and is verified with `decode_token` (never logged). The socket is closed with
policy code 1008 on a bad origin, bad token, a site the account doesn't own —
the #1 multi-tenant leak path (CLAUDE.md §9) — or once the access token expires.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppError
from app.core.security import CurrentUser, access_token_expiry, decode_token
from app.db import postgres
from app.db.postgres import get_session
from app.db.redis import get_client
from app.models.schemas import SiteOut
from app.services import live

logger = logging.getLogger("flowly.live")

router = APIRouter(tags=["live"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Message sender: serializes writes so concurrent tasks can't interleave frames.
Sender = Callable[[dict[str, object]], Awaitable[None]]

# Policy-violation close code; used for every auth/ownership/origin rejection so
# a client can't distinguish "bad token" from "not your site".
_WS_POLICY_VIOLATION = 1008
_HEARTBEAT_SECONDS = 10


def _normalize_origin(value: str | None) -> str | None:
    """Canonicalize an incoming `Origin` header for comparison, or None if absent.

    A browser `Origin` is `scheme://host[:port]` with no path — case-insensitive,
    no trailing slash — so we lowercase and strip. The allowed value it's compared
    against (`settings.web_base_url`) is already canonicalized at config load, so
    both sides meet in the same normal form.
    """
    if not value:
        return None
    return value.strip().lower().rstrip("/")


# The only Origin allowed to open a live socket. Already canonical (config
# normalizes WEB_BASE_URL), so it needs no further processing here.
_ALLOWED_ORIGIN = settings.web_base_url


@router.get("/sites")
async def list_sites(account: CurrentUser, session: SessionDep) -> list[SiteOut]:
    """The authenticated account's sites (ownership-scoped)."""
    sites = await live.list_account_sites(session, account.id)
    return [SiteOut.model_validate(s) for s in sites]


async def _authorize(ws: WebSocket, site_id: str) -> str | None:
    """Origin + token + ownership. Returns the validated token, else closes.

    Assumes `ws.accept()` has run so we can send a close code on rejection. A
    non-None return is the verified access token (needed for the expiry watchdog).
    """
    if _normalize_origin(ws.headers.get("origin")) != _ALLOWED_ORIGIN:
        await ws.close(code=_WS_POLICY_VIOLATION)
        return None

    token = ws.query_params.get("token")
    try:
        account_id = decode_token(token or "", "access")
    except AppError:
        await ws.close(code=_WS_POLICY_VIOLATION)
        return None

    # Ownership check on its own short-lived session — released before the
    # (Redis-only) streaming loop so no Postgres connection is pinned per socket.
    async with postgres.async_session_factory() as session:
        site = await live.get_owned_site(session, site_id, account_id)
    if site is None:
        await ws.close(code=_WS_POLICY_VIOLATION)
        return None
    return token


async def _forward(send: Sender, site_id: str) -> None:
    """Send the initial snapshot (once subscribed), then push each live event."""

    async def send_snapshot() -> None:
        now = datetime.now(UTC).timestamp()
        await send(
            {"type": "snapshot", "count": await live.count_active(get_client(), site_id, now)}
        )

    async for event in live.subscribe_events(site_id, on_ready=send_snapshot):
        await send({"type": "event", **event})


async def _heartbeat(send: Sender, site_id: str) -> None:
    """Periodically resend the live count so idle decay shows without traffic."""
    while True:
        await asyncio.sleep(_HEARTBEAT_SECONDS)
        now = datetime.now(UTC).timestamp()
        await send({"type": "count", "count": await live.count_active(get_client(), site_id, now)})


async def _receive_until_disconnect(ws: WebSocket) -> None:
    """Drain client frames so a disconnect is noticed promptly (not just on send)."""
    while True:
        await ws.receive_text()


async def _close_on_token_expiry(send_lock: asyncio.Lock, ws: WebSocket, token: str) -> None:
    """Close the socket (1008) when the access token expires.

    The socket can outlive the short access-token TTL; closing with 1008 makes
    the client refresh its token and reconnect. Takes the send lock so the close
    frame can't interleave with an in-flight `send`.
    """
    remaining = (access_token_expiry(token) - datetime.now(UTC)).total_seconds()
    if remaining > 0:
        await asyncio.sleep(remaining)
    async with send_lock:
        await ws.close(code=_WS_POLICY_VIOLATION)


@router.websocket("/live/{site_id}")
async def live_ws(ws: WebSocket, site_id: str) -> None:
    await ws.accept()
    token = await _authorize(ws, site_id)
    if token is None:
        return

    # One lock funnels every write: _forward, _heartbeat, and the expiry close
    # all send through here, so no two coroutines are in the socket at once.
    send_lock = asyncio.Lock()

    async def send(message: dict[str, object]) -> None:
        async with send_lock:
            await ws.send_json(message)

    tasks = [
        asyncio.create_task(_forward(send, site_id)),
        asyncio.create_task(_heartbeat(send, site_id)),
        asyncio.create_task(_receive_until_disconnect(ws)),
        asyncio.create_task(_close_on_token_expiry(send_lock, ws, token)),
    ]
    try:
        # First task to finish means the socket ended (client disconnect, send
        # failure, channel close, or token expiry) — tear the rest down.
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        # Surface a genuine failure (e.g. Redis down mid-stream) instead of
        # swallowing it; a client disconnect is expected, so it's not logged.
        for result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(result, Exception) and not isinstance(result, WebSocketDisconnect):
                logger.warning("live socket task failed (site=%s): %r", site_id, result)
