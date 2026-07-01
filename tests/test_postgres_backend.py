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
