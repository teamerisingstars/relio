from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from ..record import MemoryType


class AddRequest(BaseModel):
    content: str
    type: MemoryType = MemoryType.SEMANTIC
    tenant: Optional[str] = None
    user: Optional[str] = None
    agent: Optional[str] = None
    session: Optional[str] = None
    data: dict[str, Any] = {}
    ttl: Optional[int] = None
    metadata: dict[str, Any] = {}


class ChatRequest(BaseModel):
    message: str
    tenant: Optional[str] = None
    user: Optional[str] = None
    session: Optional[str] = None
