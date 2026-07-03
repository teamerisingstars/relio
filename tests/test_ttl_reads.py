# tests/test_ttl_reads.py — expired records must be invisible on EVERY read path,
# not just recall() (regression: expiry was enforced only in RecallEngine).
from datetime import datetime, timedelta, timezone

from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.record import MemoryRecord, MemoryType


def _expired_session_record():
    return MemoryRecord(
        type=MemoryType.SESSION,
        content="stale turn",
        ttl=60,  # 60s TTL, but created an hour ago → long expired
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )


def test_expired_record_hidden_from_query_history_and_get(tmp_path):
    m = Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))
    rec = _expired_session_record()
    m.add_record(rec)

    assert m.get(rec.id) is None
    assert m.history() == []
    assert all(r.id != rec.id for r in m.query(type=MemoryType.SESSION))
    m.close()


def test_live_record_still_visible(tmp_path):
    m = Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))
    live = MemoryRecord(type=MemoryType.SESSION, content="fresh", ttl=3600)
    m.add_record(live)
    assert m.get(live.id) is not None
    assert len(m.history()) == 1
    m.close()
