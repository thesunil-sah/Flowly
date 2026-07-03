"""Pydantic request/response schemas — validation at the boundary (CLAUDE.md §4).

Emails and usernames are normalized (lowercase + trimmed) by shared validators
so every entry point stores and looks up the same form.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# Password floor 8; 128 cap keeps argon2 input bounded (hashing-DoS guard).
_Password = Field(min_length=8, max_length=128)
# 6-digit numeric code.
_Code = Field(pattern=r"^\d{6}$")


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_username(value: str) -> str:
    return value.strip().lower()


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    email: EmailStr
    password: str = _Password

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        return _normalize_username(v)


class LoginRequest(BaseModel):
    # Email or username.
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def _identifier(cls, v: str) -> str:
        return v.strip().lower()


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = _Code

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class ResendCodeRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class VerifyResetRequest(BaseModel):
    email: EmailStr
    code: str = _Code

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalize_email(v)


class ResetPasswordRequest(BaseModel):
    reset_token: str
    password: str = _Password


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access-token lifetime in seconds


class MessageResponse(BaseModel):
    status: str
    # Populated only in local dev so the code can be surfaced without email.
    dev_code: str | None = None


class ResetTokenResponse(BaseModel):
    reset_token: str


class AccountOut(BaseModel):
    """Public account shape — never exposes password_hash."""

    id: UUID
    username: str
    email: EmailStr
    plan: str
    status: str
    email_verified_at: datetime | None
    trial_ends_at: datetime | None

    model_config = {"from_attributes": True}


class SiteOut(BaseModel):
    """Public site shape for the dashboard (site_id is public, not a secret)."""

    id: UUID
    site_id: str
    domain: str

    model_config = {"from_attributes": True}
