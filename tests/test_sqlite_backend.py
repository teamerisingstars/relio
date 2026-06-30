# tests/test_sqlite_backend.py  (start the file — backend ABC contract)
import pytest
from relio.backends.base import StorageBackend


def test_storage_backend_is_abstract():
    with pytest.raises(TypeError):
        StorageBackend()  # cannot instantiate an abstract class


# tests/test_sqlite_backend.py  (append)
from relio.backends.sqlite import SQLiteBackend
from relio.record import MemoryRecord, MemoryType, Scope


def test_add_get_roundtrip(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=4)
    r = MemoryRecord(content="hello", scope=Scope(user="alice"))
    be.add(r, [0.1, 0.2, 0.3, 0.4])
    got = be.get(r.id)
    assert got is not None
    assert got.content == "hello"
    assert got.scope.user == "alice"
    be.close()


def test_delete_returns_true_then_false(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=4)
    r = MemoryRecord(content="bye")
    be.add(r, None)
    assert be.delete(r.id) is True
    assert be.delete(r.id) is False
    assert be.get(r.id) is None
    be.close()


def test_all_returns_every_record(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=4)
    be.add(MemoryRecord(content="a"), None)
    be.add(MemoryRecord(content="b"), None)
    assert {r.content for r in be.all()} == {"a", "b"}
    be.close()


# tests/test_sqlite_backend.py  (append)
def test_search_orders_by_distance(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=3)
    near = MemoryRecord(content="near")
    far = MemoryRecord(content="far")
    be.add(near, [1.0, 0.0, 0.0])
    be.add(far, [0.0, 1.0, 0.0])
    results = be.search([0.9, 0.1, 0.0], k=2)
    assert [r.content for r, _ in results] == ["near", "far"]
    assert results[0][1] <= results[1][1]
    be.close()


def test_search_ignores_records_without_embeddings(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=3)
    be.add(MemoryRecord(content="has_vec"), [1.0, 0.0, 0.0])
    be.add(MemoryRecord(content="no_vec"), None)
    results = be.search([1.0, 0.0, 0.0], k=5)
    assert [r.content for r, _ in results] == ["has_vec"]
    be.close()
