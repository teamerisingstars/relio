# tests/test_extraction.py
from typing import Iterator

import pytest

from relio import RelioAI
from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.server.llm.base import LLMProvider, Message
from relio.server.llm.fake import FakeProvider

BOM_SCHEMA = {"properties": {"part_no": {}, "qty": {}, "material": {}}}


def _ai(tmp_path, provider=None):
    m = Memory(path=str(tmp_path / "ex.db"), embedder=DeterministicEmbedder(dim=16))
    return RelioAI(memory=m, provider=provider)


def test_extract_text_returns_schema_fields(tmp_path):
    ai = _ai(tmp_path, provider=FakeProvider())
    out = ai.extract("part AB-1, qty 3, steel", schema=BOM_SCHEMA)
    assert out["source"] == "text"
    assert out["fields"] == ["part_no", "qty", "material"]
    ai.close()


def test_extract_file_marks_image_source(tmp_path):
    ai = _ai(tmp_path, provider=FakeProvider())
    out = ai.extract_file(b"%PDF-1.7 fake drawing", schema=BOM_SCHEMA)
    assert out["source"] == "image"
    assert out["media_type"] == "application/pdf"
    ai.close()


def test_extract_requires_a_provider(tmp_path):
    ai = _ai(tmp_path)  # no provider
    with pytest.raises(RuntimeError):
        ai.extract("anything", schema=BOM_SCHEMA)
    ai.close()


class StreamOnlyProvider(LLMProvider):
    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        yield "x"


def test_provider_without_extract_raises(tmp_path):
    ai = _ai(tmp_path, provider=StreamOnlyProvider())
    with pytest.raises(NotImplementedError):
        ai.extract("text", schema=BOM_SCHEMA)
    ai.close()
