# Relio Memory Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Relio Memory — an embeddable Python library that gives an AI app one unified memory store (semantic + structured + session/KV + graph) backed by a single SQLite file, plus an MCP server.

**Architecture:** A `Memory` facade sits over four small units: a Pydantic **record model** (the format), a pluggable **StorageBackend** (default: SQLite + `sqlite-vec`), a pluggable **Embedder** (deterministic for tests, `fastembed` local model for real, wrapped by a dedup cache), and a **RecallEngine** that does vector search + scope/type/expiry filtering and renders token-light natural-language lines. Import/export adapters and an MCP server wrap the facade.

**Tech Stack:** Python 3.11+, Pydantic v2, `sqlite-vec`, `fastembed` (optional), `mcp` (optional), pytest.

---

## File Structure

```
relio/
  pyproject.toml
  src/relio/
    __init__.py            # public API exports
    record.py              # MemoryType, Scope, Relation, MemoryRecord
    backends/
      __init__.py
      base.py              # StorageBackend ABC
      sqlite.py            # SQLiteBackend (sqlite-vec)
    embedding/
      __init__.py
      base.py              # Embedder ABC, DeterministicEmbedder
      cache.py             # CachingEmbedder (dedup)
      local.py             # LocalEmbedder (fastembed)
    render.py              # render_lines()
    recall.py              # RecallEngine
    memory.py              # Memory (public facade)
    interchange.py         # import_records / export_records
    mcp_server.py          # build_mcp_server()
  tests/
    test_record.py
    test_sqlite_backend.py
    test_embedding.py
    test_render.py
    test_recall.py
    test_memory.py
    test_interchange.py
    test_mcp_server.py
```

Each file has one responsibility. `memory.py` is the only unit that wires the others together; everything below it depends only on `record.py` and the two ABCs.

---

### Task 0: Project scaffolding

**Files:**
- Create: `relio/pyproject.toml`
- Create: `relio/src/relio/__init__.py` (empty for now)
- Create: `relio/src/relio/backends/__init__.py` (empty)
- Create: `relio/src/relio/embedding/__init__.py` (empty)
- Create: `relio/tests/__init__.py` (empty)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "relio"
version = "0.1.0"
description = "Relio Memory — unified AI memory engine"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
    "sqlite-vec>=0.1.6",
]

[project.optional-dependencies]
local = ["fastembed>=0.3"]
mcp = ["mcp>=1.2"]
dev = ["pytest>=8", "fastembed>=0.3", "mcp>=1.2"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/relio"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
markers = ["integration: tests that download models or need optional deps"]
```

- [ ] **Step 2: Create the empty package files**

Create `src/relio/__init__.py`, `src/relio/backends/__init__.py`, `src/relio/embedding/__init__.py`, and `tests/__init__.py`, each empty.

- [ ] **Step 3: Install in editable mode**

Run: `cd relio && pip install -e ".[dev]"`
Expected: installs pydantic, sqlite-vec, fastembed, mcp, pytest with no errors.

- [ ] **Step 4: Verify pytest collects nothing yet**

Run: `cd relio && pytest -q`
Expected: "no tests ran" (exit code 5) — confirms config is valid.

- [ ] **Step 5: Commit**

```bash
git add relio/pyproject.toml relio/src/relio relio/tests
git commit -m "chore: scaffold relio package"
```

---

### Task 1: Record model

**Files:**
- Create: `src/relio/record.py`
- Test: `tests/test_record.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_record.py
from relio.record import MemoryRecord, MemoryType, Scope, Relation


def test_defaults_make_a_semantic_record_with_generated_id():
    r = MemoryRecord(content="Alice prefers Python")
    assert r.id.startswith("mem_")
    assert r.type is MemoryType.SEMANTIC
    assert r.content == "Alice prefers Python"
    assert r.data == {}
    assert r.relations == []
    assert r.scope == Scope()
    assert r.ttl is None
    assert r.schema_version == "1.0"


def test_roundtrips_through_dict():
    r = MemoryRecord(
        type=MemoryType.FACT,
        content="works at Acme",
        data={"employer": "Acme"},
        relations=[Relation(predicate="works_at", target_id="mem_org")],
        scope=Scope(user="alice", tenant="acme"),
        ttl=3600,
    )
    again = MemoryRecord.model_validate(r.model_dump())
    assert again == r
    assert again.relations[0].predicate == "works_at"
    assert again.scope.user == "alice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_record.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.record'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/record.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    SEMANTIC = "semantic"
    FACT = "fact"
    SESSION = "session"
    NODE = "node"
    EDGE = "edge"


class Scope(BaseModel):
    tenant: Optional[str] = None
    user: Optional[str] = None
    agent: Optional[str] = None
    session: Optional[str] = None


class Relation(BaseModel):
    predicate: str
    target_id: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return "mem_" + uuid.uuid4().hex


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    type: MemoryType = MemoryType.SEMANTIC
    content: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    relations: list[Relation] = Field(default_factory=list)
    scope: Scope = Field(default_factory=Scope)
    metadata: dict[str, Any] = Field(default_factory=dict)
    ttl: Optional[int] = None  # seconds from created_at; None = permanent
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    schema_version: str = "1.0"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_record.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/record.py tests/test_record.py
git commit -m "feat: add MemoryRecord model (the format)"
```

---

### Task 2: StorageBackend ABC

**Files:**
- Create: `src/relio/backends/base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sqlite_backend.py  (start the file — backend ABC contract)
import pytest
from relio.backends.base import StorageBackend


def test_storage_backend_is_abstract():
    with pytest.raises(TypeError):
        StorageBackend()  # cannot instantiate an abstract class
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_sqlite_backend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.backends.base'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/backends/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from ..record import MemoryRecord


class StorageBackend(ABC):
    """Persistence contract. Callers (Memory, RecallEngine) depend only on this."""

    @abstractmethod
    def add(self, record: MemoryRecord, embedding: list[float] | None) -> None:
        """Insert or replace a record; store its embedding if provided."""

    @abstractmethod
    def get(self, record_id: str) -> MemoryRecord | None:
        ...

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        """Return True if a row was removed."""

    @abstractmethod
    def search(self, embedding: list[float], k: int) -> list[tuple[MemoryRecord, float]]:
        """Return up to k nearest records as (record, distance), ascending distance."""

    @abstractmethod
    def all(self) -> list[MemoryRecord]:
        ...

    @abstractmethod
    def close(self) -> None:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_sqlite_backend.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/backends/base.py tests/test_sqlite_backend.py
git commit -m "feat: add StorageBackend ABC"
```

---

### Task 3: SQLite backend — schema, add/get/delete/all

**Files:**
- Create: `src/relio/backends/sqlite.py`
- Test: `tests/test_sqlite_backend.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sqlite_backend.py  (append)
from relio.backends.sqlite import SQLiteBackend
from relio.record import MemoryRecord, MemoryType, Scope


def test_add_get_roundtrip(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=4)
    r = MemoryRecord(content="hello", scope=Scope(user="alice"))
    be.add(r, [0.1, 0.2, 0.3, 0.4])
    got = be.get(r.id)
    assert got is not None
    assert got.content == "hello"
    assert got.scope.user == "alice"
    be.close()


def test_delete_returns_true_then_false(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=4)
    r = MemoryRecord(content="bye")
    be.add(r, None)
    assert be.delete(r.id) is True
    assert be.delete(r.id) is False
    assert be.get(r.id) is None
    be.close()


def test_all_returns_every_record(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=4)
    be.add(MemoryRecord(content="a"), None)
    be.add(MemoryRecord(content="b"), None)
    assert {r.content for r in be.all()} == {"a", "b"}
    be.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_sqlite_backend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.backends.sqlite'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/backends/sqlite.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import sqlite_vec

from ..record import MemoryRecord
from .base import StorageBackend


class SQLiteBackend(StorageBackend):
    def __init__(self, path: str, dim: int = 384) -> None:
        self.dim = dim
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.enable_load_extension(True)
        sqlite_vec.load(self._db)
        self._db.enable_load_extension(False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                rid INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE NOT NULL,
                doc TEXT NOT NULL,
                expires_at REAL
            )
            """
        )
        self._db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_records "
            f"USING vec0(embedding float[{self.dim}])"
        )
        self._db.commit()

    @staticmethod
    def _expires_at(record: MemoryRecord) -> float | None:
        if record.ttl is None:
            return None
        return record.created_at.timestamp() + record.ttl

    def add(self, record: MemoryRecord, embedding: list[float] | None) -> None:
        doc = record.model_dump_json()
        cur = self._db.execute("SELECT rid FROM records WHERE id = ?", (record.id,))
        row = cur.fetchone()
        if row is not None:
            rid = row["rid"]
            self._db.execute(
                "UPDATE records SET doc = ?, expires_at = ? WHERE rid = ?",
                (doc, self._expires_at(record), rid),
            )
            self._db.execute("DELETE FROM vec_records WHERE rowid = ?", (rid,))
        else:
            cur = self._db.execute(
                "INSERT INTO records (id, doc, expires_at) VALUES (?, ?, ?)",
                (record.id, doc, self._expires_at(record)),
            )
            rid = cur.lastrowid
        if embedding is not None:
            self._db.execute(
                "INSERT INTO vec_records (rowid, embedding) VALUES (?, ?)",
                (rid, sqlite_vec.serialize_float32(embedding)),
            )
        self._db.commit()

    def get(self, record_id: str) -> MemoryRecord | None:
        row = self._db.execute(
            "SELECT doc FROM records WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            return None
        return MemoryRecord.model_validate_json(row["doc"])

    def delete(self, record_id: str) -> bool:
        row = self._db.execute(
            "SELECT rid FROM records WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            return False
        rid = row["rid"]
        self._db.execute("DELETE FROM records WHERE rid = ?", (rid,))
        self._db.execute("DELETE FROM vec_records WHERE rowid = ?", (rid,))
        self._db.commit()
        return True

    def all(self) -> list[MemoryRecord]:
        rows = self._db.execute("SELECT doc FROM records").fetchall()
        return [MemoryRecord.model_validate_json(r["doc"]) for r in rows]

    def search(self, embedding: list[float], k: int) -> list[tuple[MemoryRecord, float]]:
        rows = self._db.execute(
            """
            SELECT r.doc AS doc, v.distance AS distance
            FROM vec_records v
            JOIN records r ON r.rid = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
            """,
            (sqlite_vec.serialize_float32(embedding), k),
        ).fetchall()
        return [
            (MemoryRecord.model_validate_json(r["doc"]), float(r["distance"]))
            for r in rows
        ]

    def close(self) -> None:
        self._db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_sqlite_backend.py -v`
Expected: PASS (4 passed — the ABC test plus the 3 new ones)

- [ ] **Step 5: Commit**

```bash
git add src/relio/backends/sqlite.py tests/test_sqlite_backend.py
git commit -m "feat: SQLite backend with add/get/delete/all"
```

---

### Task 4: SQLite backend — vector search

**Files:**
- Test: `tests/test_sqlite_backend.py` (append)

(`search()` was implemented in Task 3; this task proves it works.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sqlite_backend.py  (append)
def test_search_orders_by_distance(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=3)
    near = MemoryRecord(content="near")
    far = MemoryRecord(content="far")
    be.add(near, [1.0, 0.0, 0.0])
    be.add(far, [0.0, 1.0, 0.0])
    results = be.search([0.9, 0.1, 0.0], k=2)
    assert [r.content for r, _ in results] == ["near", "far"]
    assert results[0][1] <= results[1][1]
    be.close()


def test_search_ignores_records_without_embeddings(tmp_path):
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=3)
    be.add(MemoryRecord(content="has_vec"), [1.0, 0.0, 0.0])
    be.add(MemoryRecord(content="no_vec"), None)
    results = be.search([1.0, 0.0, 0.0], k=5)
    assert [r.content for r, _ in results] == ["has_vec"]
    be.close()
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `cd relio && pytest tests/test_sqlite_backend.py -v`
Expected: PASS (search already implemented). If FAIL, fix `search()` in `sqlite.py` until green.

- [ ] **Step 3: (No new code expected)**

If the tests passed in Step 2, skip. If `sqlite-vec` raised on the `k = ?` clause, replace the `WHERE ... AND k = ?` line with `WHERE v.embedding MATCH ? ORDER BY v.distance LIMIT ?` and keep the same parameters order `(serialize(embedding), k)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd relio && pytest tests/test_sqlite_backend.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_sqlite_backend.py src/relio/backends/sqlite.py
git commit -m "test: verify SQLite vector search ordering"
```

---

### Task 5: Embedder ABC + DeterministicEmbedder

**Files:**
- Create: `src/relio/embedding/base.py`
- Test: `tests/test_embedding.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embedding.py
from relio.embedding.base import Embedder, DeterministicEmbedder


def test_deterministic_embedder_is_stable_and_right_dim():
    emb = DeterministicEmbedder(dim=8)
    a = emb.embed("hello")
    b = emb.embed("hello")
    c = emb.embed("world")
    assert emb.dim == 8
    assert len(a) == 8
    assert a == b           # same text -> same vector
    assert a != c           # different text -> different vector


def test_deterministic_embedder_is_an_embedder():
    assert isinstance(DeterministicEmbedder(dim=4), Embedder)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_embedding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.embedding.base'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/embedding/base.py
from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod


class Embedder(ABC):
    @property
    @abstractmethod
    def dim(self) -> int:
        ...

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        ...


class DeterministicEmbedder(Embedder):
    """Hash-based embedder for fast, offline, reproducible tests."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        vec: list[float] = []
        counter = 0
        while len(vec) < self._dim:
            h = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            for i in range(0, len(h), 4):
                if len(vec) >= self._dim:
                    break
                n = int.from_bytes(h[i : i + 4], "big")
                vec.append((n / 2**32) * 2 - 1)  # in [-1, 1)
            counter += 1
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_embedding.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/embedding/base.py tests/test_embedding.py
git commit -m "feat: Embedder ABC and DeterministicEmbedder"
```

---

### Task 6: CachingEmbedder (dedup)

**Files:**
- Create: `src/relio/embedding/cache.py`
- Test: `tests/test_embedding.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embedding.py  (append)
from relio.embedding.cache import CachingEmbedder


class CountingEmbedder(DeterministicEmbedder):
    def __init__(self, dim=4):
        super().__init__(dim)
        self.calls = 0

    def embed(self, text):
        self.calls += 1
        return super().embed(text)


def test_caching_embedder_only_embeds_unique_text_once():
    inner = CountingEmbedder(dim=4)
    cached = CachingEmbedder(inner)
    v1 = cached.embed("same")
    v2 = cached.embed("same")
    cached.embed("other")
    assert v1 == v2
    assert inner.calls == 2          # "same" embedded once, "other" once
    assert cached.dim == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_embedding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.embedding.cache'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/embedding/cache.py
from __future__ import annotations

import hashlib

from .base import Embedder


class CachingEmbedder(Embedder):
    """Wraps an embedder with an in-process dedup cache keyed by content hash."""

    def __init__(self, inner: Embedder) -> None:
        self._inner = inner
        self._cache: dict[str, list[float]] = {}

    @property
    def dim(self) -> int:
        return self._inner.dim

    def embed(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode()).hexdigest()
        if key not in self._cache:
            self._cache[key] = self._inner.embed(text)
        return self._cache[key]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_embedding.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/embedding/cache.py tests/test_embedding.py
git commit -m "feat: CachingEmbedder for dedup"
```

---

### Task 7: LocalEmbedder (fastembed, the zero-cost default)

**Files:**
- Create: `src/relio/embedding/local.py`
- Test: `tests/test_embedding.py` (append, marked integration)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embedding.py  (append)
import pytest


@pytest.mark.integration
def test_local_embedder_returns_expected_dim():
    pytest.importorskip("fastembed")
    from relio.embedding.local import LocalEmbedder

    emb = LocalEmbedder()           # default BAAI/bge-small-en-v1.5
    v = emb.embed("hello world")
    assert emb.dim == 384
    assert len(v) == 384
    assert all(isinstance(x, float) for x in v)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_embedding.py::test_local_embedder_returns_expected_dim -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.embedding.local'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/embedding/local.py
from __future__ import annotations

from .base import Embedder

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
_MODEL_DIMS = {"BAAI/bge-small-en-v1.5": 384}


class LocalEmbedder(Embedder):
    """Local, zero-API-cost embedder using fastembed (ONNX)."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        from fastembed import TextEmbedding

        self._model_name = model_name
        self._model = TextEmbedding(model_name=model_name)
        self._dim = _MODEL_DIMS.get(model_name, 384)

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        # fastembed yields numpy arrays; take the first and convert to list.
        vec = next(iter(self._model.embed([text])))
        return [float(x) for x in vec]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_embedding.py::test_local_embedder_returns_expected_dim -v`
Expected: PASS (downloads the model on first run; may take a minute). If running offline, this test is skipped via `importorskip`.

- [ ] **Step 5: Commit**

```bash
git add src/relio/embedding/local.py tests/test_embedding.py
git commit -m "feat: LocalEmbedder (fastembed) default model"
```

---

### Task 8: Token-light NL-line rendering

**Files:**
- Create: `src/relio/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render.py
from relio.render import render_lines
from relio.record import MemoryRecord, MemoryType


def test_renders_compact_lines_without_json_braces():
    records = [
        MemoryRecord(type=MemoryType.FACT, content="works at Acme",
                     metadata={"tags": ["pref"], "confidence": 0.9}),
        MemoryRecord(content="prefers Python"),
    ]
    text = render_lines(records)
    lines = text.splitlines()
    assert lines[0] == "- works at Acme (pref, 0.9)"
    assert lines[1] == "- prefers Python"
    assert "{" not in text and '"' not in text   # not JSON


def test_empty_input_renders_empty_string():
    assert render_lines([]) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.render'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/render.py
from __future__ import annotations

from .record import MemoryRecord


def _suffix(record: MemoryRecord) -> str:
    parts: list[str] = []
    tags = record.metadata.get("tags")
    if tags:
        parts.extend(str(t) for t in tags)
    conf = record.metadata.get("confidence")
    if conf is not None:
        parts.append(str(conf))
    return f" ({', '.join(parts)})" if parts else ""


def render_lines(records: list[MemoryRecord]) -> str:
    """Render memories as token-light natural-language lines (no JSON)."""
    return "\n".join(f"- {r.content}{_suffix(r)}" for r in records)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_render.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/render.py tests/test_render.py
git commit -m "feat: token-light NL-line rendering"
```

---

### Task 9: RecallEngine (search + scope/type/expiry filter)

**Files:**
- Create: `src/relio/recall.py`
- Test: `tests/test_recall.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recall.py
import time

from relio.backends.sqlite import SQLiteBackend
from relio.embedding.base import DeterministicEmbedder
from relio.recall import RecallEngine
from relio.record import MemoryRecord, MemoryType, Scope


def _engine(tmp_path):
    emb = DeterministicEmbedder(dim=16)
    be = SQLiteBackend(str(tmp_path / "m.db"), dim=16)
    return RecallEngine(be, emb), be, emb


def test_recall_filters_by_scope(tmp_path):
    engine, be, emb = _engine(tmp_path)
    a = MemoryRecord(content="apple pie recipe", scope=Scope(user="alice"))
    b = MemoryRecord(content="apple pie recipe", scope=Scope(user="bob"))
    be.add(a, emb.embed(a.content))
    be.add(b, emb.embed(b.content))
    results = engine.recall("apple pie recipe", scope=Scope(user="alice"), limit=5)
    assert [r.scope.user for r in results] == ["alice"]
    be.close()


def test_recall_filters_by_type(tmp_path):
    engine, be, emb = _engine(tmp_path)
    f = MemoryRecord(type=MemoryType.FACT, content="lives in Kerala")
    s = MemoryRecord(type=MemoryType.SEMANTIC, content="lives in Kerala")
    be.add(f, emb.embed(f.content))
    be.add(s, emb.embed(s.content))
    results = engine.recall("lives in Kerala", type=MemoryType.FACT, limit=5)
    assert all(r.type is MemoryType.FACT for r in results)
    be.close()


def test_recall_excludes_expired_session_memories(tmp_path):
    engine, be, emb = _engine(tmp_path)
    rec = MemoryRecord(type=MemoryType.SESSION, content="temporary note", ttl=-1)
    be.add(rec, emb.embed(rec.content))
    results = engine.recall("temporary note", limit=5, now=time.time())
    assert results == []
    be.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_recall.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.recall'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/recall.py
from __future__ import annotations

import time
from typing import Optional

from .backends.base import StorageBackend
from .embedding.base import Embedder
from .record import MemoryRecord, MemoryType, Scope


class RecallEngine:
    def __init__(self, backend: StorageBackend, embedder: Embedder) -> None:
        self._backend = backend
        self._embedder = embedder

    @staticmethod
    def _scope_matches(query: Scope, record: Scope) -> bool:
        for field in ("tenant", "user", "agent", "session"):
            wanted = getattr(query, field)
            if wanted is not None and getattr(record, field) != wanted:
                return False
        return True

    @staticmethod
    def _is_expired(record: MemoryRecord, now: float) -> bool:
        if record.ttl is None:
            return False
        return record.created_at.timestamp() + record.ttl < now

    def recall(
        self,
        query: str,
        scope: Optional[Scope] = None,
        type: Optional[MemoryType] = None,
        limit: int = 5,
        now: Optional[float] = None,
    ) -> list[MemoryRecord]:
        now = time.time() if now is None else now
        scope = scope or Scope()
        vector = self._embedder.embed(query)
        # Over-fetch so post-filtering still has enough candidates.
        candidates = self._backend.search(vector, k=max(limit * 5, limit))
        out: list[MemoryRecord] = []
        for record, _distance in candidates:
            if type is not None and record.type is not type:
                continue
            if not self._scope_matches(scope, record.scope):
                continue
            if self._is_expired(record, now):
                continue
            out.append(record)
            if len(out) >= limit:
                break
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_recall.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/recall.py tests/test_recall.py
git commit -m "feat: RecallEngine with scope/type/expiry filtering"
```

---

### Task 10: Memory public facade

**Files:**
- Create: `src/relio/memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import MemoryType, Scope


def _mem(tmp_path):
    return Memory(
        path=str(tmp_path / "m.db"),
        embedder=DeterministicEmbedder(dim=16),
    )


def test_add_then_recall_returns_the_memory(tmp_path):
    m = _mem(tmp_path)
    m.add("Alice works at Acme")
    results = m.recall("where does Alice work?", limit=3)
    assert any("Acme" in r.content for r in results)
    m.close()


def test_get_and_forget(tmp_path):
    m = _mem(tmp_path)
    rec = m.add("ephemeral", type=MemoryType.SESSION, ttl=3600)
    assert m.get(rec.id).content == "ephemeral"
    assert m.forget(rec.id) is True
    assert m.get(rec.id) is None
    m.close()


def test_link_adds_a_relation(tmp_path):
    m = _mem(tmp_path)
    person = m.add("Alice", type=MemoryType.NODE)
    org = m.add("Acme", type=MemoryType.NODE)
    m.link(person.id, "works_at", org.id)
    again = m.get(person.id)
    assert again.relations[0].predicate == "works_at"
    assert again.relations[0].target_id == org.id
    m.close()


def test_recall_text_renders_lines(tmp_path):
    m = _mem(tmp_path)
    m.add("prefers Python")
    text = m.recall_text("python", limit=3)
    assert text.startswith("- ")
    m.close()


def test_duplicate_content_is_embedded_once(tmp_path):
    from tests.test_embedding import CountingEmbedder

    m = Memory(path=str(tmp_path / "m.db"), embedder=CountingEmbedder(dim=16))
    m.add("same text")
    m.recall("same text")          # embeds the query once...
    before = m._embedder.calls     # CachingEmbedder wraps CountingEmbedder
    m.recall("same text")          # ...cached on the second identical query
    assert m._embedder.calls == before
    m.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_memory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.memory'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/memory.py
from __future__ import annotations

from typing import Any, Optional

from .backends.base import StorageBackend
from .backends.sqlite import SQLiteBackend
from .embedding.base import Embedder
from .embedding.cache import CachingEmbedder
from .recall import RecallEngine
from .record import MemoryRecord, MemoryType, Relation, Scope
from .render import render_lines


class Memory:
    """The one public entry point: add / recall / get / forget / link."""

    def __init__(
        self,
        path: str = "relio.db",
        embedder: Optional[Embedder] = None,
        backend: Optional[StorageBackend] = None,
    ) -> None:
        if embedder is None:
            from .embedding.local import LocalEmbedder

            embedder = LocalEmbedder()
        self._embedder = CachingEmbedder(embedder)
        self._backend = backend or SQLiteBackend(path, dim=self._embedder.dim)
        self._recall = RecallEngine(self._backend, self._embedder)

    def add(
        self,
        content: str,
        type: MemoryType = MemoryType.SEMANTIC,
        scope: Optional[Scope] = None,
        data: Optional[dict[str, Any]] = None,
        relations: Optional[list[Relation]] = None,
        ttl: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            type=type,
            content=content,
            scope=scope or Scope(),
            data=data or {},
            relations=relations or [],
            ttl=ttl,
            metadata=metadata or {},
        )
        embedding = self._embedder.embed(content) if content else None
        self._backend.add(record, embedding)
        return record

    def recall(
        self,
        query: str,
        scope: Optional[Scope] = None,
        type: Optional[MemoryType] = None,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        return self._recall.recall(query, scope=scope, type=type, limit=limit)

    def recall_text(self, query: str, **kwargs: Any) -> str:
        return render_lines(self.recall(query, **kwargs))

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        return self._backend.get(record_id)

    def forget(self, record_id: str) -> bool:
        return self._backend.delete(record_id)

    def link(self, source_id: str, predicate: str, target_id: str) -> MemoryRecord:
        record = self._backend.get(source_id)
        if record is None:
            raise KeyError(source_id)
        record.relations.append(Relation(predicate=predicate, target_id=target_id))
        embedding = self._embedder.embed(record.content) if record.content else None
        self._backend.add(record, embedding)
        return record

    def close(self) -> None:
        self._backend.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_memory.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/memory.py tests/test_memory.py
git commit -m "feat: Memory public facade (add/recall/get/forget/link)"
```

---

### Task 11: Interchange (import/export)

**Files:**
- Create: `src/relio/interchange.py`
- Test: `tests/test_interchange.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_interchange.py
from relio.interchange import export_records, import_records, from_mem0
from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder


def _mem(tmp_path, name="m.db"):
    return Memory(path=str(tmp_path / name), embedder=DeterministicEmbedder(dim=16))


def test_export_then_import_roundtrips(tmp_path):
    src = _mem(tmp_path, "src.db")
    src.add("fact one")
    src.add("fact two")
    blob = export_records(src)
    dst = _mem(tmp_path, "dst.db")
    count = import_records(dst, blob)
    assert count == 2
    assert {r.content for r in dst.recall("fact", limit=5)} == {"fact one", "fact two"}
    src.close()
    dst.close()


def test_from_mem0_maps_to_records_and_skips_bad_rows():
    mem0_rows = [
        {"id": "a", "memory": "likes tea", "user_id": "alice"},
        {"id": "b"},  # malformed: no memory text
    ]
    records, skipped = from_mem0(mem0_rows)
    assert len(records) == 1
    assert records[0].content == "likes tea"
    assert records[0].scope.user == "alice"
    assert skipped == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_interchange.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.interchange'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/interchange.py
from __future__ import annotations

import json
from typing import Any

from .memory import Memory
from .record import MemoryRecord, Scope


def export_records(memory: Memory) -> str:
    """Serialize all records to a JSON-lines string (the portable interchange form)."""
    return "\n".join(r.model_dump_json() for r in memory._backend.all())


def import_records(memory: Memory, blob: str) -> int:
    """Load records from a JSON-lines blob. Returns the number imported."""
    count = 0
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        record = MemoryRecord.model_validate_json(line)
        embedding = memory._embedder.embed(record.content) if record.content else None
        memory._backend.add(record, embedding)
        count += 1
    return count


def from_mem0(rows: list[dict[str, Any]]) -> tuple[list[MemoryRecord], int]:
    """Map mem0-style export rows into Relio records. Returns (records, skipped)."""
    records: list[MemoryRecord] = []
    skipped = 0
    for row in rows:
        text = row.get("memory") or row.get("text")
        if not text:
            skipped += 1
            continue
        records.append(
            MemoryRecord(
                content=text,
                scope=Scope(user=row.get("user_id")),
                metadata={"imported_from": "mem0", "source_id": row.get("id")},
            )
        )
    return records, skipped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_interchange.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/interchange.py tests/test_interchange.py
git commit -m "feat: import/export interchange (JSONL + mem0 adapter)"
```

---

### Task 12: MCP server

**Files:**
- Create: `src/relio/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_server.py
import pytest

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder


def test_build_mcp_server_exposes_add_and_recall(tmp_path):
    pytest.importorskip("mcp")
    from relio.mcp_server import build_mcp_server

    m = Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))
    server, tools = build_mcp_server(m)
    assert set(tools) == {"add", "recall"}

    tools["add"]("Alice likes hiking")
    text = tools["recall"]("hiking")
    assert "hiking" in text
    m.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_mcp_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relio.mcp_server'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/mcp_server.py
from __future__ import annotations

from typing import Callable

from .memory import Memory


def build_mcp_server(memory: Memory):
    """Build a FastMCP server exposing Relio Memory. Returns (server, tools).

    `tools` is a dict of the underlying callables, so the wiring is unit-testable
    without speaking the MCP wire protocol.
    """
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("relio-memory")

    def add(content: str) -> str:
        """Store a memory. Returns the new record id."""
        return memory.add(content).id

    def recall(query: str, limit: int = 5) -> str:
        """Recall relevant memories as token-light lines."""
        return memory.recall_text(query, limit=limit)

    server.tool()(add)
    server.tool()(recall)

    tools: dict[str, Callable] = {"add": add, "recall": recall}
    return server, tools
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio && pytest tests/test_mcp_server.py -v`
Expected: PASS (1 passed; skipped if `mcp` is not installed)

- [ ] **Step 5: Commit**

```bash
git add src/relio/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: MCP server exposing add/recall"
```

---

### Task 13: Public exports + full-suite smoke

**Files:**
- Modify: `src/relio/__init__.py`
- Test: `tests/test_memory.py` (append a smoke test)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py  (append)
def test_top_level_imports_are_exported():
    import relio

    assert hasattr(relio, "Memory")
    assert hasattr(relio, "MemoryRecord")
    assert hasattr(relio, "MemoryType")
    assert hasattr(relio, "Scope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio && pytest tests/test_memory.py::test_top_level_imports_are_exported -v`
Expected: FAIL with `AttributeError: module 'relio' has no attribute 'Memory'`

- [ ] **Step 3: Write the implementation**

```python
# src/relio/__init__.py
from .memory import Memory
from .record import MemoryRecord, MemoryType, Relation, Scope

__all__ = ["Memory", "MemoryRecord", "MemoryType", "Relation", "Scope"]
```

- [ ] **Step 4: Run the full suite**

Run: `cd relio && pytest -v -m "not integration"`
Expected: PASS (all non-integration tests green). Then optionally run `pytest -v -m integration` with network access to verify `LocalEmbedder`.

- [ ] **Step 5: Commit**

```bash
git add src/relio/__init__.py tests/test_memory.py
git commit -m "feat: export public API; full-suite smoke test"
```

---

## Self-Review

**Spec coverage (engine design doc):**
- Universal record / format → Task 1 (`record.py`). ✅
- SQLite store: vectors (`sqlite-vec`), structured columns (JSON doc), KV/session (ttl + `expires_at`), graph (relations + `link`) → Tasks 3, 4, 10. ✅
- Pluggable `StorageBackend` (storage scaling path) → Task 2 ABC; SQLite is one impl. ✅
- Embedding layer: local default (`fastembed`), cache + dedup → Tasks 5, 6, 7. ✅
- Token-light NL-line recall → Task 8 (render) + Task 9 (recall). ✅
- Public API add/recall/get/forget/link → Task 10. ✅
- Import/export interchange (incl. mem0 adapter, skip-and-count bad rows) → Task 11. ✅
- MCP server → Task 12. ✅
- Scope (tenant/user/agent/session) filtering + TTL expiry → Task 9. ✅

**Deferred (not in this plan, by design):** Postgres backend, persistent embedding cache, full graph traversal queries, FastAPI/React/DevOps layers, auth/multi-tenant DB-per-tenant. These belong to later plans per the architecture doc.

**Type consistency:** `MemoryRecord`, `MemoryType`, `Scope`, `Relation` defined in Task 1 and used identically throughout. `StorageBackend` methods (`add(record, embedding)`, `get`, `delete`, `search(embedding, k)`, `all`, `close`) defined in Task 2 and matched by `SQLiteBackend` (Task 3) and consumed by `RecallEngine`/`Memory` (Tasks 9–10). `Embedder.dim`/`embed` consistent across Tasks 5–7 and wrapped by `CachingEmbedder`. No undefined references.

**Placeholder scan:** No TBD/TODO; every code step contains complete, runnable code.
