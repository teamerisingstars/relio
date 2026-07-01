# LLM Providers & Capabilities

Relio talks to models through the `LLMProvider` seam. Pick one with
`make_provider(name)` (or construct a provider class directly), or pass
`"none"` to run with **no LLM** — memory, retrieval, graph, and structured query
all work without one.

```python
from relio.server.llm import make_provider

provider = make_provider("openai", model="gpt-4o")   # or "claude" / "gemini" / "fake" / "none"
ai = RelioAI(memory=memory, provider=provider)
```

Names: `claude` (Anthropic), `openai` (OpenAI **and** any OpenAI-compatible
endpoint via `base_url` — Groq / Together / Ollama / local vLLM), `gemini`
(Google), `fake` (deterministic, offline — for tests), `none` → `None`.

## Capability matrix

Only `stream` (chat) is required. The rest are **optional capabilities** — a
provider has one by implementing its method (see [ADR-003](adr/ADR-003-provider-capability-negotiation.md)).

| Capability | Method | Claude | OpenAI | Gemini | Fake | none |
|------------|--------|:------:|:------:|:------:|:----:|:----:|
| Chat (required) | `stream` | ✓ | ✓ | ✓ | ✓ | — |
| Structured / vision extract | `extract` | ✓ | ✓ | ✓ | ✓ | — |
| Agent tool-calling | `complete_with_tools` | ✓ | ✓ | ✓ | ✓ | — |
| Speech-to-text | `transcribe` | — | ✓ (Whisper) | — | ✓ | — |

## Ask before you call

Capabilities are introspectable, so an app or UI can pre-flight instead of
guessing:

```python
if ai.supports("transcribe"):
    show_microphone_button()

# On the provider directly:
provider.capabilities()          # -> {"extract", "complete_with_tools", ...}
provider.supports("transcribe")  # -> True / False
```

Calling an unsupported capability raises a clear `CapabilityError` **at the seam**
(early and legible), not a deep `NotImplementedError` from inside an API call:

```python
from relio.server.llm import CapabilityError

try:
    ai.transcribe(audio)
except CapabilityError as e:
    # e.g. "the GeminiProvider provider does not support 'transcribe' ..."
    ...
```

The capability set is **auto-derived** from which methods a provider actually
overrides — there is no separate list to keep in sync.

To catch a config mismatch at **construction** instead of at request time, tell
`make_provider` what you need:

```python
# Raises CapabilityError now if this provider can't transcribe (or is "none"):
provider = make_provider("openai", requires=["transcribe", "complete_with_tools"])
```

## Running without a key / offline

- `make_provider("none")` (or `RELIO_PROVIDER=none`) → no LLM; the data plane
  still runs. Disabling the LLM is an explicit choice, not a missing argument.
- `FakeProvider` implements every optional capability deterministically, so the
  whole system is testable offline with no network and no keys.
- Real providers construct their client **lazily** — you can build a
  `ClaudeProvider()` / `OpenAIProvider()` without an API key present at boot; the
  key is only needed on first call.
