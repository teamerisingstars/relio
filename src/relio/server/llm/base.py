from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Literal

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class LLMProvider(ABC):
    @abstractmethod
    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        """Yield reply text chunks for the given conversation + system prompt."""
