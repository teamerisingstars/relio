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

    def complete_with_tools(self, messages, system, tools) -> dict:
        # Deterministic: call the first available tool once, then finish. Enough
        # to exercise the agent loop offline.
        already_ran = any("[tool " in m.content for m in messages)
        if tools and not already_ran:
            return {"tool_calls": [{"name": tools[0]["name"], "arguments": {}}]}
        return {"text": "done"}

    def transcribe(self, audio, *, media_type=None, language=None) -> str:
        return f"[transcript of {len(audio)} bytes]"

    def extract(self, prompt, schema=None, *, image_bytes=None, media_type=None) -> dict:
        # Deterministic, offline: echo where the input came from and the schema's
        # field names, so extraction wiring is testable without a real model.
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        return {
            "source": "image" if image_bytes else "text",
            "media_type": media_type,
            "fields": list(props.keys()),
            "prompt": prompt,
        }
