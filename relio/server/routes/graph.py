from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request

from ...memory import Memory
from ...record import Scope
from ..auth import AuthHook, anonymous_auth


def build_graph_router(memory: Memory, auth: AuthHook = anonymous_auth) -> APIRouter:
    router = APIRouter(prefix="/api/graph")

    def principal(request: Request) -> Scope:
        return auth(request)

    @router.get("/neighbors", operation_id="graph_neighbors")
    def neighbors(
        id: str,
        predicate: Optional[str] = None,
        direction: str = "out",
        scope: Scope = Depends(principal),
    ):
        if direction == "in":
            nodes = memory.in_neighbors(id, predicate=predicate, scope=scope)
        else:
            nodes = memory.neighbors(id, predicate=predicate, scope=scope)
        return {
            "neighbors": [
                {"id": n.id, "content": n.content, "type": n.type.value}
                for n in nodes
            ]
        }

    return router
