# Relio Backend Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend layer of the Relio framework — HTTP memory endpoints plus a streaming chat agent loop — that embeds the Relio Memory engine in-process.

**Architecture:** A thin FastAPI app over `relio.Memory`. An `LLMProvider` interface (real `ClaudeProvider` + offline `FakeProvider`) keeps the whole backend testable with no API key. The `run_chat` agent loop does recall → token-light prompt → streamed LLM reply (SSE) → auto-capture of the turn.

**Tech Stack:** Python 3.11+, FastAPI, Anthropic SDK, pydantic-settings, pytest + httpx (TestClient). Builds on the existing `relio` package (record/Memory/render already implemented).

---

## File Structure

```
relio/src/relio/server/
  __init__.py        # create_app re-export
  config.py          # Settings (pydantic-settings)
  schemas.py         # AddRequest, ChatRequest
  scope.py           # scope helper
  llm/
    __init__.py
    base.py          # Message, LLMProvider ABC
    fake.py          # FakeProvider (offline, deterministic)
    claude.py        # ClaudeProvider (Anthropic SDK)
  agent.py           # run_chat(), default_capture()
  app.py             # create_app(memory, provider, settings)
  routes/
    __init__.py
    memory.py        # /api/memory endpoints
    chat.py          # /api/chat (SSE)
relio/tests/server/
  __init__.py
  conftest.py        # client fixture (FakeProvider + temp DB + DeterministicEmbedder)
  test_health.py
  test_memory_routes.py
  test_chat_routes.py
  test_claude_provider.py
```

---

### Task 0: Server dependencies

**Files:**
- Modify: `relio/pyproject.toml`

- [ ] **Step 1: Add the server optional-dependency group and test deps**

In `relio/pyproject.toml`, under `[project.optional-dependencies]`, add a `server` extra and extend `dev`:

```toml
[project.optional-dependencies]
local = ["fastembed>=0.3"]
mcp = ["mcp>=1.2"]
server = ["fastapi>=0.110", "uvicorn>=0.30", "anthropic>=0.40", "pydantic-settings>=2.2"]
dev = ["pytest>=8", "fastembed>=0.3", "mcp>=1.2", "fastapi>=0.110", "uvicorn>=0.30", "anthropic>=0.40", "pydantic-settings>=2.2", "httpx>=0.27"]
```

- [ ] **Step 2: Install**

Run: `cd relio && pip install -e ".[dev]"`
Expected: installs fastapi, uvicorn, anthropic, pydantic-settings, httpx with no errors.

- [ ] **Step 3: Create the server package dirs**

Create empty files: `src/relio/server/__init__.py`, `src/relio/server/llm/__init__.py`, `src/relio/server/routes/__init__.py`, `tests/server/__init__.py`.

- [ ] **Step 4: Commit**

```bash
git add relio/pyproject.toml relio/src/relio/server relio/tests/server
git commit -m "chore: add server deps and package skeleton"
```

---

### Task 1: Request schemas

**Files:**
- Create: `src/relio/server/schemas.py`
- Test: `tests/server/test_memory_routes.py` (start the file with a schema test)

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_memory_routes.py
from relio.server.schemas import AddRequest, ChatRequest
from relio.record import MemoryType


def test_add_request_defaults():
    req = AddRequest(content="hello")
    assert req.content == "hello"
    assert req.type is MemoryType.SEMANTIC
    assert req.user is None
    assert req.data == {}


def test_chat_request_requires_message():
    req = ChatRequest(message="hi", user="alice")
    assert req.message == "hi"
    assert req.user == "alice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_memory_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.server.schemas'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/server/schemas.py
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from ..record import MemoryType


class AddRequest(BaseModel):
    content: str
    type: MemoryType = MemoryType.SEMANTIC
    tenant: Optional[str] = None
    user: Optional[str] = None
    agent: Optional[str] = None
    session: Optional[str] = None
    data: dict[str, Any] = {}
    ttl: Optional[int] = None
    metadata: dict[str, Any] = {}


class ChatRequest(BaseModel):
    message: str
    tenant: Optional[str] = None
    user: Optional[str] = None
    session: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/server/test_memory_routes.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/schemas.py tests/server/test_memory_routes.py
git commit -m "feat: server request schemas"
```

---

### Task 2: LLM provider interface + FakeProvider

**Files:**
- Create: `src/relio/server/llm/base.py`
- Create: `src/relio/server/llm/fake.py`
- Test: `tests/server/test_chat_routes.py` (start the file)

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_chat_routes.py
from relio.server.llm.base import LLMProvider, Message
from relio.server.llm.fake import FakeProvider


def test_fake_provider_streams_words_and_reflects_memory_count():
    provider = FakeProvider()
    chunks = list(provider.stream([Message(role="user", content="hello there")],
                                  system="What you remember:\n- a fact\n- another"))
    text = "".join(chunks)
    assert "hello there" in text
    assert "[mem:2]" in text          # two "- " memory lines in the system prompt


def test_fake_provider_is_an_llm_provider():
    assert isinstance(FakeProvider(), LLMProvider)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_chat_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.server.llm.base'`

- [ ] **Step 3: Write the implementations**

```python
# src/relio/server/llm/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Literal

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class LLMProvider(ABC):
    @abstractmethod
    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        """Yield reply text chunks for the given conversation + system prompt."""
```

```python
# src/relio/server/llm/fake.py
from __future__ import annotations

from typing import Iterator, Optional

from .base import LLMProvider, Message


class FakeProvider(LLMProvider):
    """Deterministic, offline provider for tests (no API key, no network)."""

    def __init__(self, reply: Optional[str] = None) -> None:
        self._reply = reply

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        memory_count = system.count("- ")
        reply = self._reply or f"echo: {last_user} [mem:{memory_count}]"
        for word in reply.split(" "):
            yield word + " "
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/server/test_chat_routes.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/llm/base.py src/relio/server/llm/fake.py tests/server/test_chat_routes.py
git commit -m "feat: LLMProvider interface + FakeProvider"
```

---

### Task 3: Scope helper

**Files:**
- Create: `src/relio/server/scope.py`
- Test: `tests/server/test_memory_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_memory_routes.py  (append)
from relio.server.scope import make_scope
from relio.record import Scope


def test_make_scope_sets_only_provided_fields():
    s = make_scope(user="alice", tenant="acme")
    assert s == Scope(user="alice", tenant="acme")
    assert s.agent is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_memory_routes.py::test_make_scope_sets_only_provided_fields -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.server.scope'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/server/scope.py
from __future__ import annotations

from typing import Optional

from ..record import Scope


def make_scope(
    tenant: Optional[str] = None,
    user: Optional[str] = None,
    agent: Optional[str] = None,
    session: Optional[str] = None,
) -> Scope:
    """Build a Scope from request fields. The seam the auth hook later replaces."""
    return Scope(tenant=tenant, user=user, agent=agent, session=session)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/server/test_memory_routes.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/scope.py tests/server/test_memory_routes.py
git commit -m "feat: scope resolution helper"
```

---

### Task 4: Settings

**Files:**
- Create: `src/relio/server/config.py`
- Test: `tests/server/test_health.py` (start the file)

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_health.py
from relio.server.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.model == "claude-opus-4-8"
    assert s.db_path == "relio.db"
    assert s.recall_limit == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.server.config'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/server/config.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RELIO_")

    db_path: str = "relio.db"
    model: str = "claude-opus-4-8"
    recall_limit: int = 5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/server/test_health.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/config.py tests/server/test_health.py
git commit -m "feat: server Settings"
```

---

### Task 5: Agent loop

**Files:**
- Create: `src/relio/server/agent.py`
- Test: `tests/server/test_chat_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_chat_routes.py  (append)
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import Scope
from relio.server.agent import run_chat


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))


def test_run_chat_streams_then_captures_the_turn(tmp_path):
    m = _mem(tmp_path)
    provider = FakeProvider()
    scope = Scope(user="alice")
    chunks = list(run_chat(m, provider, "I like hiking", scope, limit=5))
    assert "I like hiking" in "".join(chunks)
    # The turn was auto-captured: a later recall finds the user message.
    found = m.recall("hiking", scope=scope, limit=5)
    assert any("hiking" in r.content for r in found)
    m.close()


def test_run_chat_injects_recalled_memory(tmp_path):
    m = _mem(tmp_path)
    m.add("Alice works at Acme", scope=Scope(user="alice"))
    provider = FakeProvider()
    chunks = list(run_chat(m, provider, "Alice works at Acme",
                           Scope(user="alice"), limit=5))
    text = "".join(chunks)
    assert "[mem:" in text and "[mem:0]" not in text   # at least one memory injected
    m.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_chat_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.server.agent'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/server/agent.py
from __future__ import annotations

from typing import Callable, Iterator

from ..memory import Memory
from ..record import Scope
from ..render import render_lines
from .llm.base import LLMProvider, Message


def default_capture(memory: Memory, message: str, reply: str, scope: Scope) -> None:
    """Heuristic extraction: store the user's message as a memory."""
    memory.add(message, scope=scope)


def run_chat(
    memory: Memory,
    provider: LLMProvider,
    message: str,
    scope: Scope,
    limit: int = 5,
    capture: Callable[[Memory, str, str, Scope], None] = default_capture,
) -> Iterator[str]:
    recalled = memory.recall(message, scope=scope, limit=limit)
    if recalled:
        system = "What you remember:\n" + render_lines(recalled)
    else:
        system = "You have no memories about this yet."
    parts: list[str] = []
    for chunk in provider.stream([Message(role="user", content=message)], system):
        parts.append(chunk)
        yield chunk
    capture(memory, message, "".join(parts), scope)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/server/test_chat_routes.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/agent.py tests/server/test_chat_routes.py
git commit -m "feat: run_chat agent loop with auto-capture"
```

---

### Task 6: Memory routes + app factory

**Files:**
- Create: `src/relio/server/routes/memory.py`
- Create: `src/relio/server/app.py`
- Create: `tests/server/conftest.py`
- Test: `tests/server/test_memory_routes.py` (append), `tests/server/test_health.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/server/conftest.py
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
```

```python
# tests/server/test_health.py  (append)
def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

```python
# tests/server/test_memory_routes.py  (append)
def test_add_get_delete_roundtrip(client):
    add = client.post("/api/memory", json={"content": "Alice likes tea", "user": "alice"})
    assert add.status_code == 201
    rec = add.json()
    assert rec["content"] == "Alice likes tea"
    rid = rec["id"]

    got = client.get(f"/api/memory/{rid}")
    assert got.status_code == 200
    assert got.json()["content"] == "Alice likes tea"

    deleted = client.delete(f"/api/memory/{rid}")
    assert deleted.json() == {"deleted": True}
    assert client.get(f"/api/memory/{rid}").status_code == 404


def test_search_returns_results_and_text(client):
    client.post("/api/memory", json={"content": "apple pie recipe", "user": "alice"})
    resp = client.get("/api/memory/search", params={"q": "apple pie recipe", "user": "alice"})
    assert resp.status_code == 200
    body = resp.json()
    assert any("apple pie" in r["content"] for r in body["results"])
    assert body["text"].startswith("- ")


def test_search_is_scoped_by_user(client):
    client.post("/api/memory", json={"content": "secret note", "user": "alice"})
    resp = client.get("/api/memory/search", params={"q": "secret note", "user": "bob"})
    assert resp.json()["results"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_memory_routes.py tests/server/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.server.app'`

- [ ] **Step 3: Write the implementations**

```python
# src/relio/server/routes/memory.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from ...memory import Memory
from ...record import MemoryRecord, MemoryType
from ...render import render_lines
from ..schemas import AddRequest
from ..scope import make_scope


def build_memory_router(memory: Memory) -> APIRouter:
    router = APIRouter(prefix="/api/memory")

    @router.post("", status_code=201)
    def add(req: AddRequest) -> MemoryRecord:
        scope = make_scope(req.tenant, req.user, req.agent, req.session)
        return memory.add(
            req.content,
            type=req.type,
            scope=scope,
            data=req.data,
            ttl=req.ttl,
            metadata=req.metadata,
        )

    # NOTE: declare /search BEFORE /{record_id} so it isn't captured as an id.
    @router.get("/search")
    def search(
        q: str,
        user: Optional[str] = None,
        tenant: Optional[str] = None,
        type: Optional[MemoryType] = None,
        limit: int = 5,
    ):
        scope = make_scope(tenant=tenant, user=user)
        results = memory.recall(q, scope=scope, type=type, limit=limit)
        return {"results": results, "text": render_lines(results)}

    @router.get("/{record_id}")
    def get(record_id: str) -> MemoryRecord:
        rec = memory.get(record_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="not found")
        return rec

    @router.delete("/{record_id}")
    def forget(record_id: str):
        return {"deleted": memory.forget(record_id)}

    return router
```

```python
# src/relio/server/app.py
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI

from ..memory import Memory
from .config import Settings
from .llm.base import LLMProvider
from .routes.memory import build_memory_router


def create_app(
    memory: Memory,
    provider: LLMProvider,
    settings: Optional[Settings] = None,
) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Relio")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(build_memory_router(memory))
    # Chat router is wired in Task 7.
    app.state.relio_memory = memory
    app.state.relio_provider = provider
    app.state.relio_settings = settings
    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/server/test_memory_routes.py tests/server/test_health.py -v`
Expected: PASS (health + memory route tests green)

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/routes/memory.py src/relio/server/app.py tests/server/conftest.py tests/server/test_memory_routes.py tests/server/test_health.py
git commit -m "feat: memory HTTP routes + app factory"
```

---

### Task 7: Chat route (SSE)

**Files:**
- Create: `src/relio/server/routes/chat.py`
- Modify: `src/relio/server/app.py` (wire the chat router)
- Test: `tests/server/test_chat_routes.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_chat_routes.py  (append)
import json


def _sse_payloads(raw: str):
    out = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def test_chat_streams_deltas_then_done_and_captures(client):
    resp = client.post("/api/chat", json={"message": "I enjoy chess", "user": "alice"})
    assert resp.status_code == 200
    events = _sse_payloads(resp.text)
    deltas = "".join(e["delta"] for e in events if "delta" in e)
    assert "I enjoy chess" in deltas
    assert events[-1] == {"done": True}

    # The turn was captured — searching finds the user message.
    found = client.get("/api/memory/search", params={"q": "chess", "user": "alice"})
    assert any("chess" in r["content"] for r in found.json()["results"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_chat_routes.py::test_chat_streams_deltas_then_done_and_captures -v`
Expected: FAIL — `/api/chat` returns 404 (router not wired yet)

- [ ] **Step 3: Write the implementation**

```python
# src/relio/server/routes/chat.py
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ...memory import Memory
from ..agent import run_chat
from ..config import Settings
from ..llm.base import LLMProvider
from ..schemas import ChatRequest
from ..scope import make_scope


def build_chat_router(memory: Memory, provider: LLMProvider, settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/chat")
    def chat(req: ChatRequest):
        scope = make_scope(tenant=req.tenant, user=req.user, session=req.session)

        def event_stream():
            try:
                for chunk in run_chat(
                    memory, provider, req.message, scope, limit=settings.recall_limit
                ):
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as exc:  # surface LLM errors as an SSE event, end the stream
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return router
```

Then wire it in `src/relio/server/app.py` — add the import and `include_router` call:

```python
# src/relio/server/app.py  — add this import near the other route import
from .routes.chat import build_chat_router
```

```python
# src/relio/server/app.py  — replace the "# Chat router is wired in Task 7." comment with:
    app.include_router(build_chat_router(memory, provider, settings))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/server/test_chat_routes.py -v`
Expected: PASS (all chat tests green)

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/routes/chat.py src/relio/server/app.py tests/server/test_chat_routes.py
git commit -m "feat: streaming /api/chat SSE endpoint"
```

---

### Task 8: ClaudeProvider (real LLM)

**Files:**
- Create: `src/relio/server/llm/claude.py`
- Test: `tests/server/test_claude_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_claude_provider.py
from relio.server.llm.base import Message


class _FakeStream:
    def __init__(self, texts):
        self.text_stream = iter(texts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeMessages:
    def __init__(self, texts):
        self._texts = texts
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self._texts)


class _FakeClient:
    def __init__(self, texts):
        self.messages = _FakeMessages(texts)


def test_claude_provider_yields_text_and_drops_system_role():
    from relio.server.llm.claude import ClaudeProvider

    fake = _FakeClient(["Hel", "lo"])
    provider = ClaudeProvider(model="claude-opus-4-8", client=fake)
    out = list(provider.stream(
        [Message(role="system", content="ignored"), Message(role="user", content="hi")],
        system="remember: x",
    ))
    assert out == ["Hel", "lo"]
    sent = fake.messages.calls[0]
    assert sent["model"] == "claude-opus-4-8"
    assert sent["system"] == "remember: x"
    # system-role messages are passed via `system=`, not in the messages list
    assert sent["messages"] == [{"role": "user", "content": "hi"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_claude_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.server.llm.claude'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/server/llm/claude.py
from __future__ import annotations

from typing import Iterator, Optional

from .base import LLMProvider, Message


class ClaudeProvider(LLMProvider):
    """Streams replies from Claude via the Anthropic SDK."""

    def __init__(self, model: str = "claude-opus-4-8", client: Optional[object] = None) -> None:
        self._model = model
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        wire = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=wire,
        ) as stream:
            for text in stream.text_stream:
                yield text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && python -m pytest tests/server/test_claude_provider.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/llm/claude.py tests/server/test_claude_provider.py
git commit -m "feat: ClaudeProvider (Anthropic SDK streaming)"
```

---

### Task 9: Server package exports + full-suite run

**Files:**
- Modify: `src/relio/server/__init__.py`
- Test: `tests/server/test_health.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_health.py  (append)
def test_server_exports_create_app():
    from relio import server

    assert hasattr(server, "create_app")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && python -m pytest tests/server/test_health.py::test_server_exports_create_app -v`
Expected: FAIL with `AttributeError: module 'relio.server' has no attribute 'create_app'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/server/__init__.py
from .app import create_app
from .config import Settings
from .llm.base import LLMProvider, Message
from .llm.fake import FakeProvider
from .llm.claude import ClaudeProvider

__all__ = ["create_app", "Settings", "LLMProvider", "Message", "FakeProvider", "ClaudeProvider"]
```

- [ ] **Step 4: Run the full suite**

Run: `cd relio && python -m pytest -v -m "not integration"`
Expected: PASS — all engine tests AND all server tests green.

- [ ] **Step 5: Commit**

```bash
git add src/relio/server/__init__.py tests/server/test_health.py
git commit -m "feat: export server public API; full-suite smoke"
```

---

## Self-Review

**Spec coverage (backend design doc):**
- Memory endpoints (add/search/get/delete + health) → Task 6. ✅
- Streaming chat agent loop (recall → prompt → stream → capture) → Tasks 5, 7. ✅
- LLM provider seam (Claude real + Fake for tests) → Tasks 2, 8. ✅
- Scope resolution (tenant/user/agent/session), permissive default → Task 3, used in 6/7. ✅
- Config (db_path, model default `claude-opus-4-8`, recall_limit) → Task 4. ✅
- SSE deltas + `{"done": true}`, error event on LLM failure → Task 7. ✅
- Engine embedded in-process (`Memory` passed to `create_app`) → Task 6. ✅
- Testable with no API key (FakeProvider + DeterministicEmbedder + temp DB) → conftest, Task 6. ✅

**Deferred (not in this plan, by design):** React frontend, real auth/multi-tenant DB-per-tenant, reverse-proxy/Dockerfile DevOps layer, LLM-based memory extraction, rate limiting.

**Type consistency:** `Message`/`LLMProvider` (Task 2) used identically by `run_chat` (5), `ClaudeProvider` (8), and `FakeProvider` (2). `make_scope` (3) returns `relio.Scope`, consumed by routes (6, 7) and `run_chat` (5). `create_app(memory, provider, settings)` signature (6) matches the conftest fixture and the Task 7 chat wiring. `AddRequest`/`ChatRequest` (1) consumed by routes (6, 7). The `/search`-before-`/{record_id}` ordering is called out explicitly to avoid a route-shadowing bug.

**Placeholder scan:** No TBD/TODO; every code step contains complete, runnable code.
