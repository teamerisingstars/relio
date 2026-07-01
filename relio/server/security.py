# relio/server/security.py
from __future__ import annotations

import logging

logger = logging.getLogger("relio")


class RateLimiter:
    """Fixed-window, in-process rate limiter (per key). Good enough for a single
    node; front with a shared store (Redis) when you scale out."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, tuple[float, int]] = {}

    def allow(self, key: str, now: float) -> bool:
        start, count = self._hits.get(key, (now, 0))
        if now - start >= self.window:
            start, count = now, 0
        count += 1
        self._hits[key] = (start, count)
        return count <= self.limit
