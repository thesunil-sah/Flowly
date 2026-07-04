"""Email preferences — the one-click unsubscribe link target (§8).

Public (the link is clicked from an email client with no session) but
authenticated by the signed token it carries: only a valid `unsubscribe` token
can flip an account's opt-out. Thin: parse the token, call the service, return a
small confirmation page. Entitlement/other state is untouched — the token grants
exactly one effect.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.db.postgres import get_session
from app.services import notifications

router = APIRouter(prefix="/email", tags=["email"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Flowly</title><meta name="viewport" content="width=device-width, initial-scale=1">
</head><body style="font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem;text-align:center">
<h1 style="font-size:1.25rem">{heading}</h1><p style="color:#555">{body}</p>
</body></html>"""


def _page(heading: str, body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(heading=heading, body=body), status_code=status_code)


@router.get("/unsubscribe")
async def unsubscribe(
    token: Annotated[str, Query(min_length=1)], session: SessionDep
) -> HTMLResponse:
    """Opt the token's account out of digest + onboarding email."""
    try:
        await notifications.apply_unsubscribe(session, token)
    except AuthError:
        return _page(
            "Link expired",
            "This unsubscribe link is invalid or has expired. "
            "You can manage email preferences from your Flowly dashboard.",
            status_code=400,
        )
    return _page(
        "You're unsubscribed",
        "You won't receive weekly digests or onboarding email from Flowly anymore. "
        "Account and security emails will still be sent.",
    )
