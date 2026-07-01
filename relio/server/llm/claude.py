from __future__ import annotations

from typing import Iterator, Optional

from .base import LLMProvider, Message


class ClaudeProvider(LLMProvider):
    """Streams replies from Claude via the Anthropic SDK."""

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        *,
        api_key: Optional[str] = None,
        client: Optional[object] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._client = client  # created lazily on first use — no API key needed at boot

    def _get_client(self):
        if self._client is None:
            import anthropic

            # api_key=None → the SDK falls back to ANTHROPIC_API_KEY (env).
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        wire = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        with self._get_client().messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=wire,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def extract(self, prompt, schema=None, *, image_bytes=None, media_type=None) -> dict:
        import base64
        import json

        content: list[dict] = []
        if image_bytes is not None:
            data = base64.b64encode(image_bytes).decode()
            mt = media_type or "image/png"
            block_type = "document" if mt == "application/pdf" else "image"
            content.append(
                {"type": block_type, "source": {"type": "base64", "media_type": mt, "data": data}}
            )
        content.append({"type": "text", "text": prompt or "Extract the requested structured data."})
        system = "Return ONLY valid JSON matching the requested schema, no prose."
        if schema:
            system += " JSON schema: " + json.dumps(schema)
        msg = self._get_client().messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        return json.loads(text)

    def complete_with_tools(self, messages, system, tools) -> dict:
        anth_tools = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": {
                    "type": "object",
                    "properties": {p: {"type": "string"} for p in t.get("parameters", {})},
                },
            }
            for t in tools
        ]
        wire = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        msg = self._get_client().messages.create(
            model=self._model, max_tokens=2048, system=system, tools=anth_tools, messages=wire
        )
        calls = [
            {"name": b.name, "arguments": b.input}
            for b in msg.content
            if getattr(b, "type", None) == "tool_use"
        ]
        if calls:
            return {"tool_calls": calls}
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        return {"text": text}
