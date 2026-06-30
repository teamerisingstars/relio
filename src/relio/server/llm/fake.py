from __future__ import annotations

from typing import Iterator, Optional

from .base import LLMProvider, Message


class FakeProvider(LLMProvider):
    """Deterministic, offline provider for tests (no API key, no network)."""

    def __init__(self, reply: Optional[str] = None) -> None:
        self._reply = reply

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        memory_count = system.count("- ")
        reply = self._reply or f"echo: {last_user} [mem:{memory_count}]"
        for word in reply.split(" "):
            yield word + " "
