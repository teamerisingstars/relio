# relio/recall.py
from __future__ import annotations

import time
from typing import Optional

from .backends.base import StorageBackend
from .embedding.base import Embedder
from .record import MemoryRecord, MemoryType, Scope, scope_matches


class RecallEngine:
    def __init__(self, backend: StorageBackend, embedder: Embedder) -> None:
        self._backend = backend
        self._embedder = embedder

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

        # Scope/type/expiry are filtered AFTER the vector search, so a fixed
        # over-fetch can starve a tenant whose matches are crowded out of the top-k
        # by another tenant's closer vectors. Grow k until we have `limit` scoped
        # results or the store is exhausted — so recall can't silently under-return
        # for a filtered scope. (An ANN index + in-SQL scope prefilter is the
        # scale-path optimization; see docs/deploying.md and the audit.)
        def _passes(record) -> bool:
            if type is not None and record.type is not type:
                return False
            if not scope_matches(scope, record.scope):
                return False
            return not record.is_expired(now)

        k = max(limit * 5, limit)
        while True:
            candidates = self._backend.search(vector, k=k)
            out = [rec for rec, _d in candidates if _passes(rec)]
            # Enough matches, or the backend has nothing more to give (returned
            # fewer than we asked for → we've seen the whole store).
            if len(out) >= limit or len(candidates) < k:
                return out[:limit]
            k *= 4
