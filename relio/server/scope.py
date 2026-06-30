from __future__ import annotations

from typing import Optional

from ..record import Scope


def make_scope(
    tenant: Optional[str] = None,
    user: Optional[str] = None,
    agent: Optional[str] = None,
    session: Optional[str] = None,
) -> Scope:
    """Build a Scope from request fields. The seam the auth hook later replaces."""
    return Scope(tenant=tenant, user=user, agent=agent, session=session)
