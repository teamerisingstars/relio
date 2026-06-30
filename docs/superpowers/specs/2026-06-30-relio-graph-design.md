# Feature C — Graph Query Engine

**Date:** 2026-06-30
**Status:** Approved for implementation
**Part of:** Relio missing-features build-out (Feature C of A–G)

## Problem

`MemoryType.NODE`/`EDGE`, a `Relation(predicate, target_id)` model, and
`Memory.link()` (attaches relations to a record) already exist, but there is no
way to *query* the graph: no neighbors, reverse edges, or traversal.

## Goal

A graph query layer over the existing store so callers can walk typed, directed
relationships between NODE records.

## Design

A **graph query engine over relations — not a new backend.** Edges are
`Relation`s on NODE records (reusing `link()`); nodes are `NODE` records. This
keeps "the graph lives in the one file" and needs **no `StorageBackend`
interface change**, so it works on SQLite and Postgres alike.

### `relio/graph.py` — `GraphEngine(backend)`
- `neighbors(node_id, predicate=None)` → out-neighbours: resolve `node.relations`
  to target records, optionally filtered by predicate.
- `in_neighbors(node_id, predicate=None)` → reverse edges: scan `all()` for
  records whose relations target `node_id`.
- `traverse(start_id, depth=1, predicate=None)` → cycle-safe BFS over out-edges;
  returns reachable nodes (excludes the start), each visited once.

### `Memory` convenience methods (delegate to the engine)
- `add_node(content, …)` → `add(type=NODE, …)` (embedded, so nodes are also
  semantically recallable).
- `add_edge(source_id, predicate, target_id)` → wraps `link()`.
- `neighbors` / `in_neighbors` / `traverse` → delegate to `GraphEngine`.

### API
- `GET /api/graph/neighbors?id=…&predicate=…&direction=out|in` in a new
  `relio/server/routes/graph.py`, wired in `create_app`.

## Out of scope (YAGNI)

- Edge attributes/weights — `Relation` carries only predicate + target;
  rich `EDGE`-record edges with data are a later extension.
- Shortest-path / weighted traversal, scope-filtered traversal.
- HTTP edge/node creation endpoints (creation stays via the Python API +
  existing `POST /api/memory` for nodes); only graph *reads* are exposed now.

## Tests

- `add_node` creates a NODE record.
- `neighbors` returns linked targets; predicate filter narrows them.
- `in_neighbors` finds the source of an edge.
- `traverse` depth-2 reaches a grandchild; a cycle (A→B→A) terminates.
- `GET /api/graph/neighbors` returns a node's out-neighbours.
