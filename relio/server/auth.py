from __future__ import annotations

import hashlib
import time as _time
from typing import Any, Callable, Optional, Sequence

from fastapi import HTTPException, Request

from ..record import Scope
from .scope import make_scope


def hash_key(key: str) -> str:
    """SHA-256 of an API key, for storing keys hashed instead of in plaintext."""
    return hashlib.sha256(key.encode()).hexdigest()

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

    - `hashed=True` — the keys are SHA-256 digests (see `hash_key`), so no
      plaintext keys are stored at rest.
    - A principal may carry `expires_at` (unix seconds); expired keys are 401.
    """

    def __init__(
        self,
        keys: dict[str, dict[str, Any]],
        *,
        hashed: bool = False,
        now: Optional[Callable[[], float]] = None,
    ) -> None:
        self._keys = keys
        self._hashed = hashed
        self._now = now or _time.time

    def __call__(self, request: Request) -> Scope:
        key = _extract_key(request)
        if key is None:
            raise HTTPException(status_code=401, detail="invalid or missing API key")
        lookup = hash_key(key) if self._hashed else key
        principal = self._keys.get(lookup)
        if principal is None:
            raise HTTPException(status_code=401, detail="invalid or missing API key")
        expires_at = principal.get("expires_at")
        if expires_at is not None and self._now() > expires_at:
            raise HTTPException(status_code=401, detail="API key expired")
        return make_scope(
            tenant=principal.get("tenant"),
            user=principal.get("user"),
            agent=principal.get("agent"),
        )


class JWTAuth:
    """AuthHook that verifies a JWT bearer token and maps its claims to a
    principal scope. Bring your own IdP (Auth0 / Cognito / Clerk / ...).

    Requires the `jwt` extra::  pip install "relio[jwt]"

        auth = JWTAuth(secret, audience="my-api", tenant_claim="org")
        app = create_app(memory, provider, auth=auth)

    Signature, expiry (`exp`), audience, and issuer are all verified; anything
    invalid → 401.
    """

    def __init__(
        self,
        secret: str,
        *,
        algorithms: Sequence[str] = ("HS256",),
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
        tenant_claim: str = "tenant",
        user_claim: str = "sub",
        agent_claim: Optional[str] = None,
    ) -> None:
        self._secret = secret
        self._algorithms = list(algorithms)
        self._audience = audience
        self._issuer = issuer
        self._tenant_claim = tenant_claim
        self._user_claim = user_claim
        self._agent_claim = agent_claim

    def __call__(self, request: Request) -> Scope:
        token = _extract_key(request)
        if token is None:
            raise HTTPException(status_code=401, detail="missing bearer token")
        import jwt  # lazy: only needed when JWT auth is used

        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail="invalid token") from exc
        return make_scope(
            tenant=claims.get(self._tenant_claim),
            user=claims.get(self._user_claim),
            agent=claims.get(self._agent_claim) if self._agent_claim else None,
        )
