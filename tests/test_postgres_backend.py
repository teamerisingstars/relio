# tests/test_postgres_backend.py
#
# The StorageBackend *contract* is verified for Postgres by the shared
# conformance suite (tests/test_backend_conformance.py) when
# RELIO_TEST_DATABASE_URL is set — no more hand-mirrored per-backend tests.
#
# What remains here is Postgres-specific *wiring* that isn't part of the backend
# contract: that Memory(database_url=...) selects Postgres and recall works
# end-to-end through it.
import os

import pytest

from relio.record import Scope

DSN = os.environ.get("RELIO_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(DSN is None, reason="set RELIO_TEST_DATABASE_URL to run"),
]


def test_sql_analytics_groups_and_guards_read_only():
    import psycopg

    from relio.backends.postgres import PostgresBackend
    from relio.record import MemoryRecord, MemoryType

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS records")
    be = PostgresBackend(DSN, dim=4)
    be.add(MemoryRecord(type=MemoryType.FACT, metadata={"campaign": "c1", "roas": 3.0}), None)
    be.add(MemoryRecord(type=MemoryType.FACT, metadata={"campaign": "c1", "roas": 5.0}), None)
    be.add(MemoryRecord(type=MemoryType.FACT, metadata={"campaign": "c2", "roas": 1.0}), None)

    rows = be.sql(
        "SELECT doc->'metadata'->>'campaign' AS campaign, "
        "avg((doc->'metadata'->>'roas')::float) AS avg_roas "
        "FROM records GROUP BY campaign ORDER BY avg_roas DESC"
    )
    assert rows[0]["campaign"] == "c1" and rows[0]["avg_roas"] == 4.0

    # read-only guard: writes are rejected before hitting the DB
    for bad in ("DELETE FROM records", "SELECT 1; DROP TABLE records"):
        try:
            be.sql(bad)
            assert False, "expected ValueError"
        except ValueError:
            pass
    be.close()


def test_memory_builds_postgres_backend_from_url():
    import psycopg

    from relio.backends.postgres import PostgresBackend
    from relio.embedding.base import DeterministicEmbedder
    from relio.memory import Memory

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS records")
    m = Memory(database_url=DSN, embedder=DeterministicEmbedder(dim=16))
    assert isinstance(m._backend, PostgresBackend)
    m.add("Alice works at Acme", scope=Scope(user="alice"))
    assert any("Acme" in r.content for r in m.recall("where does Alice work?", limit=3))
    m.close()
