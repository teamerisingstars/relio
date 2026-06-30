from __future__ import annotations

from typing import Callable, Iterator

from ..memory import Memory
from ..record import Scope
from ..render import render_lines
from .llm.base import LLMProvider, Message


def default_capture(memory: Memory, message: str, reply: str, scope: Scope) -> None:
    """Heuristic extraction: store the user's message as a memory."""
    memory.add(message, scope=scope)


def run_chat(
    memory: Memory,
    provider: LLMProvider,
    message: str,
    scope: Scope,
    limit: int = 5,
    capture: Callable[[Memory, str, str, Scope], None] = default_capture,
) -> Iterator[str]:
    recalled = memory.recall(message, scope=scope, limit=limit)
    if recalled:
        system = "What you remember:\n" + render_lines(recalled)
    else:
        system = "You have no memories about this yet."
    parts: list[str] = []
    for chunk in provider.stream([Message(role="user", content=message)], system):
        parts.append(chunk)
        yield chunk
    capture(memory, message, "".join(parts), scope)
