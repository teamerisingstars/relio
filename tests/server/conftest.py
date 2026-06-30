import pytest
from fastapi.testclient import TestClient

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.server.app import create_app
from relio.server.llm.fake import FakeProvider


@pytest.fixture
def client(tmp_path):
    memory = Memory(path=str(tmp_path / "api.db"), embedder=DeterministicEmbedder(dim=16))
    app = create_app(memory, FakeProvider())
    with TestClient(app) as c:
        yield c
    memory.close()
