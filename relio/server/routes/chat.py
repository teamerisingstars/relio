from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ...memory import Memory
from ...record import Scope
from ..agent import run_chat
from ..auth import AuthHook, anonymous_auth
from ..config import Settings
from ..llm.base import LLMProvider
from ..schemas import ChatRequest


def build_chat_router(
    memory: Memory,
    provider: LLMProvider,
    settings: Settings,
    auth: AuthHook = anonymous_auth,
) -> APIRouter:
    router = APIRouter(prefix="/api")

    def principal(request: Request) -> Scope:
        return auth(request)

    @router.post("/chat", operation_id="chat")
    def chat(req: ChatRequest, scope: Scope = Depends(principal)):
        scope = scope.model_copy(update={"session": req.session})

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
