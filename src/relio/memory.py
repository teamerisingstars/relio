# src/relio/memory.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .backends.base import StorageBackend
from .backends.sqlite import SQLiteBackend
from .embedding.base import Embedder
from .embedding.cache import CachingEmbedder
from .recall import RecallEngine
from .record import MemoryRecord, MemoryType, Relation, Scope
from .render import render_lines


class Memory:
    """The one public entry point: add / recall / get / forget / link."""

    def __init__(
        self,
        path: str = "relio.db",
        embedder: Optional[Embedder] = None,
        backend: Optional[StorageBackend] = None,
    ) -> None:
        if embedder is None:
            from .embedding.local import LocalEmbedder

            embedder = LocalEmbedder()
        self._embedder = CachingEmbedder(embedder)
        self._backend = backend or SQLiteBackend(path, dim=self._embedder.dim)
        self._recall = RecallEngine(self._backend, self._embedder)

    def add(
        self,
        content: str,
        type: MemoryType = MemoryType.SEMANTIC,
        scope: Optional[Scope] = None,
        data: Optional[dict[str, Any]] = None,
        relations: Optional[list[Relation]] = None,
        ttl: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            type=type,
            content=content,
            scope=scope or Scope(),
            data=data or {},
            relations=relations or [],
            ttl=ttl,
            metadata=metadata or {},
        )
        embedding = self._embedder.embed(content) if content else None
        self._backend.add(record, embedding)
        return record

    def recall(
        self,
        query: str,
        scope: Optional[Scope] = None,
        type: Optional[MemoryType] = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        return self._recall.recall(query, scope=scope, type=type, limit=limit)

    def recall_text(self, query: str, **kwargs: Any) -> str:
        return render_lines(self.recall(query, **kwargs))

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        return self._backend.get(record_id)

    def forget(self, record_id: str) -> bool:
        return self._backend.delete(record_id)

    def link(self, source_id: str, predicate: str, target_id: str) -> MemoryRecord:
        record = self._backend.get(source_id)
        if record is None:
            raise KeyError(source_id)
        record.relations.append(Relation(predicate=predicate, target_id=target_id))
        record.updated_at = datetime.now(timezone.utc)
        embedding = self._embedder.embed(record.content) if record.content else None
        self._backend.add(record, embedding)
        return record

    def close(self) -> None:
        self._backend.close()
