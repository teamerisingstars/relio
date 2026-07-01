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
        out: list[MemoryRecord] = []
        for rel in node.relations:
            if predicate is not None and rel.predicate != predicate:
                continue
            target = self._backend.get(rel.target_id)
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
            next_frontier: list[str] = []
            for node_id in frontier:
                for nb in self.neighbors(node_id, predicate=predicate, scope=scope):
                    if nb.id in seen:
                        continue
                    seen.add(nb.id)
                    result.append(nb)
                    next_frontier.append(nb.id)
            frontier = next_frontier
            if not frontier:
                break
        return result
