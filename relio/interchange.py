# relio/interchange.py
from __future__ import annotations

from typing import Any

from .memory import Memory
from .record import MemoryRecord, Scope


def export_records(memory: Memory) -> str:
    """Serialize all records to a JSON-lines string (the portable interchange form)."""
    return "\n".join(r.model_dump_json() for r in memory.iter_records())


def import_records(memory: Memory, blob: str) -> int:
    """Load records from a JSON-lines blob. Returns the number imported."""
    count = 0
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        memory.add_record(MemoryRecord.model_validate_json(line))
        count += 1
    return count


def import_record_objects(memory: Memory, records: list[MemoryRecord]) -> int:
    """Load already-parsed records (e.g. from `from_mem0`) into a Memory. Returns count."""
    for record in records:
        memory.add_record(record)
    return len(records)


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
