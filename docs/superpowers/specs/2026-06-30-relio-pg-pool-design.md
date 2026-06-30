# Feature I — Postgres Connection Pooling

**Date:** 2026-06-30
**Status:** Implemented (integration-gated; not run in this environment)
**Part of:** Relio "widen the fit" subset (Feature I of H–K)

## Problem

`PostgresBackend` used a single connection guarded by a global lock, serializing
every operation — the opposite of what the Postgres path is for (concurrency).

## Design

- Replace the single connection with `psycopg_pool.ConnectionPool`
  (`min_size=1`, `max_size=pool_size`, autocommit connections). Independent
  requests borrow their own connection and run concurrently.
- A `ContextVar` holds the **transaction-bound** connection for the current
  context. `_conn()` yields that bound connection inside a `transaction()`, or a
  freshly pooled one otherwise — so nested `add`/`delete` during a transaction
  share one connection and commit atomically, while ordinary ops don't contend.
- `transaction()` borrows one connection, binds it, wraps the block in
  `conn.transaction()` (single BEGIN/COMMIT), and unbinds on exit.
- New `postgres` dep: `psycopg-pool>=3.2` (lazy-imported, like `psycopg`).

## Out of scope (YAGNI)

- Tuning (pool sizing heuristics, statement timeouts, health checks).
- Read replicas / load balancing — that's the "heavy scale" tier the user
  deferred.
- SQLite concurrency is unchanged (single-writer is correct for the default).

## Verification

- `PostgresBackend` is concrete and imports without `psycopg`/`psycopg_pool`
  installed (lazy import) — checked.
- The existing Postgres contract + query + transaction integration tests now run
  through the pool when `RELIO_TEST_DATABASE_URL` is set (not run here).
