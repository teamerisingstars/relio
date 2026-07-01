# relio/aiapp/routes.py
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..server.schemas import ChatRequest

logger = logging.getLogger("relio")


def build_agents_router(agents: dict[str, Any]) -> APIRouter:
    """Expose the app's bounded agents over HTTP.

    - GET  /api/agents               -> list agent names + their tool slices
    - POST /api/agents/{name}/chat   -> SSE stream from that bounded agent
    """
    router = APIRouter(prefix="/api/agents")

    @router.get("", operation_id="list_agents")
    def list_agents():
        return {"agents": [{"name": a.name, "tools": a.tools()} for a in agents.values()]}

    @router.post("/{name}/chat", operation_id="agent_chat")
    def agent_chat(name: str, req: ChatRequest):
        agent = agents.get(name)
        if agent is None:
            raise HTTPException(status_code=404, detail="no such agent")

        def event_stream():
            try:
                for chunk in agent.chat(req.message):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception:  # log server-side; never leak internals to the client
                logger.exception("agent chat failed")
                yield f"data: {json.dumps({'error': 'internal error'})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return router
