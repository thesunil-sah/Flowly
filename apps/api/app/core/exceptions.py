"""Typed application errors + FastAPI handlers.

Services raise these domain errors; the handlers registered on the app
translate them to HTTP responses. This keeps `HTTPException` out of the
service layer (CLAUDE.md §4) and gives every error a single, uniform shape.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base class for expected, translatable application errors."""

    status_code: int = 400
    # A stable, client-facing message. Deliberately generic for auth errors so
    # we never leak which part of a credential check failed.
    message: str = "Request could not be processed."
    # Optional stable machine code the client can branch on (e.g. the paywall
    # needs to tell an "account locked" 402 apart from other 402 billing errors).
    code: str | None = None

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class AuthError(AppError):
    """Authentication failed (missing/invalid/expired token, bad login)."""

    status_code = 401
    message = "Invalid credentials."


class ConflictError(AppError):
    """A uniqueness constraint would be violated (e.g. duplicate email)."""

    status_code = 409
    message = "Resource already exists."


class EmailNotVerifiedError(AppError):
    """Login attempted before the email was verified."""

    status_code = 403
    message = "Please verify your email before signing in."


class SiteLimitError(AppError):
    """The account is at its site cap (Phase 14 — max 5 sites per account)."""

    status_code = 403
    message = "You've reached the maximum of 5 sites. Remove one to add another."


class RateLimitError(AppError):
    """Too many requests within the configured window."""

    status_code = 429
    message = "Too many requests. Please try again later."


class ValidationError(AppError):
    """A request payload failed service-layer validation (malformed body)."""

    status_code = 422
    message = "Invalid payload."


class NotFoundError(AppError):
    """A requested resource doesn't exist — or isn't visible to this account.

    Ownership misses return 404 (not 403) so the API never reveals that a
    site_id exists under a different account (CLAUDE.md §9).
    """

    status_code = 404
    message = "Not found."


class BillingError(AppError):
    """A billing action can't proceed (e.g. portal without an active customer)."""

    status_code = 402
    message = "Billing is not set up for this account."


class UpgradeRequiredError(AppError):
    """A paid-tier report was requested by a free account (Phase 11 city gate)."""

    status_code = 402
    message = "This report is available on a paid plan."


class AccountLockedError(AppError):
    """A free account past the free monthly-view limit hit a gated read (Phase 14).

    Ingestion is never gated (§9) — only the dashboard read surface. The `code`
    lets the web app show the blocking upgrade paywall rather than a generic error.
    """

    status_code = 402
    message = "You've passed the free monthly pageview limit. Upgrade to keep your dashboard."
    code = "account_locked"


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    content: dict[str, str] = {"detail": exc.message}
    if exc.code is not None:
        content["code"] = exc.code
    return JSONResponse(status_code=exc.status_code, content=content)


def register_exception_handlers(app: object) -> None:
    """Wire every AppError subclass to the uniform JSON handler."""
    # `app` is a FastAPI instance; typed loosely to avoid a circular import.
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[attr-defined]
