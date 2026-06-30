# src/relio/embedding/cache.py
from __future__ import annotations

import hashlib

from .base import Embedder


class CachingEmbedder(Embedder):
    """Wraps an embedder with an in-process dedup cache keyed by content hash."""

    def __init__(self, inner: Embedder) -> None:
        self._inner = inner
        self._cache: dict[str, list[float]] = {}

    @property
    def dim(self) -> int:
        return self._inner.dim

    def embed(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode()).hexdigest()
        if key not in self._cache:
            self._cache[key] = self._inner.embed(text)
        return self._cache[key]
