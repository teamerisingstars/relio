# ADR-002: Storage Backend Strategy — SQLite Default, Postgres for Scale

**Status:** Accepted
**Date:** 2026-07-01
**Deciders:** Relio maintainer
**Relates to:** [ADR-001](ADR-001-relio-system-architecture.md) (the storage seam)

---

## Context

Relio stores typed, scoped memories (`SEMANTIC / FACT / SESSION / NODE / EDGE`)
plus their vector embeddings and a graph (nodes + edges). Two workloads share
one store: **vector recall** (k-NN over embeddings) and **structured query**
(`field__gt/contains/in`, `order_by`, `limit/offset`) — plus graph traversal
(`neighbors / in_neighbors / traverse`), all filtered by `Scope`
(tenant/user/agent/session).

The deployment surface is wide:

- **Local / offline / tests / a solo app** — must work with `pip install relio`
  and zero configuration, no server, no keys.
- **Production multi-tenant** — concurrent writers, larger corpora, real
  connection pooling, and vector indexing that holds up past what an embedded DB
  can do.

The seam already exists: `StorageBackend` (ABC) with `add / get / delete /
search / all / query / transaction / close`, and `Memory.__init__` selects the
implementation. The open question ADR-001 deferred here: **what is the default,
and when/how does a user migrate?**

## Decision

Ship **SQLite + `sqlite-vec` as the zero-config default**, and **Postgres +
`pgvector` (pooled, JSONB payloads + GIN indexes) as the scale path**, both
behind the same `StorageBackend` ABC. Selection is a single config knob:

```python
Memory()                              # → SQLiteBackend("relio.db")   (default)
Memory(database_url="postgres://…")   # → PostgresBackend  (pooled, pgvector)
Memory(backend=MyBackend(...))        # → bring your own (escape hatch)
```

No app code changes across the two — only the constructor argument. Postgres
ships as an opt-in extra (`pip install "relio[postgres]"`).

## Options Considered

### Option A: One backend only (Postgres-only) — *rejected*
| Dimension | Assessment |
|-----------|------------|
| Complexity | High for the 90% case — every hello-world needs a running DB |
| Cost | A server + extension before any value |
| Scalability | Excellent |
| Team familiarity | Medium |

**Pros:** One code path; no "works on my machine, breaks in prod" gap.
**Cons:** Destroys the offline/zero-config story that drives OSS adoption; tests
need a container; contradicts ADR-001's progressive-disclosure force.

### Option B: SQLite default + Postgres scale path, one seam — *chosen*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low at adoption; two impls to maintain behind one ABC |
| Cost | Zero to start; opt-in server when needed |
| Scalability | SQLite covers solo/small; Postgres covers multi-tenant/large |
| Team familiarity | High — both are ubiquitous |

**Pros:** Zero-config default; identical app code; tests run on SQLite in-process;
migration is one config knob; `backend=` escape hatch keeps the seam open.
**Cons:** Two implementations to keep behavior-compatible; feature parity must be
guarded by a **shared conformance test suite**; vector-index semantics differ
between `sqlite-vec` and `pgvector`.

### Option C: Pluggable-only (no bundled backend, adapters live outside) — *rejected*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Pushed onto every user |
| Cost | Everyone writes/wires an adapter before first use |
| Scalability | Depends entirely on the chosen adapter |
| Team familiarity | Low |

**Pros:** Smallest core; maximal flexibility.
**Cons:** No batteries; the "10 lines and it works" promise dies; the `backend=`
argument already gives this flexibility *without* removing the defaults.

## Trade-off Analysis

The tension is **zero-config adoption vs. production scale**, and Option B
refuses to pick one at the expense of the other by putting both behind one ABC.
The real cost it takes on is **dual-implementation drift** — the two backends
must return the same records for the same queries, including operator semantics,
ordering, scope filtering, and graph traversal. That cost is paid down with a
**parameterized conformance suite** run against both backends (SQLite in-process
always; Postgres in CI when a service is available), so parity is enforced rather
than hoped for.

Vector search is where the abstraction is thinnest: `sqlite-vec` and `pgvector`
differ in index types, distance operators, and recall/latency behavior at size.
The `StorageBackend.search(embedding, k)` signature deliberately hides *how* k-NN
is done, but callers must not assume identical ranking on ties — the conformance
suite asserts set-membership and score ordering, not exact index internals.

### When to migrate SQLite → Postgres

Migrate when **any** of these is true (guidance, not a hard gate):

| Signal | Threshold (rule of thumb) |
|--------|---------------------------|
| Concurrent writers | More than one process/worker writing (SQLite's writer lock serializes them) |
| Corpus size | ~100k+ memory records, or vector recall latency exceeding your budget |
| Multi-tenancy at scale | Many tenants with isolation + per-tenant growth |
| Operational needs | Backups/PITR, replicas, connection pooling, managed hosting |
| Deployment topology | More than one app instance sharing one store (SQLite is single-host) |

Below these, SQLite is the *right* choice, not a placeholder — don't migrate on
principle.

## Consequences

**Easier**
- First run and tests: no server, no config, fully in-process.
- Scaling: flip `database_url`; app code is untouched.
- Custom stores: `backend=` accepts any `StorageBackend`.

**Harder**
- Two implementations must stay behavior-compatible (mitigated by the
  conformance suite).
- Vector-index parity is approximate at the margins; document that ranking on
  ties may differ.
- A **data migration path** (copy SQLite → Postgres, re-embed if the embedder/dim
  changed) is not yet shipped — see Action Items.

**To revisit**
- A `relio migrate` command that streams records + embeddings across backends.
- Whether embeddings should be re-computed or copied on migration (depends on
  embedder/dim stability).
- Additional backends (e.g. a hosted vector DB) if a managed tier (ADR-001
  Option C) is pursued — they attach at this same seam.

## Action Items

1. [x] `StorageBackend` ABC with `add/get/delete/search/all/query/transaction/close`.
2. [x] SQLite + `sqlite-vec` default; Postgres + `pgvector` (pooled, JSONB+GIN) opt-in extra.
3. [x] One-knob selection in `Memory(...)` (`database_url` / `backend`).
4. [x] Extract the conformance suite into a shared, parameterized fixture run against **both** backends — `tests/test_backend_conformance.py` (SQLite always; Postgres when `RELIO_TEST_DATABASE_URL` is set). The old hand-mirrored `test_sqlite_backend.py` / `test_postgres_backend.py` contract tests were removed; only Postgres-specific *wiring* remains in the latter.
5. [x] Ship `relio migrate --from <src> --to <dst>` (`relio/migrate.py` + CLI). **Decision:** it **re-embeds** rather than copying raw vectors — the backend contract doesn't expose stored embeddings, and `sqlite-vec` (serialized float32) and `pgvector` don't share a wire format, so re-embedding with a consistent embedder is both simpler and correct. `--no-embed` does a structured-only copy. Preserving raw vectors would require a new `iter_embeddings()` backend method — deferred until there's a reason to avoid re-embedding.
6. [x] Document the migration behavior + the SQLite→Postgres signal table — see [providers.md](../providers.md) and this ADR's signal table.
7. [x] Add a note to `search()`'s contract: ties are not guaranteed identically ordered across backends.
