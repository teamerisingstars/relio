# relio/interchange.py
from __future__ import annotations

from typing import Any

from .memory import Memory
from .record import MemoryRecord, Scope


def export_records(memory: Memory) -> str:
    """Serialize all records to a JSON-lines string (the portable interchange form)."""
    return "\n".join(r.model_dump_json() for r in memory._backend.all())


def import_records(memory: Memory, blob: str) -> int:
    """Load records from a JSON-lines blob. Returns the number imported."""
    count = 0
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        record = MemoryRecord.model_validate_json(line)
        embedding = memory._embedder.embed(record.content) if record.content else None
        memory._backend.add(record, embedding)
        count += 1
    return count


def import_record_objects(memory: Memory, records: list[MemoryRecord]) -> int:
    """Load already-parsed records (e.g. from `from_mem0`) into a Memory. Returns count."""
    count = 0
    for record in records:
        embedding = memory._embedder.embed(record.content) if record.content else None
        memory._backend.add(record, embedding)
        count += 1
    return count


def from_mem0(rows: list[dict[str, Any]]) -> tuple[list[MemoryRecord], int]:
    """Map mem0-style export rows into Relio records. Returns (records, skipped)."""
    records: list[MemoryRecord] = []
    skipped = 0
    for row in rows:
        text = row.get("memory") or row.get("text")
        if not text:
            skipped += 1
            continue
        records.append(
            MemoryRecord(
                content=text,
                scope=Scope(user=row.get("user_id")),
                metadata={"imported_from": "mem0", "source_id": row.get("id")},
            )
        )
    return records, skipped
