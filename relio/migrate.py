# relio/migrate.py
"""Move a memory store from one backend to another (e.g. SQLite -> Postgres).

Records carry their own ids, scope, metadata, relations, and timestamps, so a
migration is a faithful copy of those. Vectors are **re-embedded** with a single
embedder rather than copied byte-for-byte: the two vector stores (`sqlite-vec`
serialized float32 vs. `pgvector`) don't share a wire format, and re-embedding
with a consistent embedder yields an equivalent vector space on the destination.
Use `embed=False` for a structured-only copy (no vectors; recall won't work until
re-embedded). See ADR-002.
"""
from __future__ import annotations

from typing import Callable, Optional

from .backends.base import StorageBackend
from .embedding.base import Embedder


def open_backend(spec: str, *, dim: int) -> StorageBackend:
    """Open a backend from a connection spec: a `postgres://` / `postgresql://`
    URL -> Postgres+pgvector; anything else is treated as a SQLite file path."""
    if spec.startswith("postgres://") or spec.startswith("postgresql://"):
        from .backends.postgres import PostgresBackend

        return PostgresBackend(spec, dim=dim)
    from .backends.sqlite import SQLiteBackend

    return SQLiteBackend(spec, dim=dim)


def migrate_records(
    source: StorageBackend,
    dest: StorageBackend,
    embedder: Embedder,
    *,
    embed: bool = True,
    batch_size: int = 256,
    progress: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Copy every record from `source` into `dest`, preserving id/scope/metadata/
    relations/timestamps. Content-bearing records are re-embedded with `embedder`
    (unless `embed=False`). `progress(done, total)` is called after each record.
    Returns the number of records migrated."""
    records = source.all()
    total = len(records)
    done = 0
    with dest.transaction():
        for start in range(0, total, batch_size):
            chunk = records[start : start + batch_size]
            if embed:
                # Batch-embed only the content-bearing records in this chunk.
                to_embed = [(i, r) for i, r in enumerate(chunk) if r.content]
                vectors = (
                    embedder.embed_batch([r.content for _, r in to_embed])
                    if to_embed
                    else []
                )
                embedding_by_index = {i: v for (i, _), v in zip(to_embed, vectors)}
            else:
                embedding_by_index = {}
            for i, rec in enumerate(chunk):
                dest.add(rec, embedding_by_index.get(i))
                done += 1
                if progress is not None:
                    progress(done, total)
    return done
