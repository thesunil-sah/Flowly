"""Auth endpoints — thin: parse request, call a service, return a schema."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ratelimit import enforce_login_rate_limit
from app.core.security import CurrentUser
from app.db.postgres import get_session
from app.db.redis import get_redis
from app.models.schemas import (
    AccountOut,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    ResendCodeRequest,
    ResetPasswordRequest,
    ResetTokenResponse,
    SignupRequest,
    TokenResponse,
    VerifyEmailRequest,
    VerifyResetRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def _dev_code(code: str | None) -> str | None:
    """Surface a code in responses only in local dev (no email provider)."""
    return code if settings.environment == "local" else None


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest, session: SessionDep, redis: RedisDep) -> MessageResponse:
    code = await auth_service.signup(session, redis, data.username, data.email, data.password)
    return MessageResponse(status="verification_sent", dev_code=_dev_code(code))


@router.post("/resend-code")
async def resend_code(
    data: ResendCodeRequest, session: SessionDep, redis: RedisDep
) -> MessageResponse:
    code = await auth_service.resend_verification(session, redis, data.email)
    return MessageResponse(status="verification_sent", dev_code=_dev_code(code))


@router.post("/verify-email")
async def verify_email(
    data: VerifyEmailRequest, session: SessionDep, redis: RedisDep
) -> MessageResponse:
    await auth_service.verify_email(session, redis, data.email, data.code)
    return MessageResponse(status="verified")


@router.post("/login")
async def login(
    data: LoginRequest, request: Request, session: SessionDep, redis: RedisDep
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    await enforce_login_rate_limit(redis, client_ip, data.identifier)
    account = await auth_service.login(session, data.identifier, data.password)
    return auth_service.issue_tokens(account.id)


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest, session: SessionDep, redis: RedisDep
) -> MessageResponse:
    code = await auth_service.forgot_password(session, redis, data.email)
    return MessageResponse(status="reset_sent", dev_code=_dev_code(code))


@router.post("/verify-reset-code")
async def verify_reset_code(
    data: VerifyResetRequest, session: SessionDep, redis: RedisDep
) -> ResetTokenResponse:
    reset_token = await auth_service.verify_reset_code(session, redis, data.email, data.code)
    return ResetTokenResponse(reset_token=reset_token)


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, session: SessionDep) -> MessageResponse:
    await auth_service.reset_password(session, data.reset_token, data.password)
    return MessageResponse(status="password_reset")


@router.post("/refresh")
async def refresh(data: RefreshRequest) -> TokenResponse:
    return await auth_service.refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> Response:
    # Stateless: the client clears its tokens. Endpoint exists for a clean
    # contract and future server-side revoke.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
async def me(account: CurrentUser) -> AccountOut:
    return AccountOut.from_account(account)
