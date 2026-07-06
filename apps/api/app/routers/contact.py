"""/contact — public contact form (Phase F6). Thin: parse, call service."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis

from app.db.redis import get_redis
from app.models.schemas import ContactRequest
from app.services import contact as contact_service

router = APIRouter(prefix="/contact", tags=["contact"])

RedisDep = Annotated[Redis, Depends(get_redis)]


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def contact(data: ContactRequest, request: Request, redis: RedisDep) -> Response:
    client_ip = request.client.host if request.client else "unknown"
    await contact_service.submit_contact(
        redis, client_ip, data.name, data.email, data.message, data.company
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
