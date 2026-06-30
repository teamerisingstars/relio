from __future__ import annotations

from typing import Iterator, Optional

from .base import LLMProvider, Message


class ClaudeProvider(LLMProvider):
    """Streams replies from Claude via the Anthropic SDK."""

    def __init__(self, model: str = "claude-opus-4-8", client: Optional[object] = None) -> None:
        self._model = model
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        wire = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=wire,
        ) as stream:
            for text in stream.text_stream:
                yield text
