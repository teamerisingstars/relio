from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from ..record import MemoryType


class AddRequest(BaseModel):
    content: str
    type: MemoryType = MemoryType.SEMANTIC
    # Identity (tenant/user/agent) is resolved from the authenticated principal,
    # never from the request body. Only `session` (not a security boundary) is
    # client-supplied.
    session: Optional[str] = None
    data: dict[str, Any] = {}
    ttl: Optional[int] = None
    metadata: dict[str, Any] = {}


class ChatRequest(BaseModel):
    message: str
    session: Optional[str] = None


class QueryRequest(BaseModel):
    type: Optional[MemoryType] = None
    where: dict[str, str] = {}  # exact metadata equality filters
    limit: int = 100
