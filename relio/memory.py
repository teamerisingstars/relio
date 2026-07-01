# relio/memory.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Union

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
            # Honor RELIO_EMBEDDER (e.g. "deterministic" for offline/CI/tests) so
            # a bare Memory() doesn't force the ~130MB local-model download.
            from .embedding.registry import make_embedder

            embedder = make_embedder()
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
        items: list[Union[str, Mapping[str, Any]]],
        type: MemoryType = MemoryType.SEMANTIC,
        scope: Optional[Scope] = None,
        embed: bool = True,
    ) -> list[MemoryRecord]:
        """Bulk-add records in one embed batch + one transaction (atomic, far
        cheaper than N single adds).

        Each item is either a plain string (its content) **or** a mapping for
        bulk-ingesting rows with structure — `{"content", "type"?, "scope"?,
        "data"?, "metadata"?}` — so you can load records that carry per-row
        metadata, not just bare text. The `type`/`scope` args are per-call
        defaults; a mapping may override them.
        """
        default_scope = scope or Scope()
        records: list[MemoryRecord] = []
        for item in items:
            if isinstance(item, str):
                records.append(MemoryRecord(type=type, content=item, scope=default_scope))
            elif isinstance(item, Mapping):
                item_scope = item.get("scope")
                records.append(
                    MemoryRecord(
                        type=item.get("type", type),
                        content=item.get("content", ""),
                        scope=item_scope if item_scope is not None else default_scope,
                        data=dict(item.get("data") or {}),
                        metadata=dict(item.get("metadata") or {}),
                    )
                )
            else:
                raise TypeError(
                    f"add_many items must be str or mapping, got {item.__class__.__name__}"
                )
        contents = [r.content for r in records]
        embeddings = (
            self._embedder.embed_batch(contents) if embed else [None] * len(records)
        )
        with self._backend.transaction():
            for record, embedding in zip(records, embeddings):
                self._backend.add(record, embedding if (embed and record.content) else None)
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
        where: Optional[dict] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        """Structured (non-semantic) filter. `where` supports `field__op` operators
        (`gt/gte/lt/lte/contains`, default exact); `order_by` a metadata field
        (`-field` = desc); plus `limit`/`offset` pagination.

        Unlike recall(), this needs no query embedding and returns records that
        were never embedded — the path for non-AI / data-style listing.
        """
        return self._backend.query(
            type=type, scope=scope, where=where, order_by=order_by, limit=limit, offset=offset
        )

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
        self, node_id: str, predicate: Optional[str] = None, scope: Optional[Scope] = None
    ) -> list[MemoryRecord]:
        return self._graph.neighbors(node_id, predicate=predicate, scope=scope)

    def in_neighbors(
        self, node_id: str, predicate: Optional[str] = None, scope: Optional[Scope] = None
    ) -> list[MemoryRecord]:
        return self._graph.in_neighbors(node_id, predicate=predicate, scope=scope)

    def traverse(
        self, start_id: str, depth: int = 1, predicate: Optional[str] = None, scope: Optional[Scope] = None
    ) -> list[MemoryRecord]:
        return self._graph.traverse(start_id, depth=depth, predicate=predicate, scope=scope)

    def close(self) -> None:
        self._backend.close()
