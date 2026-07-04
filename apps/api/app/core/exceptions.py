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


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def register_exception_handlers(app: object) -> None:
    """Wire every AppError subclass to the uniform JSON handler."""
    # `app` is a FastAPI instance; typed loosely to avoid a circular import.
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[attr-defined]
