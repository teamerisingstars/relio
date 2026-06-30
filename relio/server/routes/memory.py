from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ...memory import Memory
from ...record import MemoryRecord, MemoryType, Scope, scope_matches
from ...render import render_lines
from ..auth import AuthHook, anonymous_auth
from ..schemas import AddRequest, QueryRequest


def build_memory_router(memory: Memory, auth: AuthHook = anonymous_auth) -> APIRouter:
    router = APIRouter(prefix="/api/memory")

    def principal(request: Request) -> Scope:
        return auth(request)

    @router.post("", status_code=201, operation_id="add_memory")
    def add(req: AddRequest, scope: Scope = Depends(principal)) -> MemoryRecord:
        scope = scope.model_copy(update={"session": req.session})
        return memory.add(
            req.content,
            type=req.type,
            scope=scope,
            data=req.data,
            ttl=req.ttl,
            metadata=req.metadata,
        )

    @router.post("/query", operation_id="query_memory")
    def query(req: QueryRequest, scope: Scope = Depends(principal)):
        results = memory.query(
            type=req.type, scope=scope, where=req.where or None, limit=req.limit
        )
        return {"results": results}

    # NOTE: declare /search BEFORE /{record_id} so it isn't captured as an id.
    @router.get("/search", operation_id="search_memory")
    def search(
        q: str,
        type: Optional[MemoryType] = None,
        limit: int = 5,
        scope: Scope = Depends(principal),
    ):
        results = memory.recall(q, scope=scope, type=type, limit=limit)
        return {"results": results, "text": render_lines(results)}

    @router.get("/{record_id}", operation_id="get_memory")
    def get(record_id: str, scope: Scope = Depends(principal)) -> MemoryRecord:
        rec = memory.get(record_id)
        if rec is None or not scope_matches(scope, rec.scope):
            raise HTTPException(status_code=404, detail="not found")
        return rec

    @router.delete("/{record_id}", operation_id="delete_memory")
    def forget(record_id: str, scope: Scope = Depends(principal)):
        rec = memory.get(record_id)
        if rec is None or not scope_matches(scope, rec.scope):
            raise HTTPException(status_code=404, detail="not found")
        return {"deleted": memory.forget(record_id)}

    return router
