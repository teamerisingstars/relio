# relio/backends/sqlite.py
from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

import sqlite_vec

from ..record import MemoryRecord, MemoryType, Scope
from .base import StorageBackend

_KEY = re.compile(r"^\w+$")  # guard interpolated json paths against injection


class SQLiteBackend(StorageBackend):
    def __init__(self, path: str, dim: int = 384) -> None:
        self.dim = dim
        # The connection is shared across threads (FastAPI runs sync handlers in a
        # threadpool), so guard the multi-statement read-modify-write methods.
        # Reentrant so writes can nest inside a transaction() that already holds it.
        self._write_lock = threading.RLock()
        self._txn_depth = 0
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.enable_load_extension(True)
        sqlite_vec.load(self._db)
        self._db.enable_load_extension(False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                rid INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE NOT NULL,
                doc TEXT NOT NULL,
                expires_at REAL
            )
            """
        )
        self._db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_records "
            f"USING vec0(embedding float[{self.dim}])"
        )
        # Expression indexes so structured query() (Feature J) is indexed, not a scan.
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_type ON records(json_extract(doc, '$.type'))"
        )
        for field in ("tenant", "user", "agent", "session"):
            self._db.execute(
                f"CREATE INDEX IF NOT EXISTS idx_scope_{field} "
                f"ON records(json_extract(doc, '$.scope.{field}'))"
            )
        self._db.commit()

    def _maybe_commit(self) -> None:
        # Inside a transaction(), defer the commit until the block exits.
        if self._txn_depth == 0:
            self._db.commit()

    @staticmethod
    def _expires_at(record: MemoryRecord) -> float | None:
        if record.ttl is None:
            return None
        return record.created_at.timestamp() + record.ttl

    def add(self, record: MemoryRecord, embedding: list[float] | None) -> None:
        doc = record.model_dump_json()
        with self._write_lock:
            cur = self._db.execute(
                "SELECT rid FROM records WHERE id = ?", (record.id,)
            )
            row = cur.fetchone()
            if row is not None:
                rid = row["rid"]
                self._db.execute(
                    "UPDATE records SET doc = ?, expires_at = ? WHERE rid = ?",
                    (doc, self._expires_at(record), rid),
                )
                self._db.execute("DELETE FROM vec_records WHERE rowid = ?", (rid,))
            else:
                cur = self._db.execute(
                    "INSERT INTO records (id, doc, expires_at) VALUES (?, ?, ?)",
                    (record.id, doc, self._expires_at(record)),
                )
                rid = cur.lastrowid
            if embedding is not None:
                self._db.execute(
                    "INSERT INTO vec_records (rowid, embedding) VALUES (?, ?)",
                    (rid, sqlite_vec.serialize_float32(embedding)),
                )
            self._maybe_commit()

    def get(self, record_id: str) -> MemoryRecord | None:
        row = self._db.execute(
            "SELECT doc FROM records WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            return None
        return MemoryRecord.model_validate_json(row["doc"])

    def delete(self, record_id: str) -> bool:
        with self._write_lock:
            row = self._db.execute(
                "SELECT rid FROM records WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                return False
            rid = row["rid"]
            self._db.execute("DELETE FROM records WHERE rid = ?", (rid,))
            self._db.execute("DELETE FROM vec_records WHERE rowid = ?", (rid,))
            self._maybe_commit()
            return True

    def all(self) -> list[MemoryRecord]:
        rows = self._db.execute("SELECT doc FROM records ORDER BY rid").fetchall()
        return [MemoryRecord.model_validate_json(r["doc"]) for r in rows]

    def query(
        self,
        *,
        type: Optional[MemoryType] = None,
        scope: Optional[Scope] = None,
        metadata: Optional[dict[str, str]] = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if type is not None:
            clauses.append("json_extract(doc, '$.type') = ?")
            params.append(type.value)
        if scope is not None:
            for field in ("tenant", "user", "agent", "session"):
                value = getattr(scope, field)
                if value is not None:
                    clauses.append(f"json_extract(doc, '$.scope.{field}') = ?")
                    params.append(value)
        for key, value in (metadata or {}).items():
            if not _KEY.match(key):
                raise ValueError(f"invalid metadata key: {key!r}")
            clauses.append(f"json_extract(doc, '$.metadata.{key}') = ?")
            params.append(value)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = self._db.execute(
            f"SELECT doc FROM records{where} ORDER BY rid LIMIT ?", params
        ).fetchall()
        return [MemoryRecord.model_validate_json(r["doc"]) for r in rows]

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._write_lock:
            self._txn_depth += 1
            try:
                yield
            except Exception:
                self._txn_depth -= 1
                self._db.rollback()
                raise
            self._txn_depth -= 1
            self._maybe_commit()

    def search(self, embedding: list[float], k: int) -> list[tuple[MemoryRecord, float]]:
        rows = self._db.execute(
            """
            SELECT r.doc AS doc, v.distance AS distance
            FROM vec_records v
            JOIN records r ON r.rid = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
            """,
            (sqlite_vec.serialize_float32(embedding), k),
        ).fetchall()
        return [
            (MemoryRecord.model_validate_json(r["doc"]), float(r["distance"]))
            for r in rows
        ]

    def close(self) -> None:
        self._db.close()
