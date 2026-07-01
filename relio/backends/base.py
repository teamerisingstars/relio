# relio/backends/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ContextManager, Optional

from ..record import MemoryRecord, MemoryType, Scope

_OPS = {"gt", "gte", "lt", "lte", "ne", "contains", "startswith", "in"}


def split_op(key: str) -> tuple[str, str]:
    """`amount__gt` -> ('amount', 'gt'); `category` -> ('category', 'eq')."""
    if "__" in key:
        field, _, op = key.rpartition("__")
        if op in _OPS:
            return field, op
    return key, "eq"


class StorageBackend(ABC):
    """Persistence contract. Callers (Memory, RecallEngine) depend only on this."""

    @abstractmethod
    def add(self, record: MemoryRecord, embedding: list[float] | None) -> None:
        """Insert or replace a record; store its embedding if provided."""

    @abstractmethod
    def get(self, record_id: str) -> MemoryRecord | None:
        ...

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        """Return True if a row was removed."""

    @abstractmethod
    def search(self, embedding: list[float], k: int) -> list[tuple[MemoryRecord, float]]:
        """Return up to k nearest records as (record, distance), ascending distance.

        Ranking on *ties* (equal distances) is not guaranteed identical across
        backends — `sqlite-vec` and `pgvector` may break ties differently. Depend
        on set membership + distance ordering, not exact tie order. See ADR-002.
        """

    @abstractmethod
    def all(self) -> list[MemoryRecord]:
        """Return every record in insertion order (oldest first).

        History relies on this ordering; backends must preserve it.
        """

    def iter_embeddings(self):
        """Yield `(record, embedding | None)` for every record, oldest first.

        Default: no stored vector (callers re-embed). Backends override to expose
        their stored vectors so `relio migrate` can preserve them instead of
        re-embedding. See ADR-002.
        """
        for record in self.all():
            yield record, None

    @abstractmethod
    def query(
        self,
        *,
        type: Optional[MemoryType] = None,
        scope: Optional[Scope] = None,
        where: Optional[dict] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        """Structured (non-semantic) filter. `where` keys support operators via a
        `field__op` suffix (`gt/gte/lt/lte/contains`, default exact). `order_by` is
        a metadata field (`-field` = descending; default insertion order). Includes
        non-embedded records (unlike search())."""

    @abstractmethod
    def transaction(self) -> "ContextManager[None]":
        """Context manager grouping writes into one atomic unit: all commit on
        clean exit, all roll back if the block raises."""

    @abstractmethod
    def close(self) -> None:
        ...
