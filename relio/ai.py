# relio/ai.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Optional, Union

from .exposure import ExposureMap
from .memory import Memory
from .record import MemoryRecord, MemoryType, Relation, Scope


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
        where: Optional[dict[str, str]] = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        return self.memory.query(type=type, scope=scope, where=where, limit=limit)

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

    def _require_provider(self, what: str) -> None:
        if self.provider is None:
            raise RuntimeError(f"RelioAI.{what} needs an LLM provider")

    def extract(self, text: str, schema: Optional[dict] = None) -> dict:
        """Extract structured data from text into `schema`."""
        self._require_provider("extract")
        return self.provider.extract(text, schema=schema)

    def extract_file(
        self,
        file: Union[str, Path, bytes, bytearray],
        schema: Optional[dict] = None,
        media_type: str = "application/pdf",
    ) -> dict:
        """Extract structured data from a file (PDF/image) into `schema` — the
        path for "read this drawing/scan and give me a bill"."""
        self._require_provider("extract_file")
        data = bytes(file) if isinstance(file, (bytes, bytearray)) else Path(file).read_bytes()
        return self.provider.extract("", schema=schema, image_bytes=data, media_type=media_type)

    # --- tools / exposure map (D3) ------------------------------------------

    def tool(self, fn=None, *, name: Optional[str] = None, description: Optional[str] = None):
        """Register an app operation the AI may call (decorator)."""
        return self.tools.tool(fn, name=name, description=description)

    def expose(self, obj: Any, fields: list[str]) -> dict[str, Any]:
        """Field allowlist: project `obj` to only `fields` for AI consumption."""
        return ExposureMap.project(obj, fields)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": s.name, "description": s.description, "parameters": s.parameters}
            for s in self.tools.list()
        ]

    def call_tool(self, name: str, **kwargs: Any) -> Any:
        return self.tools.call(name, **kwargs)

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
