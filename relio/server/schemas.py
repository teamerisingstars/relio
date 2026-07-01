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
    where: dict[str, Any] = {}  # metadata filters; keys may use field__op operators
    order_by: Optional[str] = None
    limit: int = 100
    offset: int = 0
