# relio/accounts/store.py
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class User:
    id: str
    email: str
    password_hash: Optional[str] = None
    tenant: Optional[str] = None
    provider: str = "password"  # or "google"
    name: Optional[str] = None


class UserStore(Protocol):
    def create(
        self,
        email: str,
        *,
        password_hash: Optional[str] = None,
        tenant: Optional[str] = None,
        provider: str = "password",
        name: Optional[str] = None,
    ) -> User: ...

    def get_by_email(self, email: str) -> Optional[User]: ...

    def get_by_id(self, user_id: str) -> Optional[User]: ...


def _new_id() -> str:
    return "usr_" + uuid.uuid4().hex


class InMemoryUserStore:
    """Non-persistent store — fine for demos and tests."""

    def __init__(self) -> None:
        self._by_id: dict[str, User] = {}
        self._by_email: dict[str, User] = {}

    def create(self, email, *, password_hash=None, tenant=None, provider="password", name=None) -> User:
        if email in self._by_email:
            raise ValueError("email already registered")
        user = User(_new_id(), email, password_hash, tenant, provider, name)
        self._by_id[user.id] = user
        self._by_email[email] = user
        return user

    def get_by_email(self, email):
        return self._by_email.get(email)

    def get_by_id(self, user_id):
        return self._by_id.get(user_id)


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
                name TEXT
            )
            """
        )
        self._db.commit()

    def create(self, email, *, password_hash=None, tenant=None, provider="password", name=None) -> User:
        if self.get_by_email(email) is not None:
            raise ValueError("email already registered")
        user = User(_new_id(), email, password_hash, tenant, provider, name)
        self._db.execute(
            "INSERT INTO users (id, email, password_hash, tenant, provider, name) VALUES (?, ?, ?, ?, ?, ?)",
            (user.id, user.email, user.password_hash, user.tenant, user.provider, user.name),
        )
        self._db.commit()
        return user

    def get_by_email(self, email):
        row = self._db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return self._row(row)

    def get_by_id(self, user_id):
        row = self._db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row(row)

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
        )
