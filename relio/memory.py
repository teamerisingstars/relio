# relio/memory.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .backends.base import StorageBackend
from .backends.sqlite import SQLiteBackend
from .embedding.base import Embedder
from .embedding.cache import CachingEmbedder
from .graph import GraphEngine
from .recall import RecallEngine
from .record import MemoryRecord, MemoryType, Relation, Scope, scope_matches
from .render import render_lines


class Memory:
    """The one public entry point: add / recall / get / forget / link."""

    def __init__(
        self,
        path: str = "relio.db",
        embedder: Optional[Embedder] = None,
        backend: Optional[StorageBackend] = None,
        database_url: Optional[str] = None,
    ) -> None:
        if embedder is None:
            from .embedding.local import LocalEmbedder

            embedder = LocalEmbedder()
        self._embedder = CachingEmbedder(embedder)
        if backend is not None:
            self._backend = backend
        elif database_url:
            # Scale path: swap to Postgres+pgvector with one config knob.
            from .backends.postgres import PostgresBackend

            self._backend = PostgresBackend(database_url, dim=self._embedder.dim)
        else:
            self._backend = SQLiteBackend(path, dim=self._embedder.dim)
        self._recall = RecallEngine(self._backend, self._embedder)
        self._graph = GraphEngine(self._backend)
        self._recall_cache: dict[tuple, list[MemoryRecord]] = {}

    @property
    def embedder(self) -> Embedder:
        return self._embedder

    def _invalidate(self) -> None:
        # Any write makes cached recall results potentially stale.
        self._recall_cache.clear()

    def add(
        self,
        content: str,
        type: MemoryType = MemoryType.SEMANTIC,
        scope: Optional[Scope] = None,
        data: Optional[dict[str, Any]] = None,
        relations: Optional[list[Relation]] = None,
        ttl: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
        embed: bool = True,
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
        # Turns are stored with embed=False so they never surface in semantic
        # recall (vector search only returns embedded rows).
        embedding = self._embedder.embed(content) if (embed and content) else None
        self._backend.add(record, embedding)
        self._invalidate()
        return record

    def add_many(
        self,
        contents: list[str],
        type: MemoryType = MemoryType.SEMANTIC,
        scope: Optional[Scope] = None,
        embed: bool = True,
    ) -> list[MemoryRecord]:
        """Bulk-add records, embedding all contents in one batch and writing them
        in a single transaction (atomic, and far cheaper than N single adds)."""
        records = [
            MemoryRecord(type=type, content=content, scope=scope or Scope())
            for content in contents
        ]
        embeddings = (
            self._embedder.embed_batch(list(contents))
            if embed
            else [None] * len(contents)
        )
        with self._backend.transaction():
            for record, content, embedding in zip(records, contents, embeddings):
                self._backend.add(record, embedding if (embed and content) else None)
        self._invalidate()
        return records

    def add_turn(self, role: str, content: str, scope: Optional[Scope] = None) -> MemoryRecord:
        """Persist one conversation turn as a non-embedded SESSION record."""
        return self.add(
            content,
            type=MemoryType.SESSION,
            scope=scope,
            metadata={"role": role},
            embed=False,
        )

    def history(self, scope: Optional[Scope] = None, limit: int = 20) -> list[MemoryRecord]:
        """Return the last `limit` conversation turns for `scope`, oldest first.

        Chronological (insertion order), not semantic: relies on the backend
        returning records in insertion order from `all()`.
        """
        scope = scope or Scope()
        turns = [
            r
            for r in self._backend.all()
            if r.type is MemoryType.SESSION and scope_matches(scope, r.scope)
        ]
        return turns[-limit:] if limit else turns

    def recall(
        self,
        query: str,
        scope: Optional[Scope] = None,
        type: Optional[MemoryType] = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        key = (
            query,
            scope.model_dump_json() if scope else "",
            type.value if type else "",
            limit,
        )
        cached = self._recall_cache.get(key)
        if cached is not None:
            return cached
        result = self._recall.recall(query, scope=scope, type=type, limit=limit)
        self._recall_cache[key] = result
        return result

    def recall_text(self, query: str, **kwargs: Any) -> str:
        return render_lines(self.recall(query, **kwargs))

    def query(
        self,
        type: Optional[MemoryType] = None,
        scope: Optional[Scope] = None,
        where: Optional[dict[str, str]] = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """Structured (non-semantic) filter by exact type / scope / metadata.

        Unlike recall(), this needs no query embedding and returns records that
        were never embedded — the path for non-AI / data-style listing.
        """
        return self._backend.query(type=type, scope=scope, metadata=where, limit=limit)

    def transaction(self):
        """Group multiple writes atomically: `with memory.transaction(): ...`."""
        return self._backend.transaction()

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        return self._backend.get(record_id)

    def forget(self, record_id: str) -> bool:
        ok = self._backend.delete(record_id)
        self._invalidate()
        return ok

    def link(self, source_id: str, predicate: str, target_id: str) -> MemoryRecord:
        record = self._backend.get(source_id)
        if record is None:
            raise KeyError(source_id)
        record.relations.append(Relation(predicate=predicate, target_id=target_id))
        record.updated_at = datetime.now(timezone.utc)
        embedding = self._embedder.embed(record.content) if record.content else None
        self._backend.add(record, embedding)
        self._invalidate()
        return record

    # --- graph ---------------------------------------------------------------

    def add_node(
        self,
        content: str,
        scope: Optional[Scope] = None,
        data: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryRecord:
        """Add a graph node (an embedded NODE record, also semantically recallable)."""
        return self.add(
            content, type=MemoryType.NODE, scope=scope, data=data, metadata=metadata
        )

    def add_edge(self, source_id: str, predicate: str, target_id: str) -> MemoryRecord:
        """Add a directed, typed edge from source to target."""
        return self.link(source_id, predicate, target_id)

    def neighbors(
        self, node_id: str, predicate: Optional[str] = None
    ) -> list[MemoryRecord]:
        return self._graph.neighbors(node_id, predicate=predicate)

    def in_neighbors(
        self, node_id: str, predicate: Optional[str] = None
    ) -> list[MemoryRecord]:
        return self._graph.in_neighbors(node_id, predicate=predicate)

    def traverse(
        self, start_id: str, depth: int = 1, predicate: Optional[str] = None
    ) -> list[MemoryRecord]:
        return self._graph.traverse(start_id, depth=depth, predicate=predicate)

    def close(self) -> None:
        self._backend.close()
