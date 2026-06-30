# relio/record.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    SEMANTIC = "semantic"
    FACT = "fact"
    SESSION = "session"
    NODE = "node"
    EDGE = "edge"


class Scope(BaseModel):
    tenant: Optional[str] = None
    user: Optional[str] = None
    agent: Optional[str] = None
    session: Optional[str] = None


class Relation(BaseModel):
    predicate: str
    target_id: str


def scope_matches(query: Scope, record: Scope) -> bool:
    """True if `record` satisfies every dimension `query` constrains.

    A `None` dimension in `query` is a wildcard; a set dimension must match the
    record exactly. Shared by recall (semantic) and history (chronological).
    """
    for field in ("tenant", "user", "agent", "session"):
        wanted = getattr(query, field)
        if wanted is not None and getattr(record, field) != wanted:
            return False
    return True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return "mem_" + uuid.uuid4().hex


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    type: MemoryType = MemoryType.SEMANTIC
    content: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    relations: list[Relation] = Field(default_factory=list)
    scope: Scope = Field(default_factory=Scope)
    metadata: dict[str, Any] = Field(default_factory=dict)
    ttl: Optional[int] = None  # seconds from created_at; None = permanent
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    schema_version: str = "1.0"
