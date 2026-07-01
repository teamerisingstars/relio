from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Literal, Optional

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class CapabilityError(RuntimeError):
    """Raised when a provider is asked for an optional capability it lacks —
    early and legible, instead of a deep `NotImplementedError` at the API call."""


# The optional capabilities a provider *may* implement (beyond the required
# `stream`). A provider "has" one by overriding its base method — see
# `capabilities()`, which derives the set from the overrides so there is a single
# source of truth (no separately-maintained list to drift). See ADR-003.
_OPTIONAL_CAPABILITIES = ("extract", "complete_with_tools", "transcribe")


class LLMProvider(ABC):
    @abstractmethod
    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        """Yield reply text chunks for the given conversation + system prompt."""

    def capabilities(self) -> set[str]:
        """The optional capabilities this provider supports, derived from which
        base methods the subclass actually overrides."""
        return {
            name
            for name in _OPTIONAL_CAPABILITIES
            if getattr(type(self), name, None) is not getattr(LLMProvider, name, None)
        }

    def supports(self, capability: str) -> bool:
        """Ask before calling: `provider.supports("transcribe")`."""
        return capability in self.capabilities()

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

    def complete_with_tools(
        self,
        messages: list[Message],
        system: str,
        tools: list[dict],
    ) -> dict:
        """One agent step. Given the conversation + available `tools`
        (`[{"name","description","parameters"}]`), return either
        `{"tool_calls": [{"name", "arguments"}]}` to call tools, or
        `{"text": "..."}` for the final answer. Optional capability."""
        raise NotImplementedError("this provider does not support tool-calling")

    def transcribe(
        self, audio: bytes, *, media_type: Optional[str] = None, language: Optional[str] = None
    ) -> str:
        """Transcribe speech audio to text (server-side STT). Optional capability —
        pairs with the browser Web Speech API + a typing fallback on the client."""
        raise NotImplementedError("this provider does not support transcription")
