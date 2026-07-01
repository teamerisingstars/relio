# relio/migrate.py
"""Move a memory store from one backend to another (e.g. SQLite -> Postgres).

Records carry their own ids, scope, metadata, relations, and timestamps, so a
migration is a faithful copy of those. Vectors are **preserved** when the source
exposes them (`StorageBackend.iter_embeddings`) and their dimension matches; any
record whose vector is missing or a different dimension is re-embedded. Use
`reembed=True` to force re-embedding (e.g. when switching embedder/model) or
`embed=False` for a structured-only copy. See ADR-002.
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
    reembed: bool = False,
    progress: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Copy every record from `source` into `dest`, preserving id/scope/metadata/
    relations/timestamps.

    Vectors are **preserved when possible**: a stored embedding of matching
    dimension is copied as-is. Records whose vector is missing or a different
    dimension are re-embedded with `embedder`. Options:

    - `embed=False` — structured-only copy (no vectors at all).
    - `reembed=True` — force re-embedding even where a stored vector exists (use
      when changing embedder/model).

    `progress(done, total)` is called after each record. Returns the count."""
    records: list = []
    embeddings: list = []          # final vector (or None) per record, by index
    need_embed: list = []          # (index, content) for records to re-embed
    for rec, stored in source.iter_embeddings():
        idx = len(records)
        records.append(rec)
        embeddings.append(None)
        if not embed:
            continue
        reusable = (
            stored is not None and not reembed and len(stored) == embedder.dim
        )
        if reusable:
            embeddings[idx] = stored
        elif rec.content:
            need_embed.append((idx, rec.content))

    if need_embed:  # one batch for everything that actually needs (re-)embedding
        vectors = embedder.embed_batch([c for _, c in need_embed])
        for (idx, _), vector in zip(need_embed, vectors):
            embeddings[idx] = vector

    total = len(records)
    with dest.transaction():
        for idx, rec in enumerate(records):
            dest.add(rec, embeddings[idx])
            if progress is not None:
                progress(idx + 1, total)
    return total
