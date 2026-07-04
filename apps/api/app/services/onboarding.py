"""Onboarding email sequence — ledger + content (§8, Phase 8).

The sequence nudges a new account from signup → installed → live. Each step is
sent at most once, enforced by the `onboarding_emails` ledger (one row per
(account, step)) — the same idempotency pattern as `ProcessedStripeEvent`.

This module owns *which* email a step is and *whether it was already handled*;
the worker (`workers/onboarding.py`) owns *when* a step becomes eligible and does
the sending through the marketing gate (so opt-out + unsubscribe footer apply).
Content is HTML + text; there is no per-step SQL beyond the ledger.
"""

from collections.abc import Sequence
from html import escape

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tables import Account, OnboardingEmail, Site

# Ordered sequence steps. `welcome` on verification, `install` if still not
# collecting after a nudge delay, `live` once the first event lands.
STEP_WELCOME = "welcome"
STEP_INSTALL = "install"
STEP_LIVE = "live"

# How long after signup we wait before nudging an account that still isn't live.
INSTALL_NUDGE_HOURS = 24


async def already_sent(session: AsyncSession, account_id: object, step: str) -> bool:
    """Has this (account, step) already been recorded in the ledger?"""
    row = await session.scalar(
        select(OnboardingEmail).where(
            OnboardingEmail.account_id == account_id, OnboardingEmail.step == step
        )
    )
    return row is not None


async def record_step(session: AsyncSession, account_id: object, step: str) -> bool:
    """Mark a step handled. Returns False if it was already recorded (raced).

    A unique-constraint collision means a concurrent run recorded it first —
    treated as idempotent success-elsewhere, so the caller must not also send.
    """
    session.add(OnboardingEmail(account_id=account_id, step=step))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


def _shell(heading: str, body_html: str, cta_label: str, cta_path: str) -> str:
    url = f"{settings.web_base_url}{cta_path}"
    return (
        f'<h1 style="font-size:20px">{heading}</h1>{body_html}'
        f'<p style="margin:24px 0"><a href="{escape(url)}" '
        f'style="background:#111;color:#fff;padding:10px 18px;border-radius:6px;'
        f'text-decoration:none">{escape(cta_label)}</a></p>'
    )


def render_welcome(account: Account) -> tuple[str, str, str]:
    subject = "Welcome to Flowly"
    name = escape(account.username)
    html = _shell(
        f"Welcome, {name} 👋",
        "<p>Flowly gives you privacy-first, cookieless analytics — live visitors and "
        "clean reports, no consent banner needed.</p>"
        "<p>Add your first site and drop in the one-line snippet to start collecting.</p>",
        "Add your site",
        "/sites",
    )
    text = (
        f"Welcome, {account.username}!\n\n"
        "Flowly gives you privacy-first, cookieless analytics. Add your first site "
        f"and install the snippet to start collecting: {settings.web_base_url}/sites\n"
    )
    return subject, html, text


def render_install(account: Account) -> tuple[str, str, str]:
    subject = "Finish setting up Flowly"
    html = _shell(
        "You're one step away",
        "<p>We haven't seen any traffic yet. Once the Flowly snippet is on your site, "
        "your dashboard fills in within seconds.</p>"
        "<p>Grab the snippet and install instructions here:</p>",
        "Install the snippet",
        "/sites",
    )
    text = (
        f"Hi {account.username},\n\n"
        "We haven't seen any traffic yet. Install the Flowly snippet to start "
        f"collecting: {settings.web_base_url}/sites\n"
    )
    return subject, html, text


def render_live(account: Account, domain: str) -> tuple[str, str, str]:
    subject = f"🎉 Flowly is live on {domain}"
    html = _shell(
        f"{escape(domain)} is collecting data",
        "<p>Your snippet is working — Flowly is now tracking visitors. "
        "See who's on your site right now and how your traffic is trending.</p>",
        "Open your dashboard",
        "/dashboard",
    )
    text = (
        f"Great news {account.username} — {domain} is now sending data to Flowly.\n"
        f"Open your dashboard: {settings.web_base_url}/dashboard\n"
    )
    return subject, html, text


def install_cta_domain(sites: Sequence[Site]) -> str | None:
    """The first site's domain (for the live email), or None if no sites."""
    return sites[0].domain if sites else None
