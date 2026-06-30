# src/relio/backends/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from ..record import MemoryRecord


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
        ...

    @abstractmethod
    def close(self) -> None:
        ...
