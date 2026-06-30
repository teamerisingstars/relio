# tests/test_sdkgen.py
import os

import pytest

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.server.app import create_app
from relio.server.llm.fake import FakeProvider
from relio import sdkgen


@pytest.fixture
def openapi(tmp_path):
    m = Memory(path=str(tmp_path / "s.db"), embedder=DeterministicEmbedder(dim=8))
    app = create_app(m, FakeProvider())
    schema = app.openapi()
    m.close()
    return schema


def test_ts_types_emit_interfaces_and_enum(openapi):
    ts = sdkgen.generate_ts_types(openapi)
    assert "export type MemoryType =" in ts
    assert '"semantic"' in ts
    assert "export interface MemoryRecord {" in ts
    assert "type?: MemoryType;" in ts
    assert "scope?: Scope;" in ts
    assert "ttl?: number | null;" in ts


def test_ts_client_has_typed_methods_and_chat(openapi):
    ts = sdkgen.generate_ts_client(openapi)
    assert "export class RelioClient" in ts
    assert "async addMemory(body: AddRequest): Promise<MemoryRecord>" in ts
    assert "async getMemory(recordId: string): Promise<MemoryRecord>" in ts
    assert "async searchMemory(query: {" in ts
    assert "async *chat(body: ChatRequest): AsyncGenerator<string>" in ts


def test_py_types_compile_and_define_models(openapi):
    py = sdkgen.generate_py_types(openapi)
    assert "MemoryType = Literal[" in py
    assert "class MemoryRecord(TypedDict, total=False):" in py
    compile(py, "types.py", "exec")  # must be valid Python


def test_py_client_compiles_and_has_methods(openapi):
    py = sdkgen.generate_py_client(openapi)
    assert "class RelioClient:" in py
    assert "def add_memory(self, body: " in py
    assert "def get_memory(self, record_id: str)" in py
    assert "def chat(self, body:" in py
    compile(py, "client.py", "exec")  # must be valid Python


def test_generate_all_returns_four_files(openapi):
    files = sdkgen.generate_all(openapi)
    assert set(files) == {"types.ts", "client.ts", "types.py", "client.py"}
    assert all(content.strip() for content in files.values())


def test_cli_sdk_writes_files(tmp_path):
    from relio.cli.main import main

    out = tmp_path / "sdk"
    rc = main(["sdk", "--out", str(out)])
    assert rc == 0
    for name in ("types.ts", "client.ts", "types.py", "client.py"):
        assert (out / name).read_text().strip()
