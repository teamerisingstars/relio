from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request

from ...memory import Memory
from ...record import Scope
from ..auth import AuthHook, anonymous_auth


def build_history_router(memory: Memory, auth: AuthHook = anonymous_auth) -> APIRouter:
    """A session transcript is pure memory — independent of any LLM provider."""
    router = APIRouter(prefix="/api")

    def principal(request: Request) -> Scope:
        return auth(request)

    @router.get("/history", operation_id="get_history")
    def history(
        session: Optional[str] = None,
        limit: int = 50,
        scope: Scope = Depends(principal),
    ):
        scope = scope.model_copy(update={"session": session})
        turns = memory.history(scope, limit=limit)
        return {
            "turns": [
                {
                    "id": t.id,
                    "role": t.metadata.get("role", "user"),
                    "content": t.content,
                    "created_at": t.created_at.isoformat(),
                }
                for t in turns
            ]
        }

    return router
