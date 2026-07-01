from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from ..record import MemoryRecord, MemoryType, Scope
from .base import StorageBackend, split_op

_KEY = re.compile(r"^\w+$")  # guard interpolated json paths against injection
_SQL_OP = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "ne": "!="}


def _is_number(v: object) -> bool:
    # bool is an int subclass, but JSON booleans extract to 'true'/'false' text —
    # don't numeric-cast them.
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _vector_literal(embedding: list[float]) -> str:
    """pgvector text form: [a,b,c]."""
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"


def _to_record(doc) -> MemoryRecord:
    # psycopg returns JSONB as a parsed dict; tolerate text too.
    if isinstance(doc, (dict, list)):
        return MemoryRecord.model_validate(doc)
    return MemoryRecord.model_validate_json(doc)


class PostgresBackend(StorageBackend):
    """Postgres + pgvector backend — behaviour-identical to SQLiteBackend.

    The scale path for high write-concurrency or many millions of vectors. A
    connection **pool** lets independent requests run concurrently (no global
    lock). Within `transaction()`, one connection is bound to the current
    context so nested writes share it and commit atomically.
    """

    def __init__(self, dsn: str, dim: int = 384, pool_size: int = 10) -> None:
        from psycopg_pool import ConnectionPool  # lazy: only when Postgres is used

        self.dim = dim
        # Holds the transaction's connection for the current context (else None).
        self._active: ContextVar[Optional[object]] = ContextVar(
            "relio_pg_active", default=None
        )
        self._pool = ConnectionPool(
            dsn, min_size=1, max_size=pool_size, kwargs={"autocommit": True}, open=True
        )
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[object]:
        """Yield the transaction-bound connection if inside one, else a pooled one."""
        active = self._active.get()
        if active is not None:
            yield active
        else:
            with self._pool.connection() as conn:
                yield conn

    def _init_schema(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS records (
                    rid        BIGSERIAL PRIMARY KEY,
                    id         TEXT UNIQUE NOT NULL,
                    doc        JSONB NOT NULL,
                    expires_at DOUBLE PRECISION,
                    embedding  vector({self.dim})
                )
                """
            )
            # GIN index makes structured query() (Feature J) indexed on jsonb.
            cur.execute("CREATE INDEX IF NOT EXISTS idx_doc_gin ON records USING GIN (doc)")

    @staticmethod
    def _expires_at(record: MemoryRecord) -> float | None:
        if record.ttl is None:
            return None
        return record.created_at.timestamp() + record.ttl

    def add(self, record: MemoryRecord, embedding: list[float] | None) -> None:
        doc = record.model_dump_json()
        vec = _vector_literal(embedding) if embedding is not None else None
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO records (id, doc, expires_at, embedding)
                VALUES (%s, %s::jsonb, %s, %s::vector)
                ON CONFLICT (id) DO UPDATE
                SET doc = EXCLUDED.doc,
                    expires_at = EXCLUDED.expires_at,
                    embedding = EXCLUDED.embedding
                """,
                (record.id, doc, self._expires_at(record), vec),
            )

    def get(self, record_id: str) -> MemoryRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT doc FROM records WHERE id = %s", (record_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return _to_record(row[0])

    def delete(self, record_id: str) -> bool:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM records WHERE id = %s", (record_id,))
            return cur.rowcount > 0

    def all(self) -> list[MemoryRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT doc FROM records ORDER BY rid")
            rows = cur.fetchall()
        return [_to_record(r[0]) for r in rows]

    def iter_embeddings(self):
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT doc, embedding::text FROM records ORDER BY rid")
            rows = cur.fetchall()
        for doc, emb in rows:
            # pgvector text form is "[a,b,c]"; parse back to a float list.
            vector = [float(x) for x in emb.strip("[]").split(",") if x] if emb else None
            yield _to_record(doc), vector

    def search(self, embedding: list[float], k: int) -> list[tuple[MemoryRecord, float]]:
        vec = _vector_literal(embedding)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT doc, embedding <-> %s::vector AS distance
                FROM records
                WHERE embedding IS NOT NULL
                ORDER BY distance
                LIMIT %s
                """,
                (vec, k),
            )
            rows = cur.fetchall()
        return [(_to_record(r[0]), float(r[1])) for r in rows]

    def query(
        self,
        *,
        type: Optional[MemoryType] = None,
        scope: Optional[Scope] = None,
        where: Optional[dict] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if type is not None:
            clauses.append("doc->>'type' = %s")
            params.append(type.value)
        if scope is not None:
            for field in ("tenant", "user", "agent", "session"):
                value = getattr(scope, field)
                if value is not None:
                    clauses.append(f"doc#>>'{{scope,{field}}}' = %s")
                    params.append(value)
        for key, value in (where or {}).items():
            field, op = split_op(key)
            if not _KEY.match(field):
                raise ValueError(f"invalid where field: {field!r}")
            col = f"doc#>>'{{metadata,{field}}}'"
            if op == "contains":
                clauses.append(f"{col} LIKE %s")
                params.append(f"%{value}%")
            elif op == "startswith":
                clauses.append(f"{col} LIKE %s")
                params.append(f"{value}%")
            elif op == "in":
                # `#>>` yields text; cast to numeric when the values are numbers so
                # `IN (100, 900)` matches (SQLite compares typed values natively).
                values = list(value)
                placeholders = ", ".join("%s" for _ in values)
                lhs = f"({col})::numeric" if values and all(_is_number(v) for v in values) else col
                clauses.append(f"{lhs} IN ({placeholders})")
                params.extend(values)
            elif op == "ne":
                lhs = f"({col})::numeric" if _is_number(value) else col
                clauses.append(f"{lhs} != %s")
                params.append(value)
            elif op in _SQL_OP:
                clauses.append(f"({col})::numeric {_SQL_OP[op]} %s")
                params.append(value)
            else:  # exact equality
                lhs = f"({col})::numeric" if _is_number(value) else col
                clauses.append(f"{lhs} = %s")
                params.append(value)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        order_sql = " ORDER BY rid"
        if order_by:
            desc = order_by.startswith("-")
            field = order_by.lstrip("-")
            if not _KEY.match(field):
                raise ValueError(f"invalid order_by field: {field!r}")
            # `#>` keeps the value as jsonb so ordering is by value (numbers sort
            # numerically, strings lexically) — matching SQLite's typed json_extract.
            # `#>>` (text) would sort numbers lexicographically ("100" < "9").
            order_sql = f" ORDER BY doc#>'{{metadata,{field}}}' {'DESC' if desc else 'ASC'}"
        params += [limit, offset]
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT doc FROM records{where_sql}{order_sql} LIMIT %s OFFSET %s", params
            )
            rows = cur.fetchall()
        return [_to_record(r[0]) for r in rows]

    @contextmanager
    def transaction(self) -> Iterator[None]:
        # Borrow one connection, bind it for this context so nested add()/delete()
        # reuse it, and wrap the block in a single BEGIN/COMMIT.
        with self._pool.connection() as conn:
            token = self._active.set(conn)
            try:
                with conn.transaction():
                    yield
            finally:
                self._active.reset(token)

    def sql(self, query: str, params: Optional[tuple] = None) -> list[dict]:
        """Run a **read-only** analytical SQL query against the `records` table and
        return rows as dicts. The escape hatch for joins / GROUP BY / window
        functions over the JSONB doc — things `query()` deliberately doesn't do.

        Records live in `records(rid, id, doc JSONB, expires_at, embedding)`; pull
        fields with `doc->>'content'`, `doc->'metadata'->>'roas'`, etc. Only a
        single SELECT/WITH statement is allowed; use `params` for values (never
        string-format them in).

            be.sql("SELECT doc->'metadata'->>'campaign' c, avg((doc->'metadata'->>'roas')::float) "
                   "FROM records GROUP BY c ORDER BY 2 DESC")
        """
        stripped = query.lstrip().lower()
        if not (stripped.startswith("select") or stripped.startswith("with")):
            raise ValueError("sql() is read-only: only SELECT / WITH queries are allowed")
        if ";" in query.rstrip().rstrip(";"):
            raise ValueError("sql() runs a single statement; ';' is not allowed")
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            cols = [d.name for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self._pool.close()
