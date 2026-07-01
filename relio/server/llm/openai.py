from __future__ import annotations

import base64
import json
from typing import Iterator, Optional

from .base import Message, _LazyClientProvider, tool_input_schema


class OpenAIProvider(_LazyClientProvider):
    """OpenAI (and any OpenAI-compatible endpoint via `base_url`: Groq, Together,
    Fireworks, Ollama at http://localhost:11434/v1, local vLLM, ...)."""

    def __init__(
        self,
        model: str = "gpt-4o",
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Optional[object] = None,
    ) -> None:
        super().__init__(model, api_key=api_key, client=client)
        self._base_url = base_url

    def _build_client(self):
        import openai  # lazy: needs the `openai` extra

        return openai.OpenAI(base_url=self._base_url, api_key=self._api_key)

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        wire = [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        stream = self._get_client().chat.completions.create(
            model=self._model, messages=wire, stream=True
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def transcribe(self, audio, *, media_type=None, language=None) -> str:
        import io

        ext = (media_type or "audio/webm").rsplit("/", 1)[-1]
        f = io.BytesIO(bytes(audio))
        f.name = f"audio.{ext}"  # the SDK infers the format from the filename
        kwargs = {"model": "whisper-1", "file": f}
        if language:
            kwargs["language"] = language
        resp = self._get_client().audio.transcriptions.create(**kwargs)
        return resp.text

    def extract(self, prompt, schema=None, *, image_bytes=None, media_type=None) -> dict:
        content: list[dict] = []
        if image_bytes is not None:
            b64 = base64.b64encode(image_bytes).decode()
            url = f"data:{media_type or 'image/png'};base64,{b64}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        content.append({"type": "text", "text": prompt or "Extract the requested structured data."})
        system = "Return ONLY valid JSON matching the requested schema."
        if schema:
            system += " JSON schema: " + json.dumps(schema)
        resp = self._get_client().chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        )
        return json.loads(resp.choices[0].message.content)

    def complete_with_tools(self, messages, system, tools) -> dict:
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": tool_input_schema(t.get("parameters", {})),
                },
            }
            for t in tools
        ]
        wire = [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ]
        resp = self._get_client().chat.completions.create(
            model=self._model, messages=wire, tools=oai_tools
        )
        msg = resp.choices[0].message
        if getattr(msg, "tool_calls", None):
            return {
                "tool_calls": [
                    {"name": tc.function.name, "arguments": json.loads(tc.function.arguments or "{}")}
                    for tc in msg.tool_calls
                ]
            }
        return {"text": msg.content or ""}
