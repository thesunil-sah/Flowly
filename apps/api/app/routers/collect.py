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
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import ValidationError as PydanticValidationError
from redis.asyncio import Redis

from app.core.exceptions import NotFoundError, ValidationError
from app.db.redis import get_redis
from app.models.events import CollectEvent
from app.services import ingest as ingest_service

router = APIRouter(tags=["collect"])

RedisDep = Annotated[Redis, Depends(get_redis)]

# Open CORS for the public tracker (dashboard CORS stays locked in main.py).
_CORS_HEADERS = {"Access-Control-Allow-Origin": "*"}

# The built, minified tracking script (apps/tracker/dist/script.js). This file
# lives at parents[4] == repo root from apps/api/app/routers/collect.py.
_TRACKER_SCRIPT = Path(__file__).resolve().parents[4] / "apps" / "tracker" / "dist" / "script.js"


def _client_ip(request: Request) -> str:
    """Real client IP: first X-Forwarded-For hop (behind a CDN) else the socket.

    Only used to compute the visitor hash + geo; never logged or stored.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",", 1)[0].strip()
    return request.client.host if request.client else ""


@router.get("/script.js")
async def tracker_script() -> FileResponse:
    """Serve the built tracking script (public, open CORS, cacheable).

    Dev/self-host convenience so the default `TRACKER_SCRIPT_URL`
    (`{API}/script.js`) resolves; in production this is fronted by a CDN.
    """
    if not _TRACKER_SCRIPT.is_file():
        # Tracker not built yet (`pnpm --filter tracker build`). 404 beats a
        # bare 500 from FileResponse on a missing path.
        raise NotFoundError("Tracking script has not been built.")
    return FileResponse(
        _TRACKER_SCRIPT,
        media_type="application/javascript",
        headers={**_CORS_HEADERS, "Cache-Control": "public, max-age=300"},
    )


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
