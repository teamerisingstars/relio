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


def test_sdk_generates_streaming_and_multipart_methods():
    openapi = {
        "paths": {
            "/api/events": {"get": {
                "operationId": "events",
                "responses": {"200": {"content": {"text/event-stream": {}}}},
            }},
            "/api/upload": {"post": {
                "operationId": "ingest_creative_file",
                "requestBody": {"content": {"multipart/form-data": {"schema": {"properties": {"file": {}}}}}},
                "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
            }},
        }
    }
    ts = sdkgen.generate_ts_client(openapi)
    py = sdkgen.generate_py_client(openapi)

    # streaming → generators, not one-shot requests
    assert "async *events(): AsyncGenerator<string>" in ts and "this._stream(" in ts
    assert "def events(self) -> Iterator[str]:" in py and "self._stream(" in py

    # multipart → a real file-upload method (was arg-less before)
    assert "ingestCreativeFile(form: FormData)" in ts and "this._requestForm(" in ts
    assert "def ingest_creative_file(self, files:" in py and "self._request_multipart(" in py

    # the generated Python must at least compile
    compile(py, "client.py", "exec")


def test_cli_sdk_introspects_the_users_app_including_custom_endpoints(tmp_path, monkeypatch):
    # The whole point: `relio sdk` must read the USER's app.py, so custom
    # endpoints show up in the generated client (bug: it used a throwaway app).
    from relio.cli.main import main

    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "@app.get('/api/widgets', operation_id='list_widgets')\n"
        "def list_widgets() -> list[str]:\n"
        "    return []\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    out = tmp_path / "sdk"
    assert main(["sdk", "--out", str(out)]) == 0
    for name in ("types.ts", "client.ts", "types.py", "client.py"):
        assert (out / name).read_text().strip()
    # the custom endpoint made it into both clients
    assert "listWidgets" in (out / "client.ts").read_text()
    assert "def list_widgets" in (out / "client.py").read_text()


def test_cli_sdk_fails_clearly_when_app_cannot_be_loaded(tmp_path, monkeypatch, capsys):
    from relio.cli.main import main

    monkeypatch.chdir(tmp_path)  # no app.py here
    assert main(["sdk", "--out", str(tmp_path / "sdk")]) == 1
    assert "couldn't load your app" in capsys.readouterr().err
