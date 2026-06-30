from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Literal, Optional

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class LLMProvider(ABC):
    @abstractmethod
    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        """Yield reply text chunks for the given conversation + system prompt."""

    def extract(
        self,
        prompt: str,
        schema: Optional[dict] = None,
        *,
        image_bytes: Optional[bytes] = None,
        media_type: Optional[str] = None,
    ) -> dict:
        """Return structured data (optionally from an image/PDF) matching `schema`.

        Optional capability — providers that can't do vision / structured output
        leave this unimplemented.
        """
        raise NotImplementedError("this provider does not support extraction")
