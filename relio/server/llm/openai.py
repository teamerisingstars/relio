from __future__ import annotations

import base64
import json
from typing import Iterator, Optional

from .base import LLMProvider, Message


class OpenAIProvider(LLMProvider):
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
        self._model = model
        self._base_url = base_url
        self._api_key = api_key
        self._client = client  # created lazily on first use — no key/SDK needed at boot

    def _get_client(self):
        if self._client is None:
            import openai  # lazy: needs the `openai` extra

            self._client = openai.OpenAI(base_url=self._base_url, api_key=self._api_key)
        return self._client

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
