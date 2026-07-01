# tests/test_backend_conformance.py
#
# ONE contract, run against EVERY StorageBackend — this is the anti-drift suite
# ADR-002 calls for. SQLite runs always (in-process); Postgres runs only when
# RELIO_TEST_DATABASE_URL points at a Postgres with the `vector` extension.
#
# To add a backend: extend `_BACKENDS`. To assert a contract: write it once here
# and both backends are held to it. Do NOT hand-mirror backend tests again.
import os

import pytest

from relio.backends.base import StorageBackend
from relio.record import MemoryRecord, MemoryType, Scope

DSN = os.environ.get("RELIO_TEST_DATABASE_URL")


def _sqlite_factory(tmp_path):
    from relio.backends.sqlite import SQLiteBackend

    created = []

    def make(dim):
        be = SQLiteBackend(str(tmp_path / f"m{dim}_{len(created)}.db"), dim=dim)
        created.append(be)
        return be

    yield make
    for be in created:
        be.close()


def _postgres_factory():
    import psycopg

    from relio.backends.postgres import PostgresBackend

    created = []

    def make(dim):
        # Fresh table per backend so `dim`/order are deterministic.
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("DROP TABLE IF EXISTS records")
        be = PostgresBackend(DSN, dim=dim)
        created.append(be)
        return be

    yield make
    for be in created:
        be.close()


@pytest.fixture(params=["sqlite", "postgres"])
def make_backend(request, tmp_path):
    """A factory `make(dim) -> StorageBackend`, parameterized across backends."""
    if request.param == "sqlite":
        yield from _sqlite_factory(tmp_path)
    else:
        if DSN is None:
            pytest.skip("set RELIO_TEST_DATABASE_URL to run the Postgres conformance suite")
        yield from _postgres_factory()


# --- the abstract base itself ----------------------------------------------

def test_storage_backend_is_abstract():
    with pytest.raises(TypeError):
        StorageBackend()  # cannot instantiate an abstract class


# --- CRUD ------------------------------------------------------------------

def test_add_get_roundtrip(make_backend):
    be = make_backend(4)
    r = MemoryRecord(content="hello", scope=Scope(user="alice"))
    be.add(r, [0.1, 0.2, 0.3, 0.4])
    got = be.get(r.id)
    assert got is not None and got.content == "hello" and got.scope.user == "alice"


def test_get_missing_returns_none(make_backend):
    assert make_backend(4).get("nope") is None


def test_delete_returns_true_then_false(make_backend):
    be = make_backend(4)
    r = MemoryRecord(content="bye")
    be.add(r, None)
    assert be.delete(r.id) is True
    assert be.delete(r.id) is False
    assert be.get(r.id) is None


def test_all_returns_records_in_insertion_order(make_backend):
    be = make_backend(4)
    for c in ("a", "b", "c"):
        be.add(MemoryRecord(content=c), None)
    assert [r.content for r in be.all()] == ["a", "b", "c"]


def test_upsert_replaces_in_place_preserving_order(make_backend):
    be = make_backend(3)
    first = MemoryRecord(content="first")
    be.add(first, [1.0, 0.0, 0.0])
    be.add(MemoryRecord(content="second"), [0.0, 1.0, 0.0])
    first.content = "first-edited"
    be.add(first, [0.0, 0.0, 1.0])  # same id
    assert [r.content for r in be.all()] == ["first-edited", "second"]  # no dup, order kept


# --- vector search ----------------------------------------------------------

def test_search_orders_by_distance(make_backend):
    be = make_backend(3)
    be.add(MemoryRecord(content="near"), [1.0, 0.0, 0.0])
    be.add(MemoryRecord(content="far"), [0.0, 1.0, 0.0])
    results = be.search([0.9, 0.1, 0.0], k=2)
    assert [r.content for r, _ in results] == ["near", "far"]
    assert results[0][1] <= results[1][1]


def test_search_ignores_records_without_embeddings(make_backend):
    be = make_backend(3)
    be.add(MemoryRecord(content="has_vec"), [1.0, 0.0, 0.0])
    be.add(MemoryRecord(content="no_vec"), None)
    assert [r.content for r, _ in be.search([1.0, 0.0, 0.0], k=5)] == ["has_vec"]


# --- structured query -------------------------------------------------------

def _seed_query(be):
    be.add(MemoryRecord(content="a", type=MemoryType.FACT,
                        metadata={"amount": 100, "name": "alpha"}), None)
    be.add(MemoryRecord(content="b", type=MemoryType.SEMANTIC,
                        metadata={"amount": 500, "name": "beta"}), None)
    be.add(MemoryRecord(content="c", type=MemoryType.SEMANTIC,
                        metadata={"amount": 900, "name": "gamma"}), None)


def test_query_by_type_and_metadata_eq(make_backend):
    be = make_backend(4)
    _seed_query(be)
    assert [r.content for r in be.query(type=MemoryType.FACT)] == ["a"]
    assert [r.content for r in be.query(where={"name": "beta"})] == ["b"]


def test_query_range_and_membership_operators(make_backend):
    be = make_backend(4)
    _seed_query(be)
    assert {r.content for r in be.query(where={"amount__gt": 400})} == {"b", "c"}
    assert {r.content for r in be.query(where={"amount__lte": 500})} == {"a", "b"}
    assert {r.content for r in be.query(where={"amount__ne": 500})} == {"a", "c"}
    assert {r.content for r in be.query(where={"amount__in": [100, 900]})} == {"a", "c"}
    assert {r.content for r in be.query(where={"name__contains": "amm"})} == {"c"}   # gamma
    assert {r.content for r in be.query(where={"name__startswith": "al"})} == {"a"}  # alpha


def test_query_order_by_and_pagination(make_backend):
    be = make_backend(4)
    _seed_query(be)
    assert [r.metadata["amount"] for r in be.query(order_by="-amount")] == [900, 500, 100]
    page = be.query(order_by="amount", limit=1, offset=1)
    assert [r.metadata["amount"] for r in page] == [500]


def test_query_filters_by_scope(make_backend):
    be = make_backend(4)
    be.add(MemoryRecord(content="acme", scope=Scope(tenant="acme")), None)
    be.add(MemoryRecord(content="other", scope=Scope(tenant="other")), None)
    assert [r.content for r in be.query(scope=Scope(tenant="acme"))] == ["acme"]


# --- transactions -----------------------------------------------------------

def test_transaction_rolls_back_on_error(make_backend):
    be = make_backend(4)
    be.add(MemoryRecord(content="pre"), None)
    with pytest.raises(RuntimeError):
        with be.transaction():
            be.add(MemoryRecord(content="mid"), None)
            raise RuntimeError("boom")
    assert [r.content for r in be.all()] == ["pre"]
