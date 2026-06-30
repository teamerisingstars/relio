# src/relio/recall.py
from __future__ import annotations

import time
from typing import Optional

from .backends.base import StorageBackend
from .embedding.base import Embedder
from .record import MemoryRecord, MemoryType, Scope


class RecallEngine:
    def __init__(self, backend: StorageBackend, embedder: Embedder) -> None:
        self._backend = backend
        self._embedder = embedder

    @staticmethod
    def _scope_matches(query: Scope, record: Scope) -> bool:
        for field in ("tenant", "user", "agent", "session"):
            wanted = getattr(query, field)
            if wanted is not None and getattr(record, field) != wanted:
                return False
        return True

    @staticmethod
    def _is_expired(record: MemoryRecord, now: float) -> bool:
        if record.ttl is None:
            return False
        return record.created_at.timestamp() + record.ttl < now

    def recall(
        self,
        query: str,
        scope: Optional[Scope] = None,
        type: Optional[MemoryType] = None,
        limit: int = 5,
        now: Optional[float] = None,
    ) -> list[MemoryRecord]:
        now = time.time() if now is None else now
        scope = scope or Scope()
        vector = self._embedder.embed(query)
        # Over-fetch so post-filtering still has enough candidates.
        candidates = self._backend.search(vector, k=max(limit * 5, limit))
        out: list[MemoryRecord] = []
        for record, _distance in candidates:
            if type is not None and record.type is not type:
                continue
            if not self._scope_matches(scope, record.scope):
                continue
            if self._is_expired(record, now):
                continue
            out.append(record)
            if len(out) >= limit:
                break
        return out
