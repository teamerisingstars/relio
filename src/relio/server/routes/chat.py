from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ...memory import Memory
from ..agent import run_chat
from ..config import Settings
from ..llm.base import LLMProvider
from ..schemas import ChatRequest
from ..scope import make_scope


def build_chat_router(memory: Memory, provider: LLMProvider, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/chat")
    def chat(req: ChatRequest):
        scope = make_scope(tenant=req.tenant, user=req.user, session=req.session)

        def event_stream():
            try:
                for chunk in run_chat(
                    memory, provider, req.message, scope, limit=settings.recall_limit
                ):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as exc:  # surface LLM errors as an SSE event, end the stream
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return router
