from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Literal, Optional

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


# Map the Python type names captured in ToolSpec.parameters to JSON-schema types,
# so the LLM receives correctly-typed tool args (ints as integers, etc.) instead
# of everything flattened to "string".
_JSON_SCHEMA_TYPES = {
    "int": "integer",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "str": "string",
    "list": "array",
    "dict": "object",
}


def tool_input_schema(parameters: dict) -> dict:
    """Build a JSON-schema `object` from a tool's `{param: type_name}` map."""
    return {
        "type": "object",
        "properties": {
            name: {"type": _JSON_SCHEMA_TYPES.get(str(tname).lower(), "string")}
            for name, tname in parameters.items()
        },
    }


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


class _LazyClientProvider(LLMProvider):
    """Base for SDK-backed providers: stores `model`/`api_key` and builds the
    vendor client **lazily on first use** (so importing/constructing needs no key
    or SDK at boot). Subclasses implement `_build_client()`."""

    def __init__(
        self,
        model: str,
        *,
        api_key: Optional[str] = None,
        client: Optional[object] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._client = client  # created on first use if None

    def _build_client(self):
        raise NotImplementedError

    def _get_client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client
