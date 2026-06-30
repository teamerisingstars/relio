from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from ...memory import Memory


def build_graph_router(memory: Memory) -> APIRouter:
    router = APIRouter(prefix="/api/graph")

    @router.get("/neighbors", operation_id="graph_neighbors")
    def neighbors(id: str, predicate: Optional[str] = None, direction: str = "out"):
        if direction == "in":
            nodes = memory.in_neighbors(id, predicate=predicate)
        else:
            nodes = memory.neighbors(id, predicate=predicate)
        return {
            "neighbors": [
                {"id": n.id, "content": n.content, "type": n.type.value}
                for n in nodes
            ]
        }

    return router
