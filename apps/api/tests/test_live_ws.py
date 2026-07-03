"""WS /live/{site_id} — auth, origin, ownership, and the event stream.

Uses the sync Starlette TestClient (websocket support). The Postgres session
factory is neutralized and `get_owned_site` is patched per test, so these run
without a database. Redis is a shared fakeredis wired into BOTH the injected
dependency (used by /collect) and the module client (used by the WS pub/sub),
so a /collect publish reaches the socket. TestClient runs the app on one portal
loop, so the publish and the subscriber share an event loop.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import app.db.redis as redis_mod
import app.routers.live as live_router
import fakeredis.aioredis
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.core.security import create_access_token
from app.db import postgres
from app.db.redis import get_redis
from app.main import app
from app.services import sites, visitor

ORIGIN = settings.web_base_url
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
COLLECT_BODY = '{"site_id":"demo","path":"/pricing","referrer":"","screen_w":800}'


class _NullSession:
    """Stand-in for an AsyncSession context manager; get_owned_site is patched."""

    async def __aenter__(self) -> "_NullSession":
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.aioredis.FakeRedis:
    visitor._reset_cache()
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_mod, "_client", fake)  # used by the WS (get_client)
    app.dependency_overrides[get_redis] = lambda: fake  # used by /collect
    monkeypatch.setattr(postgres, "async_session_factory", lambda: _NullSession())
    yield fake
    app.dependency_overrides.clear()


def _url(*, site: str = "demo", token: str | None = None) -> str:
    tok = token if token is not None else create_access_token(uuid4())
    return f"/live/{site}?token={tok}"


def _own(monkeypatch: pytest.MonkeyPatch, *, owned: bool) -> None:
    async def _get_owned_site(*_: object) -> object | None:
        return object() if owned else None

    monkeypatch.setattr(sites, "get_owned_site", _get_owned_site)


def test_bad_origin_is_rejected(fake_redis) -> None:
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as exc:
            with c.websocket_connect(_url(), headers={"origin": "http://evil.example"}) as ws:
                ws.receive_json()
    assert exc.value.code == 1008


def test_missing_token_is_rejected(fake_redis) -> None:
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as exc:
            with c.websocket_connect("/live/demo", headers={"origin": ORIGIN}) as ws:
                ws.receive_json()
    assert exc.value.code == 1008


def test_invalid_token_is_rejected(fake_redis) -> None:
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as exc:
            with c.websocket_connect(_url(token="not-a-jwt"), headers={"origin": ORIGIN}) as ws:
                ws.receive_json()
    assert exc.value.code == 1008


def test_unowned_site_is_rejected(fake_redis, monkeypatch: pytest.MonkeyPatch) -> None:
    _own(monkeypatch, owned=False)
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as exc:
            with c.websocket_connect(_url(), headers={"origin": ORIGIN}) as ws:
                ws.receive_json()
    assert exc.value.code == 1008


def test_owned_site_streams_snapshot_then_event(
    fake_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    _own(monkeypatch, owned=True)
    with TestClient(app) as c:
        with c.websocket_connect(_url(), headers={"origin": ORIGIN}) as ws:
            snapshot = ws.receive_json()
            assert snapshot["type"] == "snapshot"
            assert snapshot["count"] == 0

            # Publish a real event through /collect (same fake + same loop).
            resp = c.post(
                "/collect",
                content=COLLECT_BODY,
                headers={
                    "content-type": "text/plain",
                    "user-agent": CHROME,
                    "origin": "https://demo.example",
                },
            )
            assert resp.status_code == 202

            event = ws.receive_json()
            assert event["type"] == "event"
            assert event["path"] == "/pricing"
            assert "visitor_hash" not in event


@pytest.mark.parametrize("variant", [ORIGIN + "/", ORIGIN.upper()])
def test_origin_normalization_accepts_equivalent_forms(
    fake_redis, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    # A trailing slash or mixed case on the Origin (or the configured
    # web_base_url) must not reject an otherwise-valid socket. (Whitespace
    # stripping is covered at the config layer, where the env var is parsed.)
    _own(monkeypatch, owned=True)
    with TestClient(app) as c:
        with c.websocket_connect(_url(), headers={"origin": variant}) as ws:
            assert ws.receive_json()["type"] == "snapshot"


def test_scheme_mismatch_is_still_rejected(fake_redis, monkeypatch: pytest.MonkeyPatch) -> None:
    # Normalization must not paper over http-vs-https — that's a real config error.
    _own(monkeypatch, owned=True)
    other_scheme = (
        "http://" + ORIGIN[len("https://") :]
        if ORIGIN.startswith("https://")
        else "https://" + ORIGIN[len("http://") :]
    )
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as exc:
            with c.websocket_connect(_url(), headers={"origin": other_scheme}) as ws:
                ws.receive_json()
    assert exc.value.code == 1008


def test_expired_token_closes_socket(fake_redis, monkeypatch: pytest.MonkeyPatch) -> None:
    _own(monkeypatch, owned=True)
    # Token already expired -> the watchdog closes the socket with 1008.
    monkeypatch.setattr(
        live_router,
        "access_token_expiry",
        lambda _t: datetime.now(UTC) - timedelta(seconds=1),
    )
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as exc:
            with c.websocket_connect(_url(), headers={"origin": ORIGIN}) as ws:
                # A snapshot may arrive before the expiry close; drain until it closes.
                for _ in range(5):
                    ws.receive_json()
    assert exc.value.code == 1008
