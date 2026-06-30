# tests/test_postgres_backend.py
#
# Live-database contract tests for PostgresBackend. They mirror the SQLite
# contract so both backends are held to identical behaviour. Skipped unless
# RELIO_TEST_DATABASE_URL points at a Postgres with the `vector` extension
# available. Run with:  RELIO_TEST_DATABASE_URL=postgresql://... pytest -m integration
import os

import pytest

from relio.record import MemoryRecord, MemoryType, Scope

DSN = os.environ.get("RELIO_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(DSN is None, reason="set RELIO_TEST_DATABASE_URL to run"),
]


def _backend(dim):
    """A PostgresBackend on a freshly-dropped `records` table for this dim."""
    import psycopg

    from relio.backends.postgres import PostgresBackend

    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS records")
    return PostgresBackend(DSN, dim=dim)


def test_add_get_roundtrip():
    be = _backend(4)
    r = MemoryRecord(content="hello", scope=Scope(user="alice"))
    be.add(r, [0.1, 0.2, 0.3, 0.4])
    got = be.get(r.id)
    assert got is not None
    assert got.content == "hello"
    assert got.scope.user == "alice"
    be.close()


def test_delete_returns_true_then_false():
    be = _backend(4)
    r = MemoryRecord(content="bye")
    be.add(r, None)
    assert be.delete(r.id) is True
    assert be.delete(r.id) is False
    assert be.get(r.id) is None
    be.close()


def test_all_returns_records_in_insertion_order():
    be = _backend(4)
    be.add(MemoryRecord(content="a"), None)
    be.add(MemoryRecord(content="b"), None)
    be.add(MemoryRecord(content="c"), None)
    assert [r.content for r in be.all()] == ["a", "b", "c"]
    be.close()


def test_search_orders_by_distance():
    be = _backend(3)
    near = MemoryRecord(content="near")
    far = MemoryRecord(content="far")
    be.add(near, [1.0, 0.0, 0.0])
    be.add(far, [0.0, 1.0, 0.0])
    results = be.search([0.9, 0.1, 0.0], k=2)
    assert [r.content for r, _ in results] == ["near", "far"]
    assert results[0][1] <= results[1][1]
    be.close()


def test_search_ignores_records_without_embeddings():
    be = _backend(3)
    be.add(MemoryRecord(content="has_vec"), [1.0, 0.0, 0.0])
    be.add(MemoryRecord(content="no_vec"), None)
    results = be.search([1.0, 0.0, 0.0], k=5)
    assert [r.content for r, _ in results] == ["has_vec"]
    be.close()


def test_upsert_replaces_in_place_preserving_order():
    be = _backend(3)
    first = MemoryRecord(content="first")
    be.add(first, [1.0, 0.0, 0.0])
    be.add(MemoryRecord(content="second"), [0.0, 1.0, 0.0])
    # Re-add `first` with new content/embedding under the same id.
    first.content = "first-edited"
    be.add(first, [0.0, 0.0, 1.0])
    contents = [r.content for r in be.all()]
    assert contents == ["first-edited", "second"]  # order preserved, no duplicate
    be.close()


def test_query_filters_by_type_and_metadata():
    be = _backend(4)
    be.add(MemoryRecord(content="x", type=MemoryType.FACT, metadata={"category": "task"}), None)
    be.add(MemoryRecord(content="y", type=MemoryType.SEMANTIC, metadata={"category": "idea"}), None)
    assert [r.content for r in be.query(type=MemoryType.FACT)] == ["x"]
    assert [r.content for r in be.query(metadata={"category": "idea"})] == ["y"]
    be.close()


def test_transaction_rolls_back_on_error():
    be = _backend(4)
    be.add(MemoryRecord(content="pre"), None)
    with pytest.raises(RuntimeError):
        with be.transaction():
            be.add(MemoryRecord(content="mid"), None)
            raise RuntimeError("boom")
    assert [r.content for r in be.all()] == ["pre"]
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
