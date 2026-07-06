"""/account — authed self-service settings (profile, password, email, delete).

Thin per §3: parse, depend on the current user, call `services/account.py`,
return a schema. Every route is authed via `CurrentUser` and acts only on the
caller's own account — there is no site_id or account_id in these paths, so the
tenant boundary is simply "you are you". `GET /auth/me` (in the auth router)
remains the account read; this router holds the writes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import CurrentUser
from app.db.clickhouse import ClickHouseDep
from app.db.postgres import get_session
from app.db.redis import get_redis
from app.models.schemas import (
    AccountOut,
    ChangeEmailRequest,
    ChangePasswordRequest,
    DeleteAccountRequest,
    EmailPreferencesRequest,
    IdentityOut,
    MessageResponse,
    VerifyEmailChangeRequest,
)
from app.services import account as account_service

router = APIRouter(prefix="/account", tags=["account"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def _dev_code(code: str | None) -> str | None:
    """Surface a code in responses only in local dev (no email provider)."""
    return code if settings.environment == "local" else None


@router.get("/identities")
async def list_identities(account: CurrentUser, session: SessionDep) -> list[IdentityOut]:
    identities = await account_service.list_identities(session, account.id)
    return [IdentityOut.from_identity(i) for i in identities]


@router.put("/email-preferences")
async def email_preferences(
    data: EmailPreferencesRequest, account: CurrentUser, session: SessionDep
) -> AccountOut:
    updated = await account_service.set_email_preferences(session, account, data.email_opt_out)
    return AccountOut.from_account(updated)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordRequest, account: CurrentUser, session: SessionDep
) -> Response:
    await account_service.change_password(
        session, account, data.current_password, data.new_password
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-email")
async def change_email(
    data: ChangeEmailRequest, account: CurrentUser, session: SessionDep, redis: RedisDep
) -> MessageResponse:
    code = await account_service.request_email_change(
        session, redis, account, data.new_email, data.password
    )
    return MessageResponse(status="verification_sent", dev_code=_dev_code(code))


@router.post("/verify-email-change")
async def verify_email_change(
    data: VerifyEmailChangeRequest, account: CurrentUser, session: SessionDep, redis: RedisDep
) -> AccountOut:
    updated = await account_service.verify_email_change(
        session, redis, account, data.new_email, data.code
    )
    return AccountOut.from_account(updated)


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    data: DeleteAccountRequest,
    account: CurrentUser,
    session: SessionDep,
    redis: RedisDep,
    ch_client: ClickHouseDep,
) -> Response:
    await account_service.delete_account(session, redis, ch_client, account, data.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
