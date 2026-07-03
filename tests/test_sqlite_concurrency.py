# tests/test_sqlite_concurrency.py
# Correctness gate for the thread-local-connection SQLite backend: concurrent
# readers + writers must never corrupt data, error, or lose writes.
import threading

from relio.backends.sqlite import SQLiteBackend
from relio.record import MemoryRecord, MemoryType, Scope


def _emb(i, dim=16):
    return [float((i + j) % 7) for j in range(dim)]


def test_concurrent_writes_and_reads_are_consistent(tmp_path):
    be = SQLiteBackend(str(tmp_path / "c.db"), dim=16)
    n_threads, per_thread = 8, 40
    errors: list[Exception] = []

    def worker(t: int):
        try:
            for i in range(per_thread):
                rid = f"t{t}-r{i}"
                be.add(MemoryRecord(id=rid, content=f"item {rid}",
                                    scope=Scope(user=f"u{t}")), _emb(t * 100 + i))
                # interleave reads on other threads' data
                be.get(rid)
                be.query(scope=Scope(user=f"u{t}"), limit=5)
                be.search(_emb(t * 100 + i), k=3)
        except Exception as e:  # any locking/threading error fails the gate
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert not errors, f"concurrent access raised: {errors[:3]}"
    # No writes lost or duplicated.
    all_ids = {r.id for r in be.all()}
    assert len(be.all()) == n_threads * per_thread
    for t in range(n_threads):
        for i in range(per_thread):
            assert f"t{t}-r{i}" in all_ids
    be.close()


def test_read_your_writes_within_a_transaction(tmp_path):
    # A thread must see its own uncommitted writes inside transaction() (same
    # connection) — the invariant that makes thread-local connections safe.
    be = SQLiteBackend(str(tmp_path / "t.db"), dim=16)
    with be.transaction():
        be.add(MemoryRecord(id="x", content="hi"), _emb(1))
        assert be.get("x") is not None            # own write, visible pre-commit
        assert any(r.id == "x" for r in be.all())
    assert be.get("x") is not None                # still there after commit
    be.close()
