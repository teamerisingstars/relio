from __future__ import annotations

from typing import Iterator, Optional

from .base import LLMProvider, Message


class GeminiProvider(LLMProvider):
    """Google Gemini via the google-genai SDK."""

    def __init__(
        self,
        model: str = "gemini-1.5-pro",
        *,
        api_key: Optional[str] = None,
        client: Optional[object] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._client = client  # created lazily on first use — no key/SDK needed at boot

    def _get_client(self):
        if self._client is None:
            from google import genai  # lazy: needs the `gemini` extra

            self._client = genai.Client(api_key=self._api_key) if self._api_key else genai.Client()
        return self._client

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        contents = "\n".join(
            f"{m.role}: {m.content}" for m in messages if m.role != "system"
        )
        stream = self._get_client().models.generate_content_stream(
            model=self._model,
            contents=contents,
            config={"system_instruction": system} if system else None,
        )
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text

    def complete_with_tools(self, messages, system, tools) -> dict:
        from google.genai import types  # lazy

        decls = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters={
                    "type": "object",
                    "properties": {p: {"type": "string"} for p in t.get("parameters", {})},
                },
            )
            for t in tools
        ]
        contents = "\n".join(f"{m.role}: {m.content}" for m in messages if m.role != "system")
        resp = self._get_client().models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system or None,
                tools=[types.Tool(function_declarations=decls)] if decls else None,
            ),
        )
        calls = getattr(resp, "function_calls", None)
        if calls:
            return {"tool_calls": [{"name": c.name, "arguments": dict(c.args or {})} for c in calls]}
        return {"text": getattr(resp, "text", "") or ""}
