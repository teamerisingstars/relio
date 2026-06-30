# src/relio/render.py
from __future__ import annotations

from .record import MemoryRecord


def _suffix(record: MemoryRecord) -> str:
    parts: list[str] = []
    tags = record.metadata.get("tags")
    if tags:
        parts.extend(str(t) for t in tags)
    conf = record.metadata.get("confidence")
    if conf is not None:
        parts.append(str(conf))
    return f" ({', '.join(parts)})" if parts else ""


def render_lines(records: list[MemoryRecord]) -> str:
    """Render memories as token-light natural-language lines (no JSON)."""
    return "\n".join(f"- {r.content}{_suffix(r)}" for r in records)
