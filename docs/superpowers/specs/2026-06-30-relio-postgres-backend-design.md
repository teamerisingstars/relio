# Feature B — Postgres + pgvector Storage Backend

**Date:** 2026-06-30
**Status:** Approved for implementation
**Part of:** Relio missing-features build-out (Feature B of A–G)

## Problem

The engine talks to a `StorageBackend` interface but only `SQLiteBackend`
exists. The architecture (spec §10.1) promises a `Postgres + pgvector` backend
implementing the same interface, swappable via config with no caller changes,
for the high-concurrency / many-millions-of-vectors scale path.

## Goal

Add `PostgresBackend` with behavior identical to `SQLiteBackend`, verified
against the same contract, and a one-knob config switch.

## Design

### Interface (must match SQLiteBackend exactly)
`add` (insert or replace by `id`), `get`, `delete` (bool), `search`
((record, distance) ascending, embedded rows only), `all` (insertion order),
`close`.

### Driver & deps
`psycopg` 3, new optional group `postgres = ["psycopg[binary]>=3.1"]`.
Lazy-imported in `Memory`, so psycopg is never required unless a Postgres URL is
configured. Embeddings are passed as `[a,b,c]` text cast to `::vector`, avoiding
an extra `pgvector` Python dependency.

### Schema (one table, mirrors SQLite)
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS records (
    rid        BIGSERIAL PRIMARY KEY,   -- insertion order for all()
    id         TEXT UNIQUE NOT NULL,
    doc        TEXT NOT NULL,
    expires_at DOUBLE PRECISION,
    embedding  vector(<dim>)            -- nullable
);
```

### Distance
pgvector `<->` (L2), matching sqlite-vec's L2 default, so `search` ordering is
identical across backends.

### Upsert
`INSERT ... ON CONFLICT (id) DO UPDATE SET doc, expires_at, embedding`. Preserves
`rid` on update, matching SQLite's replace-keeps-rowid behavior, so insertion
order is stable across updates.

### search
```sql
SELECT doc, embedding <-> %s::vector AS distance
FROM records
WHERE embedding IS NOT NULL
ORDER BY distance
LIMIT %s
```
The `IS NOT NULL` filter keeps non-embedded chat turns (Feature A) out of
semantic recall, as in SQLite.

### Concurrency
A `threading.Lock` serializes operations (FastAPI's threadpool shares one
connection); connection set to autocommit. A connection pool is the documented
scale path, not built now.

### Config swap (no caller changes)
- `Memory.__init__` gains `database_url: Optional[str] = None`. When set (and no
  explicit `backend` given), `Memory` builds `PostgresBackend(database_url, dim)`
  instead of `SQLiteBackend`.
- `Settings` gains `database_url: Optional[str] = None` (env `RELIO_DATABASE_URL`).

## Out of scope (YAGNI)

- Vector index (IVFFlat / HNSW) — sequential scan is correct; indexing is a
  later performance pass.
- Connection pooling — single guarded connection for now.
- Data migration tooling between SQLite and Postgres.

## Tests

- Reuse the SQLite contract against `PostgresBackend`, gated by env
  `RELIO_TEST_DATABASE_URL` and marked `integration` (skipped when unset):
  add/get roundtrip, delete true→false, `all` insertion order, search distance
  order, search ignores no-embedding rows, upsert replaces in place.
- `Memory(database_url=...)` builds a `PostgresBackend` (integration).
