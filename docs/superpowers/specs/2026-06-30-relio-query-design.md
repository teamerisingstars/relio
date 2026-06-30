# Feature J — Structured Query + Multi-record Transactions

**Date:** 2026-06-30
**Status:** Implemented (Postgres paths integration-gated)
**Part of:** Relio "widen the fit" subset (Feature J of H–K)

## Problem

Records were retrievable only by semantic similarity (`recall`) or by id. No way
to list "all FACTs for user X where metadata.category = 'task'", and no atomic
multi-record writes. This blocked non-AI / data-style use.

## Design

Two abstract methods added to `StorageBackend` (both backends implement):

- **`query(type=, scope=, metadata=, limit=)`** — exact-match structured filter,
  insertion order, **includes non-embedded records** (unlike `search`). SQLite
  pushes predicates down with `json_extract`; Postgres with `(doc::jsonb)#>>`.
  Interpolated json paths are guarded by a `^\w+$` key check.
- **`transaction()`** — context manager; writes inside commit atomically, roll
  back on exception. SQLite uses a reentrant lock + deferred commit
  (`_txn_depth`); Postgres uses `connection.transaction()`. Reentrant locks let
  `add`/`delete` nest inside without deadlock.

`Memory.query(type, scope, where, limit)` and `Memory.transaction()` expose them.
`POST /api/memory/query` filters by the principal's scope + a `where` body.

## Out of scope (YAGNI)

- Ranges / comparisons / OR / joins — equality only (full relational = a
  different product).
- Secondary indexes on metadata — pushdown works now; indexing is a later perf
  pass.
- HTTP transaction control — Python API only.

## Tests

- Query by type / scope / metadata; returns non-embedded records; insertion
  order + limit; invalid metadata key rejected.
- Transaction commits all on success; rolls back the partial batch on exception.
- `POST /api/memory/query` filters by type and metadata.
- Postgres query + rollback (integration-gated).
