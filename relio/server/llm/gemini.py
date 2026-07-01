from __future__ import annotations

from typing import Iterator, Optional

from .base import Message, _LazyClientProvider, tool_input_schema


class GeminiProvider(_LazyClientProvider):
    """Google Gemini via the google-genai SDK."""

    def __init__(
        self,
        model: str = "gemini-1.5-pro",
        *,
        api_key: Optional[str] = None,
        client: Optional[object] = None,
    ) -> None:
        super().__init__(model, api_key=api_key, client=client)

    def _build_client(self):
        from google import genai  # lazy: needs the `gemini` extra

        return genai.Client(api_key=self._api_key) if self._api_key else genai.Client()

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
                parameters=tool_input_schema(t.get("parameters", {})),
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
