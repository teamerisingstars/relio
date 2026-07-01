# relio/accounts/__init__.py
"""User accounts for Relio apps: user store, password login, and Google OAuth.

The login flow issues a JWT that `relio.server.auth.JWTAuth` verifies — so this
module produces identity, and the existing auth hook consumes it.

    pip install "relio[accounts]"
"""
from .github import GitHubOAuth
from .google import GoogleOAuth
from .microsoft import MicrosoftOAuth
from .passwords import hash_password, verify_password
from .routes import build_accounts_router
from .store import InMemoryUserStore, SqliteUserStore, User, UserStore
from .tokens import issue_reset_token, issue_token, issue_tokens, read_token

__all__ = [
    "hash_password",
    "verify_password",
    "User",
    "UserStore",
    "InMemoryUserStore",
    "SqliteUserStore",
    "issue_token",
    "issue_tokens",
    "issue_reset_token",
    "read_token",
    "GoogleOAuth",
    "GitHubOAuth",
    "MicrosoftOAuth",
    "build_accounts_router",
]
