"""Phase 12 uptime — SSRF guard, check flow, incident/alert state machine.

Covers the unforgiving paths: alert-once-per-incident, recover notice, flapping
doesn't spam, alerts never route through the marketing gate, SSRF targets (incl.
redirect-to-internal) are refused, and the read endpoint is ownership-scoped.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import create_access_token
from app.models.tables import Account, Site, UptimeIncident, UptimeMonitor
from app.services import uptime

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


# --- SSRF guard -----------------------------------------------------------
@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.0.0.1", "192.168.1.5", "172.16.0.9", "169.254.169.254", "::1", "0.0.0.0"],
)
def test_is_blocked_ip_refuses_internal(ip: str) -> None:
    assert uptime._is_blocked_ip(ip) is True


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34"])
def test_is_blocked_ip_allows_public(ip: str) -> None:
    assert uptime._is_blocked_ip(ip) is False


def test_ipv4_mapped_ipv6_is_unwrapped_and_blocked() -> None:
    # ::ffff:10.0.0.1 must not sneak past as a "global" v6 address.
    assert uptime._is_blocked_ip("::ffff:10.0.0.1") is True


async def test_screen_host_blocks_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_resolve(host: str) -> list[str]:
        return ["10.0.0.5"]

    monkeypatch.setattr(uptime, "_resolve", fake_resolve)
    assert await uptime._screen_host("intranet.example") == "blocked"


async def test_screen_host_dns_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    async def boom(host: str) -> list[str]:
        raise socket.gaierror("nope")

    monkeypatch.setattr(uptime, "_resolve", boom)
    assert await uptime._screen_host("nx.example") == "dns"


async def test_screen_host_allows_public(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_resolve(host: str) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr(uptime, "_resolve", fake_resolve)
    assert await uptime._screen_host("example.com") == ""


# --- Check flow -----------------------------------------------------------
def _mock_client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


async def test_check_url_up_on_200(monkeypatch: pytest.MonkeyPatch) -> None:
    async def public(host: str) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr(uptime, "_resolve", public)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    async with _mock_client(handler) as client:
        result = await uptime._check_url(client, "https://example.com", 3)
    assert result.ok and result.status_code == 200 and result.cause == ""


async def test_check_url_down_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uptime, "_resolve", lambda h: _ret(["93.184.216.34"]))

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with _mock_client(handler) as client:
        result = await uptime._check_url(client, "https://example.com", 3)
    assert not result.ok and result.status_code == 503 and result.cause == "http_5xx"


async def test_check_url_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uptime, "_resolve", lambda h: _ret(["93.184.216.34"]))

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=req)

    async with _mock_client(handler) as client:
        result = await uptime._check_url(client, "https://example.com", 3)
    assert not result.ok and result.cause == "timeout"


async def test_redirect_to_internal_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # example.com resolves public but 302s to an internal host — the classic SSRF
    # bypass. Each hop is re-screened, so the internal target is refused.
    async def resolve(host: str) -> list[str]:
        return ["10.1.2.3"] if host == "metadata.internal" else ["93.184.216.34"]

    monkeypatch.setattr(uptime, "_resolve", resolve)

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "example.com":
            return httpx.Response(302, headers={"location": "http://metadata.internal/"})
        return httpx.Response(200)

    async with _mock_client(handler) as client:
        result = await uptime._check_url(client, "https://example.com", 3)
    assert not result.ok and result.cause == "blocked"


async def _ret(v: list[str]) -> list[str]:
    return v


# --- State machine + alerts ----------------------------------------------
class _Mailer:
    """Records transactional uptime sends so tests can assert alert-once."""

    def __init__(self) -> None:
        self.down: list[tuple[str, str, str]] = []
        self.up: list[tuple[str, str]] = []

    async def send_down(self, to: str, domain: str, cause: str) -> None:
        self.down.append((to, domain, cause))

    async def send_up(self, to: str, domain: str) -> None:
        self.up.append((to, domain))


async def _seed_site(
    session_factory: async_sessionmaker[AsyncSession], *, verified: bool = True, opted_out: bool = False
) -> UUID:
    async with session_factory() as s:
        acc = Account(
            email="owner@example.com",
            username="owner",
            status="active",
            email_verified_at=NOW if verified else None,
            email_opt_out=opted_out,
        )
        s.add(acc)
        await s.flush()
        site = Site(account_id=acc.id, site_id="pub0", domain="example.com")
        s.add(site)
        await s.commit()
        return site.id


def _install_mailer(monkeypatch: pytest.MonkeyPatch) -> _Mailer:
    mailer = _Mailer()
    monkeypatch.setattr(uptime.email, "send_uptime_down_email", mailer.send_down)
    monkeypatch.setattr(uptime.email, "send_uptime_up_email", mailer.send_up)
    return mailer


DOWN = uptime.CheckResult(False, None, "connect")
UP = uptime.CheckResult(True, 200, "")


async def test_down_alerts_once_at_threshold_then_stays_silent(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    site_id = await _seed_site(session_factory)
    mailer = _install_mailer(monkeypatch)
    async with session_factory() as s:
        site = await s.get(Site, site_id)
        assert site is not None
        # Threshold is 2: first failure is below the alarm line (retry-before-alarm).
        await uptime.process_result(s, site, DOWN, NOW)
        assert mailer.down == []
        assert (await s.scalar(select(UptimeMonitor.status))) == "unknown"
        # Second consecutive failure opens the incident + fires exactly one alert.
        await uptime.process_result(s, site, DOWN, NOW)
        assert len(mailer.down) == 1
        assert (await s.scalar(select(UptimeMonitor.status))) == "down"
        # Third failure: incident already open → no new alert.
        await uptime.process_result(s, site, DOWN, NOW)
        assert len(mailer.down) == 1
        assert (await s.scalar(select(UptimeIncident).where(UptimeIncident.resolved_at.is_(None)))) is not None


async def test_recovery_resolves_incident_and_notifies_once(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    site_id = await _seed_site(session_factory)
    mailer = _install_mailer(monkeypatch)
    async with session_factory() as s:
        site = await s.get(Site, site_id)
        assert site is not None
        await uptime.process_result(s, site, DOWN, NOW)
        await uptime.process_result(s, site, DOWN, NOW)  # incident open
        assert len(mailer.down) == 1
        # Recovery: resolves the incident, flips to up, one recovery email.
        await uptime.process_result(s, site, UP, NOW)
        assert len(mailer.up) == 1
        assert (await s.scalar(select(UptimeMonitor.status))) == "up"
        incident = await s.scalar(select(UptimeIncident))
        assert incident is not None and incident.resolved_at is not None
        # A second passing check does not re-notify.
        await uptime.process_result(s, site, UP, NOW)
        assert len(mailer.up) == 1


async def test_single_blip_below_threshold_never_alerts(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    site_id = await _seed_site(session_factory)
    mailer = _install_mailer(monkeypatch)
    async with session_factory() as s:
        site = await s.get(Site, site_id)
        assert site is not None
        await uptime.process_result(s, site, DOWN, NOW)  # streak 1, below threshold
        await uptime.process_result(s, site, UP, NOW)  # recovers before alarming
        assert mailer.down == [] and mailer.up == []
        assert (await s.scalar(select(UptimeIncident))) is None


async def test_alert_bypasses_marketing_gate_even_when_opted_out(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Uptime alerts are transactional: an opted-out owner still gets them, and the
    # marketing gate is never invoked.
    from app.services import notifications

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("uptime must not route through the marketing gate")

    monkeypatch.setattr(notifications, "send_marketing_email", boom)
    site_id = await _seed_site(session_factory, opted_out=True)
    mailer = _install_mailer(monkeypatch)
    async with session_factory() as s:
        site = await s.get(Site, site_id)
        assert site is not None
        await uptime.process_result(s, site, DOWN, NOW)
        await uptime.process_result(s, site, DOWN, NOW)
    assert len(mailer.down) == 1  # delivered despite opt-out


async def test_unverified_owner_is_not_emailed(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    site_id = await _seed_site(session_factory, verified=False)
    mailer = _install_mailer(monkeypatch)
    async with session_factory() as s:
        site = await s.get(Site, site_id)
        assert site is not None
        await uptime.process_result(s, site, DOWN, NOW)
        await uptime.process_result(s, site, DOWN, NOW)
    # Incident still tracked, but no email to an unconfirmed address.
    assert mailer.down == []


async def test_blocked_result_does_not_open_incident(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    site_id = await _seed_site(session_factory)
    mailer = _install_mailer(monkeypatch)
    blocked = uptime.CheckResult(False, None, "blocked")
    async with session_factory() as s:
        site = await s.get(Site, site_id)
        assert site is not None
        await uptime.process_result(s, site, blocked, NOW)
        await uptime.process_result(s, site, blocked, NOW)
    # An SSRF-refused internal target is a misconfig, not an outage: no alert.
    assert mailer.down == []
    async with session_factory() as s:
        assert (await s.scalar(select(UptimeIncident))) is None


# --- Read endpoint (ownership) -------------------------------------------
async def test_uptime_endpoint_is_ownership_scoped(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as s:
        owner = Account(email="o@e.com", username="owner")
        other = Account(email="x@e.com", username="other")
        s.add_all([owner, other])
        await s.flush()
        s.add(Site(account_id=owner.id, site_id="mine", domain="a.com"))
        s.add(Site(account_id=other.id, site_id="theirs", domain="b.com"))
        await s.commit()
        owner_id = owner.id

    token = create_access_token(owner_id)
    headers = {"Authorization": f"Bearer {token}"}

    ok = await client.get("/sites/mine/uptime", headers=headers)
    assert ok.status_code == 200
    assert ok.json()["status"] == "unknown"  # never checked yet

    leak = await client.get("/sites/theirs/uptime", headers=headers)
    assert leak.status_code == 404  # foreign site: 404, never revealed
