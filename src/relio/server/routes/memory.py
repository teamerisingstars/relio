from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from ...memory import Memory
from ...record import MemoryRecord, MemoryType
from ...render import render_lines
from ..schemas import AddRequest
from ..scope import make_scope


def build_memory_router(memory: Memory) -> APIRouter:
    router = APIRouter(prefix="/api/memory")

    @router.post("", status_code=201)
    def add(req: AddRequest) -> MemoryRecord:
        scope = make_scope(req.tenant, req.user, req.agent, req.session)
        return memory.add(
            req.content,
            type=req.type,
            scope=scope,
            data=req.data,
            ttl=req.ttl,
            metadata=req.metadata,
        )

    # NOTE: declare /search BEFORE /{record_id} so it isn't captured as an id.
    @router.get("/search")
    def search(
        q: str,
        user: Optional[str] = None,
        tenant: Optional[str] = None,
        type: Optional[MemoryType] = None,
        limit: int = 5,
    ):
        scope = make_scope(tenant=tenant, user=user)
        results = memory.recall(q, scope=scope, type=type, limit=limit)
        return {"results": results, "text": render_lines(results)}

    @router.get("/{record_id}")
    def get(record_id: str) -> MemoryRecord:
        rec = memory.get(record_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="not found")
        return rec

    @router.delete("/{record_id}")
    def forget(record_id: str):
        return {"deleted": memory.forget(record_id)}

    return router
