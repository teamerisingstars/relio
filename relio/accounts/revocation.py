# relio/accounts/revocation.py
from __future__ import annotations

from typing import Protocol


class RevocationStore(Protocol):
    """Tracks revoked refresh-token ids (`jti`) so a token can be invalidated
    before it expires — enabling real logout, rotation, and theft response."""

    def revoke(self, jti: str, exp: int) -> None: ...

    def is_revoked(self, jti: str) -> bool: ...


class InMemoryRevocationStore:
    """Process-local denylist — fine for a single worker / tests. For multiple
    workers use a shared store (e.g. Redis) implementing the same protocol."""

    def __init__(self) -> None:
        self._revoked: dict[str, int] = {}  # jti -> exp (kept for later pruning)

    def revoke(self, jti: str, exp: int = 0) -> None:
        if jti:
            self._revoked[jti] = exp

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked
