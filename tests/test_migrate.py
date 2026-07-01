# tests/test_migrate.py
from relio.backends.sqlite import SQLiteBackend
from relio.embedding.base import DeterministicEmbedder
from relio.migrate import migrate_records, open_backend
from relio.record import MemoryRecord, MemoryType, Scope

EMB = DeterministicEmbedder(dim=16)


def _seed(path):
    b = SQLiteBackend(path, dim=16)
    recs = [
        MemoryRecord(content="Alice works at Acme", scope=Scope(tenant="t1")),
        MemoryRecord(content="Bob likes coffee", scope=Scope(tenant="t1")),
        MemoryRecord(type=MemoryType.NODE, content="", data={"label": "graph-node"}),
    ]
    for r in recs:
        b.add(r, EMB.embed(r.content) if r.content else None)
    return b, recs


def test_migrate_preserves_records_and_ids(tmp_path):
    src, recs = _seed(str(tmp_path / "src.db"))
    dst = SQLiteBackend(str(tmp_path / "dst.db"), dim=16)

    n = migrate_records(src, dst, EMB)
    assert n == 3

    got = dst.all()
    assert [r.id for r in got] == [r.id for r in recs]        # ids + order preserved
    assert got[0].content == "Alice works at Acme"
    assert got[0].scope.tenant == "t1"
    assert got[2].type == MemoryType.NODE and got[2].data["label"] == "graph-node"
    src.close()
    dst.close()


def test_migrate_reembeds_so_recall_works_on_destination(tmp_path):
    src, _ = _seed(str(tmp_path / "src.db"))
    dst = SQLiteBackend(str(tmp_path / "dst.db"), dim=16)
    migrate_records(src, dst, EMB)

    hits = dst.search(EMB.embed("Alice works at Acme"), k=1)
    assert hits and hits[0][0].content == "Alice works at Acme"
    src.close()
    dst.close()


def test_migrate_no_embed_copies_records_without_vectors(tmp_path):
    src, recs = _seed(str(tmp_path / "src.db"))
    dst = SQLiteBackend(str(tmp_path / "dst.db"), dim=16)

    n = migrate_records(src, dst, EMB, embed=False)
    assert n == 3
    assert len(dst.all()) == 3               # records copied
    assert dst.search(EMB.embed("Alice"), k=5) == []   # but no vectors indexed
    src.close()
    dst.close()


def test_open_backend_picks_sqlite_for_a_path(tmp_path):
    b = open_backend(str(tmp_path / "x.db"), dim=16)
    assert isinstance(b, SQLiteBackend)
    b.close()
