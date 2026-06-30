# relio/backends/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ContextManager, Optional

from ..record import MemoryRecord, MemoryType, Scope


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
        """Return up to k nearest records as (record, distance), ascending distance."""

    @abstractmethod
    def all(self) -> list[MemoryRecord]:
        """Return every record in insertion order (oldest first).

        History relies on this ordering; backends must preserve it.
        """

    @abstractmethod
    def query(
        self,
        *,
        type: Optional[MemoryType] = None,
        scope: Optional[Scope] = None,
        metadata: Optional[dict[str, str]] = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """Structured (non-semantic) filter by exact type / scope / metadata
        equality, returned in insertion order. Unlike search(), this includes
        records with no embedding."""

    @abstractmethod
    def transaction(self) -> "ContextManager[None]":
        """Context manager grouping writes into one atomic unit: all commit on
        clean exit, all roll back if the block raises."""

    @abstractmethod
    def close(self) -> None:
        ...
