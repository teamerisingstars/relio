# relio/graph.py
from __future__ import annotations

from typing import Optional

from .backends.base import StorageBackend
from .record import MemoryRecord, Scope, scope_matches


class GraphEngine:
    """Query layer over relations: nodes are records, edges are their relations.

    Out-edges are read directly from a node's `relations`; in-edges require a
    scan of all records. No backend interface change — works on any backend.
    """

    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    def neighbors(
        self, node_id: str, predicate: Optional[str] = None, scope: Optional[Scope] = None
    ) -> list[MemoryRecord]:
        node = self._backend.get(node_id)
        if node is None:
            return []
        # Batch the target lookups into one query instead of one get() per edge.
        target_ids = [
            rel.target_id for rel in node.relations
            if predicate is None or rel.predicate == predicate
        ]
        fetched = self._backend.get_many(target_ids)
        out: list[MemoryRecord] = []
        for tid in target_ids:  # preserve edge order
            target = fetched.get(tid)
            if target is not None and (scope is None or scope_matches(scope, target.scope)):
                out.append(target)
        return out

    def in_neighbors(
        self, node_id: str, predicate: Optional[str] = None, scope: Optional[Scope] = None
    ) -> list[MemoryRecord]:
        out: list[MemoryRecord] = []
        for record in self._backend.all():
            if scope is not None and not scope_matches(scope, record.scope):
                continue
            for rel in record.relations:
                if rel.target_id == node_id and (
                    predicate is None or rel.predicate == predicate
                ):
                    out.append(record)
                    break
        return out

    def traverse(
        self,
        start_id: str,
        depth: int = 1,
        predicate: Optional[str] = None,
        scope: Optional[Scope] = None,
    ) -> list[MemoryRecord]:
        """Cycle-safe BFS over out-edges. Returns reachable nodes (excludes start)."""
        seen = {start_id}
        frontier = [start_id]
        result: list[MemoryRecord] = []
        for _ in range(depth):
            # Two batched queries per level (fetch the frontier, then all their
            # targets) instead of a get() per node and per edge.
            nodes = self._backend.get_many(frontier)
            target_ids: list[str] = []
            for node_id in frontier:
                node = nodes.get(node_id)
                if node is None:
                    continue
                for rel in node.relations:
                    if predicate is None or rel.predicate == predicate:
                        target_ids.append(rel.target_id)
            targets = self._backend.get_many(target_ids)
            next_frontier: list[str] = []
            for tid in target_ids:  # BFS order, deduped by `seen`
                if tid in seen:
                    continue
                nb = targets.get(tid)
                if nb is None or (scope is not None and not scope_matches(scope, nb.scope)):
                    continue
                seen.add(tid)
                result.append(nb)
                next_frontier.append(tid)
            frontier = next_frontier
            if not frontier:
                break
        return result
