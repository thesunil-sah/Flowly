"""Weekly email digest — the per-site summary + its HTML render (§8, Phase 8).

Pure data + rendering: `build_site_digest` reuses the Phase 5 stats builders
(`services/stats.py`) over the last 7 days with a prior-week comparison; there is
no bespoke SQL here (§3). `render_digest` turns one account's site digests into a
`(subject, html, text)` triple. The worker (`workers/digest.py`) owns iteration,
delivery, and idempotency — this module never sends.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html import escape

from clickhouse_connect.driver import AsyncClient

from app.services import stats

# The digest covers the trailing 7 days, compared against the 7 before that.
WINDOW_DAYS = 7
_TOP_N = 5


@dataclass
class SiteDigest:
    """One site's week at a glance."""

    domain: str
    visitors: int
    pageviews: int
    # None when the prior week had no traffic (a percentage vs zero is undefined).
    visitors_change_pct: float | None
    top_pages: list[tuple[str, int]] = field(default_factory=list)
    top_sources: list[tuple[str, int]] = field(default_factory=list)

    @property
    def has_traffic(self) -> bool:
        return self.pageviews > 0


async def build_site_digest(
    client: AsyncClient, site_id: str, domain: str, now: datetime
) -> SiteDigest:
    """Compute a site's trailing-week digest (reuses the stats services)."""
    to = now
    from_ = now - timedelta(days=WINDOW_DAYS)
    overview = await stats.overview(client, site_id, from_, to, compare=True)
    top = await stats.pages(client, site_id, from_, to, "top", _TOP_N)
    srcs = await stats.sources(client, site_id, from_, to, _TOP_N)
    return SiteDigest(
        domain=domain,
        visitors=int(overview.visitors.value),
        pageviews=int(overview.pageviews.value),
        visitors_change_pct=overview.visitors.change_pct,
        top_pages=[(r.label, r.count) for r in top.rows],
        # A blank source is direct traffic; label it so the email reads cleanly.
        top_sources=[(r.label or "Direct", r.visitors) for r in srcs.sources],
    )


def _fmt_change(pct: float | None) -> str:
    """A signed, rounded week-over-week delta (never a raw float artifact, §4)."""
    if pct is None:
        return "—"
    arrow = "▲" if pct >= 0 else "▼"
    return f"{arrow} {abs(pct):.0f}%"


def _period_label(now: datetime) -> str:
    start = (now - timedelta(days=WINDOW_DAYS)).strftime("%b %d")
    end = now.strftime("%b %d")
    return f"{start} – {end}"


def _site_html(d: SiteDigest) -> str:
    pages = (
        "".join(
            f"<li>{escape(label)} — <strong>{count:,}</strong></li>" for label, count in d.top_pages
        )
        or "<li>No pages yet</li>"
    )
    sources = (
        "".join(
            f"<li>{escape(label)} — <strong>{visitors:,}</strong></li>"
            for label, visitors in d.top_sources
        )
        or "<li>No sources yet</li>"
    )
    return (
        f'<div style="margin:24px 0;padding:16px;border:1px solid #eee;border-radius:8px">'
        f'<h2 style="font-size:16px;margin:0 0 8px">{escape(d.domain)}</h2>'
        f'<p style="margin:0 0 4px"><strong>{d.visitors:,}</strong> visitors '
        f"({_fmt_change(d.visitors_change_pct)} vs last week)</p>"
        f'<p style="margin:0 0 12px"><strong>{d.pageviews:,}</strong> pageviews</p>'
        f'<p style="margin:0 0 4px;color:#555;font-size:13px">Top pages</p><ul>{pages}</ul>'
        f'<p style="margin:12px 0 4px;color:#555;font-size:13px">Top sources</p><ul>{sources}</ul>'
        f"</div>"
    )


def _site_text(d: SiteDigest) -> str:
    pages = "\n".join(f"  - {label}: {count}" for label, count in d.top_pages) or "  - none"
    sources = (
        "\n".join(f"  - {label}: {visitors}" for label, visitors in d.top_sources) or "  - none"
    )
    return (
        f"{d.domain}\n"
        f"  {d.visitors} visitors ({_fmt_change(d.visitors_change_pct)} vs last week)\n"
        f"  {d.pageviews} pageviews\n"
        f"  Top pages:\n{pages}\n"
        f"  Top sources:\n{sources}\n"
    )


def render_digest(username: str, digests: list[SiteDigest], now: datetime) -> tuple[str, str, str]:
    """Render one account's digest into (subject, html, text).

    Only sites with traffic are included; the worker skips the send entirely when
    the account has no traffic anywhere.
    """
    active = [d for d in digests if d.has_traffic]
    period = _period_label(now)
    subject = f"Your Flowly week in review ({period})"
    heading = (
        f'<h1 style="font-size:20px">Hi {escape(username)}, here\'s your week</h1>'
        f'<p style="color:#888;font-size:13px">{period}</p>'
    )
    html = heading + "".join(_site_html(d) for d in active)
    text = f"Hi {username}, here's your Flowly week ({period}).\n\n" + "\n".join(
        _site_text(d) for d in active
    )
    return subject, html, text
