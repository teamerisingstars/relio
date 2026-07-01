# tests/test_providers.py
import pytest

from relio.server.llm.base import LLMProvider, Message
from relio.server.llm.fake import FakeProvider
from relio.server.llm.gemini import GeminiProvider
from relio.server.llm.openai import OpenAIProvider
from relio.server.llm.registry import make_provider


# --- registry: the proper way to select / disable the LLM -------------------

def test_make_provider_fake():
    assert isinstance(make_provider("fake"), FakeProvider)


@pytest.mark.parametrize("name", ["none", "off", "", None, "None"])
def test_make_provider_none_disables_llm(name):
    assert make_provider(name) is None      # explicit, documented disable


def test_make_provider_unknown_raises():
    with pytest.raises(ValueError):
        make_provider("bogus")


def test_provider_classes_are_llm_providers():
    assert issubclass(OpenAIProvider, LLMProvider)
    assert issubclass(GeminiProvider, LLMProvider)


def test_providers_construct_lazily_without_key_or_sdk():
    # Constructing a provider must not require an API key or the SDK at boot —
    # the client is created on first use. (openai/google-genai aren't installed.)
    from relio.server.llm.claude import ClaudeProvider

    ClaudeProvider()          # no ANTHROPIC_API_KEY needed to construct
    OpenAIProvider()          # no openai SDK needed to construct
    GeminiProvider()          # no google-genai SDK needed to construct


# --- OpenAI provider stream (injected client, no SDK/API needed) ------------

class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _Chunk:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _FakeOpenAIClient:
    class _Completions:
        def create(self, model, messages, stream=False, **kw):
            return [_Chunk("hi "), _Chunk("there"), _Chunk(None)]  # None is skipped

    class _Chat:
        def __init__(self):
            self.completions = _FakeOpenAIClient._Completions()

    def __init__(self):
        self.chat = _FakeOpenAIClient._Chat()


def test_openai_provider_streams_deltas():
    p = OpenAIProvider(client=_FakeOpenAIClient())
    out = "".join(p.stream([Message(role="user", content="hey")], "sys"))
    assert out == "hi there"


# --- Gemini provider stream (injected client) -------------------------------

class _GChunk:
    def __init__(self, text):
        self.text = text


class _FakeGenaiClient:
    class _Models:
        def generate_content_stream(self, model, contents, config=None):
            return [_GChunk("a "), _GChunk("b")]

    def __init__(self):
        self.models = _FakeGenaiClient._Models()


def test_gemini_provider_streams_text():
    p = GeminiProvider(client=_FakeGenaiClient())
    out = "".join(p.stream([Message(role="user", content="hey")], "sys"))
    assert out == "a b"
