# relio/accounts/store.py
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class User:
    id: str
    email: str
    password_hash: Optional[str] = None
    tenant: Optional[str] = None
    provider: str = "password"  # or google / github / microsoft
    name: Optional[str] = None
    profile: dict = field(default_factory=dict)  # app-specific data (intake, prefs, ...)


class UserStore(Protocol):
    def create(
        self,
        email: str,
        *,
        password_hash: Optional[str] = None,
        tenant: Optional[str] = None,
        provider: str = "password",
        name: Optional[str] = None,
        profile: Optional[dict] = None,
    ) -> User: ...

    def get_by_email(self, email: str) -> Optional[User]: ...

    def get_by_id(self, user_id: str) -> Optional[User]: ...

    def set_password(self, user_id: str, password_hash: str) -> None: ...

    def set_profile(self, user_id: str, profile: dict) -> None: ...

    def merge_profile(self, user_id: str, partial: dict) -> Optional[dict]: ...


def _new_id() -> str:
    return "usr_" + uuid.uuid4().hex


def _deep_merge(base: dict, partial: dict) -> dict:
    """Recursively merge `partial` into `base` (RFC 7386 / JSON-merge-patch style):
    nested dicts merge key-by-key; a `None` value deletes that key; everything else
    overwrites. Returns a new dict."""
    out = dict(base)
    for k, v in partial.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class InMemoryUserStore:
    """Non-persistent store — fine for demos and tests."""

    def __init__(self) -> None:
        self._by_id: dict[str, User] = {}
        self._by_email: dict[str, User] = {}

    def create(self, email, *, password_hash=None, tenant=None, provider="password", name=None, profile=None) -> User:
        if email in self._by_email:
            raise ValueError("email already registered")
        user = User(_new_id(), email, password_hash, tenant, provider, name, dict(profile or {}))
        self._by_id[user.id] = user
        self._by_email[email] = user
        return user

    def get_by_email(self, email):
        return self._by_email.get(email)

    def get_by_id(self, user_id):
        return self._by_id.get(user_id)

    def set_password(self, user_id, password_hash):
        user = self._by_id.get(user_id)
        if user is not None:
            user.password_hash = password_hash

    def set_profile(self, user_id, profile):
        user = self._by_id.get(user_id)
        if user is not None:
            user.profile = dict(profile or {})

    def merge_profile(self, user_id, partial):
        user = self._by_id.get(user_id)
        if user is None:
            return None
        user.profile = _deep_merge(user.profile, partial or {})
        return dict(user.profile)


class SqliteUserStore:
    """Persistent store in its own `users` table (separate from the memory DB)."""

    def __init__(self, path: str = "relio.db") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                tenant TEXT,
                provider TEXT NOT NULL DEFAULT 'password',
                name TEXT,
                profile TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        # Tolerate an older schema (add the profile column if missing).
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(users)")}
        if "profile" not in cols:
            self._db.execute("ALTER TABLE users ADD COLUMN profile TEXT NOT NULL DEFAULT '{}'")
        self._db.commit()

    def create(self, email, *, password_hash=None, tenant=None, provider="password", name=None, profile=None) -> User:
        if self.get_by_email(email) is not None:
            raise ValueError("email already registered")
        user = User(_new_id(), email, password_hash, tenant, provider, name, dict(profile or {}))
        self._db.execute(
            "INSERT INTO users (id, email, password_hash, tenant, provider, name, profile) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user.id, user.email, user.password_hash, user.tenant, user.provider, user.name,
             json.dumps(user.profile)),
        )
        self._db.commit()
        return user

    def get_by_email(self, email):
        row = self._db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return self._row(row)

    def get_by_id(self, user_id):
        row = self._db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row(row)

    def set_password(self, user_id, password_hash):
        self._db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )
        self._db.commit()

    def set_profile(self, user_id, profile):
        self._db.execute(
            "UPDATE users SET profile = ? WHERE id = ?", (json.dumps(profile or {}), user_id)
        )
        self._db.commit()

    def merge_profile(self, user_id, partial):
        # json_patch is RFC-7386 merge (recursive; null deletes) applied in a single
        # atomic UPDATE — no read-modify-write race between concurrent callers.
        self._db.execute(
            "UPDATE users SET profile = json_patch(profile, ?) WHERE id = ?",
            (json.dumps(partial or {}), user_id),
        )
        self._db.commit()
        user = self.get_by_id(user_id)
        return None if user is None else dict(user.profile)

    @staticmethod
    def _row(row) -> Optional[User]:
        if row is None:
            return None
        return User(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            tenant=row["tenant"],
            provider=row["provider"],
            name=row["name"],
            profile=json.loads(row["profile"] or "{}"),
        )
