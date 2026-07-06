"""/assistant — public support chatbot (Phase F7). Thin: parse, call service."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis

from app.db.redis import get_redis
from app.models.schemas import AssistantChatRequest, AssistantReply
from app.services import assistant as assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])

RedisDep = Annotated[Redis, Depends(get_redis)]


@router.post("/chat")
async def chat(data: AssistantChatRequest, request: Request, redis: RedisDep) -> AssistantReply:
    client_ip = request.client.host if request.client else "unknown"
    reply, source = await assistant_service.answer(redis, client_ip, data.message)
    return AssistantReply(reply=reply, source=source)
