"""Public ingestion endpoint — thin: parse, enrich via the service, 202 fast.

`POST /collect` is the one public, unauthenticated, high-volume write path. It:
  - reads the raw `text/plain` body the tracker sends (JSON-as-text, no preflight),
  - validates it, derives the client IP + Origin, hands off to the ingest service,
  - and returns **202** in milliseconds — the batch writer does the ClickHouse write.

CORS here is **open** (its own `Access-Control-Allow-Origin: *`), separate from the
dashboard's locked CORS in `main.py`. A bot/over-limit drop still returns 202 so
the filter isn't detectable.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import ValidationError as PydanticValidationError
from redis.asyncio import Redis

from app.core.exceptions import ValidationError
from app.db.redis import get_redis
from app.models.events import CollectEvent
from app.services import ingest as ingest_service

router = APIRouter(tags=["collect"])

RedisDep = Annotated[Redis, Depends(get_redis)]

# Open CORS for the public tracker (dashboard CORS stays locked in main.py).
_CORS_HEADERS = {"Access-Control-Allow-Origin": "*"}


def _client_ip(request: Request) -> str:
    """Real client IP: first X-Forwarded-For hop (behind a CDN) else the socket.

    Only used to compute the visitor hash + geo; never logged or stored.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",", 1)[0].strip()
    return request.client.host if request.client else ""


@router.options("/collect")
async def collect_options() -> Response:
    # Harmless preflight support for any non-simple future request.
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=_CORS_HEADERS)


@router.post("/collect", status_code=status.HTTP_202_ACCEPTED)
async def collect(request: Request, redis: RedisDep) -> Response:
    raw = await request.body()
    try:
        payload = json.loads(raw)
        event = CollectEvent.model_validate(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, PydanticValidationError) as exc:
        # Malformed body — reject with 422 (the tracker ignores the response).
        raise ValidationError() from exc

    await ingest_service.ingest_event(
        event,
        _client_ip(request),
        request.headers.get("user-agent", ""),
        request.headers.get("origin"),
        redis,
    )
    return Response(status_code=status.HTTP_202_ACCEPTED, headers=_CORS_HEADERS)
