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
