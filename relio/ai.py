# relio/ai.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Optional, Union

from .exposure import ExposureMap
from .memory import Memory
from .record import MemoryRecord, MemoryType, Relation, Scope


def validate_extraction(data: dict, schema: Optional[dict]) -> dict:
    """Ensure model-extracted `data` has the schema's `required` fields.

    A minimal, dependency-free guard — extraction output is untrusted, so validate
    before feeding it to business logic."""
    required = (schema or {}).get("required", [])
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"extraction missing required fields: {missing}")
    return data


class RelioAI:
    """The called-in AI component: one seam composing the AI-system components
    (memory/RAG, embeddings, graph, structured query, reasoning, MCP interop).

    The LLM is optional — construct it with no provider for a pure
    memory/retrieval/data component, and add a provider when you need `chat`.
    """

    def __init__(
        self,
        memory: Optional[Memory] = None,
        provider: Optional[object] = None,
        *,
        path: str = "relio.db",
        embedder: Optional[object] = None,
        database_url: Optional[str] = None,
    ) -> None:
        self.memory = memory or Memory(
            path=path, embedder=embedder, database_url=database_url
        )
        self.provider = provider
        self.tools = ExposureMap()  # the governed surface the AI may call

    # --- knowledge & retrieval ----------------------------------------------

    def remember(
        self,
        content: str,
        type: MemoryType = MemoryType.SEMANTIC,
        scope: Optional[Scope] = None,
        **kwargs: Any,
    ) -> MemoryRecord:
        return self.memory.add(content, type=type, scope=scope, **kwargs)

    def remember_many(
        self,
        items: list[Union[str, dict]],
        type: MemoryType = MemoryType.SEMANTIC,
        scope: Optional[Scope] = None,
        embed: bool = True,
    ) -> list[MemoryRecord]:
        """Bulk-remember: each item is a string or a `{"content", "metadata", ...}`
        mapping — for ingesting rows with metadata in one atomic, batched call."""
        return self.memory.add_many(items, type=type, scope=scope, embed=embed)

    def recall(
        self, query: str, scope: Optional[Scope] = None, limit: int = 5
    ) -> list[MemoryRecord]:
        return self.memory.recall(query, scope=scope, limit=limit)

    def recall_text(self, query: str, **kwargs: Any) -> str:
        return self.memory.recall_text(query, **kwargs)

    def embed(self, texts: Union[str, list[str]]) -> Union[list[float], list[list[float]]]:
        if isinstance(texts, str):
            return self.memory.embedder.embed(texts)
        return self.memory.embedder.embed_batch(list(texts))

    # --- graph ---------------------------------------------------------------

    def add_node(self, content: str, **kwargs: Any) -> MemoryRecord:
        return self.memory.add_node(content, **kwargs)

    def add_edge(self, source_id: str, predicate: str, target_id: str) -> MemoryRecord:
        return self.memory.add_edge(source_id, predicate, target_id)

    def neighbors(self, node_id: str, predicate: Optional[str] = None) -> list[MemoryRecord]:
        return self.memory.neighbors(node_id, predicate=predicate)

    def in_neighbors(self, node_id: str, predicate: Optional[str] = None) -> list[MemoryRecord]:
        return self.memory.in_neighbors(node_id, predicate=predicate)

    def traverse(self, start_id: str, depth: int = 1, predicate: Optional[str] = None) -> list[MemoryRecord]:
        return self.memory.traverse(start_id, depth=depth, predicate=predicate)

    # --- structured query ----------------------------------------------------

    def query(
        self,
        type: Optional[MemoryType] = None,
        scope: Optional[Scope] = None,
        where: Optional[dict] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        return self.memory.query(
            type=type, scope=scope, where=where, order_by=order_by, limit=limit, offset=offset
        )

    def sql(self, query: str, params: Optional[tuple] = None) -> list[dict]:
        """Read-only analytical SQL over the store (Postgres backend only) — for
        joins/GROUP BY/windows beyond `query()`. See `Memory.sql`."""
        return self.memory.sql(query, params)

    def transaction(self):
        return self.memory.transaction()

    # --- reasoning -----------------------------------------------------------

    @property
    def has_llm(self) -> bool:
        return self.provider is not None

    def chat(
        self, message: str, scope: Optional[Scope] = None, **kwargs: Any
    ) -> Iterator[str]:
        if self.provider is None:
            raise RuntimeError(
                "RelioAI.chat needs an LLM provider; construct RelioAI(provider=...)"
            )
        from .server.agent import run_chat

        return run_chat(self.memory, self.provider, message, scope or Scope(), **kwargs)

    # --- structured / multimodal extraction (D6) ----------------------------

    def supports(self, capability: str) -> bool:
        """Pre-flight for app/UI: is a provider present *and* does it support this
        capability (`"extract"` / `"complete_with_tools"` / `"transcribe"`)?"""
        return self.provider is not None and self.provider.supports(capability)

    def _require_provider(self, what: str, capability: Optional[str] = None) -> None:
        if self.provider is None:
            raise RuntimeError(f"RelioAI.{what} needs an LLM provider")
        if capability is not None and not self.provider.supports(capability):
            from .server.llm.base import CapabilityError

            name = type(self.provider).__name__
            raise CapabilityError(
                f"the {name} provider does not support {capability!r} "
                f"(needed by RelioAI.{what})"
            )

    def extract(self, text: str, schema: Optional[dict] = None, validate: bool = False) -> dict:
        """Extract structured data from text into `schema`.

        Model output is untrusted — pass `validate=True` to enforce the schema's
        `required` fields before you use the result.
        """
        self._require_provider("extract", "extract")
        result = self.provider.extract(text, schema=schema)
        return validate_extraction(result, schema) if validate else result

    def extract_file(
        self,
        file: Union[str, Path, bytes, bytearray],
        schema: Optional[dict] = None,
        media_type: str = "application/pdf",
        validate: bool = False,
    ) -> dict:
        """Extract structured data from a file (PDF/image) into `schema` — the
        path for "read this drawing/scan and give me a bill"."""
        self._require_provider("extract_file", "extract")
        data = bytes(file) if isinstance(file, (bytes, bytearray)) else Path(file).read_bytes()
        result = self.provider.extract(
            "", schema=schema, image_bytes=data, media_type=media_type
        )
        return validate_extraction(result, schema) if validate else result

    def transcribe(
        self,
        audio: Union[str, Path, bytes, bytearray],
        *,
        media_type: str = "audio/webm",
        language: Optional[str] = None,
    ) -> str:
        """Speech-to-text: turn a voice clip into text (server-side STT). Pairs
        with the browser's Web Speech API on the client, with this as the
        fallback. `audio` is raw bytes or a path."""
        self._require_provider("transcribe", "transcribe")
        data = bytes(audio) if isinstance(audio, (bytes, bytearray)) else Path(audio).read_bytes()
        return self.provider.transcribe(data, media_type=media_type, language=language)

    # --- tools / exposure map (D3) ------------------------------------------

    def tool(
        self,
        fn=None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        destructive: bool = False,
    ):
        """Register an app operation the AI may call (decorator)."""
        return self.tools.tool(fn, name=name, description=description, destructive=destructive)

    def expose(self, obj: Any, fields: list[str]) -> dict[str, Any]:
        """Field allowlist: project `obj` to only `fields` for AI consumption."""
        return ExposureMap.project(obj, fields)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
                "destructive": s.destructive,
            }
            for s in self.tools.list()
        ]

    def call_tool(
        self, name: str, *, scope: Optional[Scope] = None, confirm: bool = False, **kwargs: Any
    ) -> Any:
        """Invoke an exposed tool. If the tool declares a `scope` parameter, the
        given `scope` is injected for it (per-request principal) — pass the
        current request's Scope for multi-tenant isolation."""
        return self.tools.call(name, scope=scope, confirm=confirm, **kwargs)

    # --- agents (D4) ---------------------------------------------------------

    def agent(
        self,
        name: str,
        *,
        space: Optional[Scope] = None,
        tools: Optional[list[str]] = None,
        system: str = "",
        model: Optional[str] = None,
        recall_limit: int = 5,
    ):
        """Construct a bounded agent: its own memory namespace + tool slice +
        config + session. Private by default."""
        from .agents import Agent

        return Agent(
            self,
            name,
            space=space,
            tools=tools,
            system=system,
            model=model,
            recall_limit=recall_limit,
        )

    # --- interop -------------------------------------------------------------

    def mcp_server(self, include_tools: bool = True):
        """The FastMCP server exposing this memory (add/recall) and — when
        `include_tools` — the exposure-map tools, to external agents."""
        from .mcp_server import build_mcp_server

        server, tools = build_mcp_server(self.memory)
        if include_tools:
            for spec in self.tools.list():
                server.tool()(spec.fn)
                tools[spec.name] = spec.fn
        return server, tools

    def close(self) -> None:
        self.memory.close()
