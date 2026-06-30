# tests/test_interchange.py
from relio.interchange import export_records, import_records, from_mem0
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder


def _mem(tmp_path, name="m.db"):
    return Memory(path=str(tmp_path / name), embedder=DeterministicEmbedder(dim=16))


def test_export_then_import_roundtrips(tmp_path):
    src = _mem(tmp_path, "src.db")
    src.add("fact one")
    src.add("fact two")
    blob = export_records(src)
    dst = _mem(tmp_path, "dst.db")
    count = import_records(dst, blob)
    assert count == 2
    assert {r.content for r in dst.recall("fact", limit=5)} == {"fact one", "fact two"}
    src.close()
    dst.close()


def test_from_mem0_records_are_importable_and_recallable(tmp_path):
    from relio.interchange import import_record_objects
    rows = [{"id": "a", "memory": "drinks green tea", "user_id": "alice"}]
    records, _ = from_mem0(rows)
    m = _mem(tmp_path, "mem0.db")
    assert import_record_objects(m, records) == 1
    results = m.recall("green tea", limit=5)
    assert any("green tea" in r.content for r in results)
    m.close()


def test_from_mem0_maps_to_records_and_skips_bad_rows():
    mem0_rows = [
        {"id": "a", "memory": "likes tea", "user_id": "alice"},
        {"id": "b"},  # malformed: no memory text
    ]
    records, skipped = from_mem0(mem0_rows)
    assert len(records) == 1
    assert records[0].content == "likes tea"
    assert records[0].scope.user == "alice"
    assert skipped == 1
