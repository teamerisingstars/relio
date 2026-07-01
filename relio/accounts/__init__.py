# relio/accounts/__init__.py
"""User accounts for Relio apps: user store, password login, and Google OAuth.

The login flow issues a JWT that `relio.server.auth.JWTAuth` verifies — so this
module produces identity, and the existing auth hook consumes it.

    pip install "relio[accounts]"
"""
from .google import GoogleOAuth
from .passwords import hash_password, verify_password
from .routes import build_accounts_router
from .store import InMemoryUserStore, SqliteUserStore, User, UserStore
from .tokens import issue_token

__all__ = [
    "hash_password",
    "verify_password",
    "User",
    "UserStore",
    "InMemoryUserStore",
    "SqliteUserStore",
    "issue_token",
    "GoogleOAuth",
    "build_accounts_router",
]
