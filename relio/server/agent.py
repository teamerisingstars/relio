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
    history_limit: int = 20,
    system_prefix: str = "",
    capture: Callable[[Memory, str, str, Scope], None] = default_capture,
) -> Iterator[str]:
    recalled = memory.recall(message, scope=scope, limit=limit)
    if recalled:
        system = "What you remember:\n" + render_lines(recalled)
    else:
        system = "You have no memories about this yet."
    system = system_prefix + system  # agent identity / instructions, if any
    # Replay prior turns so the LLM has conversational context, then the new turn.
    messages = [
        Message(role=turn.metadata.get("role", "user"), content=turn.content)
        for turn in memory.history(scope, limit=history_limit)
    ]
    messages.append(Message(role="user", content=message))
    parts: list[str] = []
    for chunk in provider.stream(messages, system):
        parts.append(chunk)
        yield chunk
    reply = "".join(parts)
    memory.add_turn("user", message, scope)
    memory.add_turn("assistant", reply, scope)
    capture(memory, message, reply, scope)
