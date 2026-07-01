from __future__ import annotations

from typing import Any, Optional

from .base import CapabilityError, LLMProvider
from .fake import FakeProvider

# The intentional, documented way to choose an AI provider — or to run with no
# LLM at all. `"none"` returns None (the memory/data backend runs without chat),
# so disabling the LLM is an explicit config choice, not a deleted argument.
_DISABLED = {"", "none", "off", "false", "disabled"}


def make_provider(
    name: Optional[str],
    *,
    model: Optional[str] = None,
    requires: Optional[list[str]] = None,
    **kwargs: Any,
) -> Optional[LLMProvider]:
    """Build an LLM provider by name.

    Names: "claude" (Anthropic), "openai" (OpenAI *and* any OpenAI-compatible
    endpoint via base_url — Groq/Together/Ollama/…), "gemini" (Google), "fake"
    (offline/tests), or "none" → None (LLM disabled).

    Pass `requires=["transcribe", ...]` to fail fast (`CapabilityError`) unless the
    built provider supports every listed capability — so a config mismatch is
    caught at construction, not deep in a request. Requiring capabilities with a
    disabled provider ("none") is itself an error. See ADR-003.
    """
    key = (name or "none").strip().lower()
    provider: Optional[LLMProvider]
    if key in _DISABLED:
        provider = None
    elif key == "fake":
        provider = FakeProvider(**kwargs)
    elif key == "claude":
        from .claude import ClaudeProvider

        provider = ClaudeProvider(model=model or "claude-opus-4-8", **kwargs)
    elif key == "openai":
        from .openai import OpenAIProvider

        provider = OpenAIProvider(model=model or "gpt-4o", **kwargs)
    elif key == "gemini":
        from .gemini import GeminiProvider

        provider = GeminiProvider(model=model or "gemini-1.5-pro", **kwargs)
    else:
        raise ValueError(
            f"unknown provider: {name!r} (use claude, openai, gemini, fake, or none)"
        )

    if requires:
        if provider is None:
            raise CapabilityError(
                f"provider {key!r} is disabled but capabilities {list(requires)} were required"
            )
        missing = [c for c in requires if not provider.supports(c)]
        if missing:
            raise CapabilityError(
                f"the {type(provider).__name__} provider does not support "
                f"required capabilities: {missing}"
            )
    return provider
