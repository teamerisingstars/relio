# relio/backends/sqlite.py
from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

import sqlite_vec

from ..record import MemoryRecord, MemoryType, Scope
from .base import StorageBackend, split_op

_SQL_OP = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "ne": "!="}

_KEY = re.compile(r"^\w+$")  # guard interpolated json paths against injection


class SQLiteBackend(StorageBackend):
    """SQLite + sqlite-vec backend with per-thread connections.

    A single shared connection is unsafe under FastAPI's threadpool: concurrent
    reads/writes on one sqlite3 connection raise `InterfaceError` and can return
    corrupt rows. Instead each thread gets its own connection to the same WAL
    file — WAL permits many concurrent readers + one writer, so reads run in
    parallel. Writes are still serialized process-wide (SQLite = single writer)
    by `_write_lock`; a thread reads its own connection, so read-your-writes
    inside `transaction()` still holds. Transaction depth is per-thread too.
    """

    def __init__(self, path: str, dim: int = 384) -> None:
        self.dim = dim
        self._path = path
        # SQLite allows one writer at a time (even in WAL) — serialize writers
        # across threads. Reentrant so writes can nest inside transaction().
        self._write_lock = threading.RLock()
        self._local = threading.local()   # per-thread: .conn, .txn_depth
        self._conns: list[sqlite3.Connection] = []
        self._conns_lock = threading.Lock()
        self._init_schema()  # on this thread's connection; creates the file/tables

    def _new_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")  # wait out a checkpoint vs erroring
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        with self._conns_lock:
            self._conns.append(conn)
        return conn

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._new_conn()
            self._local.conn = conn
            self._local.txn_depth = 0
        return conn

    @property
    def _txn_depth(self) -> int:
        return getattr(self._local, "txn_depth", 0)

    @_txn_depth.setter
    def _txn_depth(self, value: int) -> None:
        self._local.txn_depth = value

    def _init_schema(self) -> None:
        self._conn().execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                rid INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE NOT NULL,
                doc TEXT NOT NULL,
                expires_at REAL
            )
            """
        )
        self._conn().execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_records "
            f"USING vec0(embedding float[{self.dim}])"
        )
        # Expression indexes so structured query() (Feature J) is indexed, not a scan.
        self._conn().execute(
            "CREATE INDEX IF NOT EXISTS idx_type ON records(json_extract(doc, '$.type'))"
        )
        for field in ("tenant", "user", "agent", "session"):
            self._conn().execute(
                f"CREATE INDEX IF NOT EXISTS idx_scope_{field} "
                f"ON records(json_extract(doc, '$.scope.{field}'))"
            )
        self._conn().commit()

    def _maybe_commit(self) -> None:
        # Inside a transaction(), defer the commit until the block exits.
        if self._txn_depth == 0:
            self._conn().commit()

    @staticmethod
    def _expires_at(record: MemoryRecord) -> float | None:
        if record.ttl is None:
            return None
        return record.created_at.timestamp() + record.ttl

    def add(self, record: MemoryRecord, embedding: list[float] | None) -> None:
        doc = record.model_dump_json()
        with self._write_lock:
            cur = self._conn().execute(
                "SELECT rid FROM records WHERE id = ?", (record.id,)
            )
            row = cur.fetchone()
            if row is not None:
                rid = row["rid"]
                self._conn().execute(
                    "UPDATE records SET doc = ?, expires_at = ? WHERE rid = ?",
                    (doc, self._expires_at(record), rid),
                )
                self._conn().execute("DELETE FROM vec_records WHERE rowid = ?", (rid,))
            else:
                cur = self._conn().execute(
                    "INSERT INTO records (id, doc, expires_at) VALUES (?, ?, ?)",
                    (record.id, doc, self._expires_at(record)),
                )
                rid = cur.lastrowid
            if embedding is not None:
                self._conn().execute(
                    "INSERT INTO vec_records (rowid, embedding) VALUES (?, ?)",
                    (rid, sqlite_vec.serialize_float32(embedding)),
                )
            self._maybe_commit()

    def get(self, record_id: str) -> MemoryRecord | None:
        row = self._conn().execute(
            "SELECT doc FROM records WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            return None
        return MemoryRecord.model_validate_json(row["doc"])

    def get_many(self, ids) -> dict[str, MemoryRecord]:
        ids = list(ids)
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        rows = self._conn().execute(
            f"SELECT doc FROM records WHERE id IN ({placeholders})", ids
        ).fetchall()
        recs = (MemoryRecord.model_validate_json(r["doc"]) for r in rows)
        return {r.id: r for r in recs}

    def delete(self, record_id: str) -> bool:
        with self._write_lock:
            row = self._conn().execute(
                "SELECT rid FROM records WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                return False
            rid = row["rid"]
            self._conn().execute("DELETE FROM records WHERE rid = ?", (rid,))
            self._conn().execute("DELETE FROM vec_records WHERE rowid = ?", (rid,))
            self._maybe_commit()
            return True

    def all(self) -> list[MemoryRecord]:
        rows = self._conn().execute("SELECT doc FROM records ORDER BY rid").fetchall()
        return [MemoryRecord.model_validate_json(r["doc"]) for r in rows]

    def iter_embeddings(self):
        import struct

        rows = self._conn().execute(
            "SELECT r.doc AS doc, v.embedding AS emb FROM records r "
            "LEFT JOIN vec_records v ON v.rowid = r.rid ORDER BY r.rid"
        ).fetchall()
        for row in rows:
            record = MemoryRecord.model_validate_json(row["doc"])
            emb = row["emb"]
            # sqlite-vec stores little-endian float32; unpack back to a list.
            vector = list(struct.unpack(f"<{self.dim}f", emb)) if emb is not None else None
            yield record, vector

    def query(
        self,
        *,
        type: Optional[MemoryType] = None,
        scope: Optional[Scope] = None,
        where: Optional[dict] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        newest_first: bool = False,
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
        for key, value in (where or {}).items():
            field, op = split_op(key)
            if not _KEY.match(field):
                raise ValueError(f"invalid where field: {field!r}")
            col = f"json_extract(doc, '$.metadata.{field}')"
            if op == "contains":
                clauses.append(f"{col} LIKE ?")
                params.append(f"%{value}%")
            elif op == "startswith":
                clauses.append(f"{col} LIKE ?")
                params.append(f"{value}%")
            elif op == "in":
                values = list(value)
                clauses.append(f"{col} IN ({', '.join('?' for _ in values)})")
                params.extend(values)
            else:
                clauses.append(f"{col} {_SQL_OP.get(op, '=')} ?")
                params.append(value)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        order_sql = " ORDER BY rid DESC" if newest_first else " ORDER BY rid"
        if order_by:
            desc = order_by.startswith("-")
            field = order_by.lstrip("-")
            if not _KEY.match(field):
                raise ValueError(f"invalid order_by field: {field!r}")
            order_sql = f" ORDER BY json_extract(doc, '$.metadata.{field}') {'DESC' if desc else 'ASC'}"
        params += [limit, offset]
        rows = self._conn().execute(
            f"SELECT doc FROM records{where_sql}{order_sql} LIMIT ? OFFSET ?", params
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
                self._conn().rollback()
                raise
            self._txn_depth -= 1
            self._maybe_commit()

    def search(self, embedding: list[float], k: int) -> list[tuple[MemoryRecord, float]]:
        rows = self._conn().execute(
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
        # Close every per-thread connection, not just the caller's.
        with self._conns_lock:
            for conn in self._conns:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._conns.clear()
        self._local = threading.local()
