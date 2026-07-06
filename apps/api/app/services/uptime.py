"""Uptime monitoring — check a site, track incidents, alert the owner (Phase 12).

Layering (§3): all the logic lives here; `workers/uptime.py` only drives the
sweep and `routers/sites.py` only exposes the read model. Three concerns:

  1. **The check** (`check_with_retry` → `_check_url`) — an outbound GET/HEAD to
     the site's domain, with an in-run retry so a single transient blip isn't a
     failure. "Down" means no response / timeout / DNS failure / a 5xx; any
     completed <500 response (incl. 3xx/4xx) means the server is alive.
  2. **The SSRF guard** (`_screen_host`) — `domain` is an *unverified* user label
     (Phase 6), so before every request (and every redirect hop) we resolve the
     host and refuse any non-global address (loopback / private / link-local /
     cloud-metadata …). This is the one genuinely dangerous new surface: without
     it a customer could point us at `169.254.169.254` or `10.0.0.x`.
  3. **State + alerts** (`process_result`) — a per-site `UptimeMonitor` counts
     consecutive failures; once it crosses the threshold an `UptimeIncident`
     opens and the owner is emailed **once** (down), then once more on recovery.
     The open incident is the idempotency key, so we never alert per failed ping.

Alerts go through `services/email.py` **directly** — they are transactional (a
service alert about the customer's own site) and MUST NOT route through the
marketing opt-out gate (`services/notifications.py`), exactly like verify/reset.
"""

import asyncio
import ipaddress
import logging
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.schemas import UptimeIncidentOut, UptimeStatusOut
from app.models.tables import Account, Site, UptimeIncident, UptimeMonitor
from app.services import email

logger = logging.getLogger("flowly.uptime")

# Short pause before the in-run retry, to ride out a momentary blip without
# turning a healthy site into a false failure.
_RETRY_BACKOFF_SECONDS = 1.0
# How many recent incidents the dashboard read model returns.
_INCIDENT_HISTORY = 10


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one uptime check. `cause` is set only when not `ok`."""

    ok: bool
    status_code: int | None
    cause: str  # "" | "timeout" | "connect" | "dns" | "http_5xx" | "blocked"


# --- SSRF guard -----------------------------------------------------------
def _is_blocked_ip(ip: str) -> bool:
    """True if `ip` is anything but a public/global address (SSRF-unsafe).

    `is_global` is False for loopback, private (RFC1918), link-local (incl. the
    169.254.169.254 cloud-metadata address), shared, reserved, multicast and
    unspecified ranges — so a single check covers every internal target. IPv4
    mapped into IPv6 (`::ffff:10.0.0.1`) is unwrapped first so it can't sneak
    past as a "global" v6 address.
    """
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return not addr.is_global


async def _resolve(host: str) -> list[str]:
    """Resolve `host` to its IP strings via the event loop's resolver.

    Split out so tests can substitute DNS without touching the network. Raises
    `socket.gaierror` when the host doesn't resolve.
    """
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


async def _screen_host(host: str) -> str:
    """Resolve `host` and screen every address. Returns "" if safe to fetch.

    A non-empty return is the *cause*: "dns" (doesn't resolve → really
    unreachable) or "blocked" (resolves to an internal address → we refuse to
    fetch it, SSRF). Every resolved address must be public — a host with even one
    internal address is refused, closing the split-horizon / rebinding trick.
    """
    if not host:
        return "dns"
    try:
        ips = await _resolve(host)
    except socket.gaierror:
        return "dns"
    if not ips:
        return "dns"
    for ip in ips:
        try:
            if _is_blocked_ip(ip):
                return "blocked"
        except ValueError:  # unparseable address — refuse rather than risk it
            return "blocked"
    return ""


# --- The check ------------------------------------------------------------
async def _request(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """HEAD the URL (cheap — no body), falling back to GET if HEAD is refused."""
    resp = await client.request("HEAD", url)
    if resp.status_code in (405, 501):  # method not allowed / not implemented
        resp = await client.request("GET", url)
    return resp


async def _check_url(client: httpx.AsyncClient, url: str, max_redirects: int) -> CheckResult:
    """Follow up to `max_redirects` hops manually, re-screening each host.

    Auto-following redirects would let a public host 302 us to an internal one
    (the classic SSRF bypass), so redirects are followed by hand and each target
    goes back through `_screen_host` before we connect.
    """
    current = url
    for _ in range(max_redirects + 1):
        host = urlparse(current).hostname or ""
        cause = await _screen_host(host)
        if cause:
            return CheckResult(False, None, cause)
        try:
            resp = await _request(client, current)
        except httpx.TimeoutException:
            return CheckResult(False, None, "timeout")
        except httpx.HTTPError:
            return CheckResult(False, None, "connect")
        if resp.is_redirect and "location" in resp.headers:
            current = urljoin(current, resp.headers["location"])
            continue
        if resp.status_code >= 500:
            return CheckResult(False, resp.status_code, "http_5xx")
        return CheckResult(True, resp.status_code, "")
    # Exhausted the redirect budget: the server is clearly responding, just
    # bouncing — count it up rather than a false outage.
    return CheckResult(True, None, "")


async def check_domain(domain: str) -> CheckResult:
    """One uptime check of `https://{domain}` (no DB, safe to run concurrently)."""
    async with httpx.AsyncClient(
        timeout=settings.uptime_check_timeout,
        follow_redirects=False,
        # Never send credentials/cookies; identify ourselves honestly.
        headers={"User-Agent": "FlowlyUptimeBot/1.0 (+https://flowly.local)"},
    ) as client:
        return await _check_url(client, f"https://{domain}", settings.uptime_max_redirects)


async def check_with_retry(domain: str) -> CheckResult:
    """Check `domain`; on failure retry once after a short pause (blip filter).

    A "blocked" result is not retried — an internal address won't become public,
    and we must not keep probing it.
    """
    result = await check_domain(domain)
    if result.ok or result.cause == "blocked":
        return result
    await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
    return await check_domain(domain)


# --- State + alerts -------------------------------------------------------
async def _get_or_create_monitor(session: AsyncSession, site: Site, now: datetime) -> UptimeMonitor:
    monitor = await session.scalar(select(UptimeMonitor).where(UptimeMonitor.site_id == site.id))
    if monitor is None:
        monitor = UptimeMonitor(site_id=site.id, status="unknown", fail_streak=0, updated_at=now)
        session.add(monitor)
    return monitor


async def _open_incident(session: AsyncSession, site: Site) -> UptimeIncident | None:
    """The site's currently-open (unresolved) incident, if any."""
    return await session.scalar(
        select(UptimeIncident)
        .where(UptimeIncident.site_id == site.id, UptimeIncident.resolved_at.is_(None))
        .order_by(UptimeIncident.started_at.desc())
    )


async def _alert(coro: object, site_id: str, kind: str) -> bool:
    """Await a best-effort alert send; log + swallow failures. True on success.

    A failed send leaves the incident's notified flag false so the next run
    retries — one incident still yields (eventually) one alert.
    """
    try:
        await coro  # type: ignore[misc]
        return True
    except Exception:
        logger.exception("uptime %s alert failed for site %s", kind, site_id)
        return False


async def process_result(
    session: AsyncSession, site: Site, result: CheckResult, now: datetime
) -> None:
    """Fold one check result into the site's monitor + incident + alerts.

    Commits its own work. A "blocked" result (SSRF-refused internal target) is
    recorded but never opens an incident or alerts — it's a misconfiguration, not
    an outage, and would be a confusing false "your site is down".
    """
    monitor = await _get_or_create_monitor(session, site, now)
    monitor.last_checked_at = now
    monitor.last_status_code = result.status_code
    monitor.updated_at = now

    if result.cause == "blocked":
        monitor.status = "unknown"
        await session.commit()
        logger.warning(
            "uptime: refused to check site %s (%s → internal address)", site.site_id, site.domain
        )
        return

    if result.ok:
        await _handle_up(session, site, monitor, now)
    else:
        await _handle_down(session, site, monitor, result, now)


async def _recipient_email(session: AsyncSession, site: Site) -> str | None:
    """The owner's email iff verified — we never mail an unconfirmed address."""
    account = await session.get(Account, site.account_id)
    if account is None or account.email_verified_at is None:
        return None
    return account.email


async def _handle_up(
    session: AsyncSession, site: Site, monitor: UptimeMonitor, now: datetime
) -> None:
    monitor.status = "up"
    monitor.fail_streak = 0
    incident = await _open_incident(session, site)
    if incident is not None:
        incident.resolved_at = now
    await session.commit()
    if incident is not None and not incident.notified_up:
        to = await _recipient_email(session, site)
        if to is not None and await _alert(
            email.send_uptime_up_email(to, site.domain), site.site_id, "recovery"
        ):
            incident.notified_up = True
            await session.commit()


async def _handle_down(
    session: AsyncSession,
    site: Site,
    monitor: UptimeMonitor,
    result: CheckResult,
    now: datetime,
) -> None:
    monitor.fail_streak += 1
    incident = await _open_incident(session, site)
    # Retry-before-alarm: only open an incident (and flip to "down") once the
    # streak crosses the threshold, so a lone failed check never pages anyone.
    if incident is None and monitor.fail_streak >= settings.uptime_fail_threshold:
        incident = UptimeIncident(site_id=site.id, started_at=now, cause=result.cause)
        session.add(incident)
        monitor.status = "down"
    await session.commit()
    if incident is not None and not incident.notified_down:
        to = await _recipient_email(session, site)
        if to is not None and await _alert(
            email.send_uptime_down_email(to, site.domain, result.cause), site.site_id, "down"
        ):
            incident.notified_down = True
            await session.commit()


# --- Read model -----------------------------------------------------------
async def get_status(session: AsyncSession, site: Site) -> UptimeStatusOut:
    """Current status + recent incidents for one site (dashboard read)."""
    monitor = await session.scalar(select(UptimeMonitor).where(UptimeMonitor.site_id == site.id))
    incidents = await session.scalars(
        select(UptimeIncident)
        .where(UptimeIncident.site_id == site.id)
        .order_by(UptimeIncident.started_at.desc())
        .limit(_INCIDENT_HISTORY)
    )
    return UptimeStatusOut(
        status=monitor.status if monitor else "unknown",
        last_checked_at=monitor.last_checked_at if monitor else None,
        last_status_code=monitor.last_status_code if monitor else None,
        incidents=[
            UptimeIncidentOut(
                started_at=i.started_at,
                resolved_at=i.resolved_at,
                cause=i.cause,
                ongoing=i.resolved_at is None,
            )
            for i in incidents.all()
        ],
    )


async def sweep(session: AsyncSession, now: datetime | None = None, concurrency: int = 10) -> int:
    """Check every site once and fold in the results. Returns sites processed.

    Network checks run concurrently (bounded) since they're the slow part and
    touch no DB; the state/alert updates are then applied **sequentially** on the
    single AsyncSession (which is not concurrency-safe). One site's failure is
    logged and never aborts the sweep.
    """
    from app.services import sites as sites_svc

    now = now or datetime.now(UTC)
    all_sites = list(await sites_svc.list_all_sites(session))
    if not all_sites:
        return 0

    semaphore = asyncio.Semaphore(concurrency)

    async def _guarded(domain: str) -> CheckResult:
        async with semaphore:
            try:
                return await check_with_retry(domain)
            except Exception:
                logger.exception("uptime check crashed for %s", domain)
                return CheckResult(False, None, "connect")

    results = await asyncio.gather(*(_guarded(s.domain) for s in all_sites))

    processed = 0
    for site, result in zip(all_sites, results):
        try:
            await process_result(session, site, result, now)
            processed += 1
        except Exception:
            await session.rollback()
            logger.exception("uptime state update failed for site %s", site.site_id)
    logger.info("uptime sweep complete; %s sites processed", processed)
    return processed
