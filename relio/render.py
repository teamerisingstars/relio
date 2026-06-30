# relio/render.py
from __future__ import annotations

from typing import Optional

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


def render_lines(records: list[MemoryRecord], max_chars: Optional[int] = None) -> str:
    """Render memories as token-light natural-language lines (no JSON).

    With `max_chars`, stop adding lines once the budget is reached — a simple
    token budget for what gets injected into the LLM prompt (cost/latency lever).
    """
    lines: list[str] = []
    used = 0
    for r in records:
        line = f"- {r.content}{_suffix(r)}"
        if max_chars is not None and lines and used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)
