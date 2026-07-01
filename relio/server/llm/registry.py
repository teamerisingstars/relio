from __future__ import annotations

from typing import Any, Optional

from .base import LLMProvider
from .fake import FakeProvider

# The intentional, documented way to choose an AI provider — or to run with no
# LLM at all. `"none"` returns None (the memory/data backend runs without chat),
# so disabling the LLM is an explicit config choice, not a deleted argument.
_DISABLED = {"", "none", "off", "false", "disabled"}


def make_provider(
    name: Optional[str],
    *,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[LLMProvider]:
    """Build an LLM provider by name.

    Names: "claude" (Anthropic), "openai" (OpenAI *and* any OpenAI-compatible
    endpoint via base_url — Groq/Together/Ollama/…), "gemini" (Google), "fake"
    (offline/tests), or "none" → None (LLM disabled).
    """
    key = (name or "none").strip().lower()
    if key in _DISABLED:
        return None
    if key == "fake":
        return FakeProvider(**kwargs)
    if key == "claude":
        from .claude import ClaudeProvider

        return ClaudeProvider(model=model or "claude-opus-4-8", **kwargs)
    if key == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(model=model or "gpt-4o", **kwargs)
    if key == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(model=model or "gemini-1.5-pro", **kwargs)
    raise ValueError(
        f"unknown provider: {name!r} (use claude, openai, gemini, fake, or none)"
    )
