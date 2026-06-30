from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import HTTPException, Request

from ..record import Scope
from .scope import make_scope

# An auth hook maps a request to its authenticated principal scope.
# Apps bring their own (JWT/OAuth) by supplying a different AuthHook.
AuthHook = Callable[[Request], Scope]


def anonymous_auth(request: Request) -> Scope:
    """Default hook: no identity. Client-claimed tenant/user is never trusted."""
    return Scope()


def _extract_key(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[len("bearer ") :].strip()
    return request.headers.get("x-api-key")


class ApiKeyAuth:
    """Minimal built-in: map an API key to a principal scope.

    keys = {"sk-alice": {"tenant": "acme", "user": "alice"}, ...}
    """

    def __init__(self, keys: dict[str, dict[str, Any]]) -> None:
        self._keys = keys

    def __call__(self, request: Request) -> Scope:
        key = _extract_key(request)
        principal = self._keys.get(key) if key is not None else None
        if principal is None:
            raise HTTPException(status_code=401, detail="invalid or missing API key")
        return make_scope(
            tenant=principal.get("tenant"),
            user=principal.get("user"),
            agent=principal.get("agent"),
        )
