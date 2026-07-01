# relio/accounts/tokens.py
from __future__ import annotations

import time as _time
from typing import Optional

from .store import User


def issue_token(
    user: User,
    secret: str,
    *,
    ttl: int = 3600,
    algorithm: str = "HS256",
    now: Optional[float] = None,
) -> str:
    """Issue a JWT for `user`, verifiable by `relio.server.auth.JWTAuth(secret)`.

    Claims: `sub` (user id), `email`, `tenant` (if set), `exp`.
    """
    import jwt  # lazy: needs the `jwt`/`accounts` extra

    issued = _time.time() if now is None else now
    payload = {"sub": user.id, "email": user.email, "exp": int(issued + ttl)}
    if user.tenant:
        payload["tenant"] = user.tenant
    return jwt.encode(payload, secret, algorithm=algorithm)


def issue_tokens(
    user: User,
    secret: str,
    *,
    access_ttl: int = 3600,
    refresh_ttl: int = 30 * 24 * 3600,
    now: Optional[float] = None,
) -> dict:
    """Issue both an access token and a longer-lived refresh token."""
    import jwt

    issued = _time.time() if now is None else now
    access = issue_token(user, secret, ttl=access_ttl, now=issued)
    refresh = jwt.encode(
        {"sub": user.id, "type": "refresh", "exp": int(issued + refresh_ttl)},
        secret,
        algorithm="HS256",
    )
    return {"access": access, "refresh": refresh}


def issue_reset_token(user: User, secret: str, *, ttl: int = 1800, now: Optional[float] = None) -> str:
    """Short-lived token proving a password-reset request (deliver it via email)."""
    import jwt

    issued = _time.time() if now is None else now
    return jwt.encode(
        {"sub": user.id, "type": "reset", "exp": int(issued + ttl)}, secret, algorithm="HS256"
    )


def read_token(token: str, secret: str, *, expected_type: Optional[str] = None) -> dict:
    """Verify a token and return its claims; raises on invalid/expired/wrong-type."""
    import jwt

    claims = jwt.decode(token, secret, algorithms=["HS256"])
    if expected_type is not None and claims.get("type") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return claims
