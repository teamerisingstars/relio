# tests/test_record.py
from relio.record import MemoryRecord, MemoryType, Scope, Relation


def test_defaults_make_a_semantic_record_with_generated_id():
    r = MemoryRecord(content="Alice prefers Python")
    assert r.id.startswith("mem_")
    assert r.type is MemoryType.SEMANTIC
    assert r.content == "Alice prefers Python"
    assert r.data == {}
    assert r.relations == []
    assert r.scope == Scope()
    assert r.ttl is None
    assert r.schema_version == "1.0"


def test_episodic_memory_type_is_available():
    r = MemoryRecord(type=MemoryType.EPISODIC, content="deploy at 10:04")
    assert r.type is MemoryType.EPISODIC
    assert MemoryType("episodic") is MemoryType.EPISODIC
    assert MemoryRecord.model_validate(r.model_dump()).type is MemoryType.EPISODIC


def test_roundtrips_through_dict():
    r = MemoryRecord(
        type=MemoryType.FACT,
        content="works at Acme",
        data={"employer": "Acme"},
        relations=[Relation(predicate="works_at", target_id="mem_org")],
        scope=Scope(user="alice", tenant="acme"),
        ttl=3600,
    )
    again = MemoryRecord.model_validate(r.model_dump())
    assert again == r
    assert again.relations[0].predicate == "works_at"
    assert again.scope.user == "alice"
