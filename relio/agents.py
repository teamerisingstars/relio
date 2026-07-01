# relio/agents.py
from __future__ import annotations

from typing import Any, Iterator, Optional

from .record import MemoryRecord, Scope


class Agent:
    """A bounded agent context: its own memory namespace, tool slice, config,
    and session. Private by default — it sees only its own space and the tools
    it was granted.
    """

    def __init__(
        self,
        ai: Any,
        name: str,
        *,
        space: Optional[Scope] = None,
        tools: Optional[list[str]] = None,
        system: str = "",
        model: Optional[str] = None,
        recall_limit: int = 5,
    ) -> None:
        self.ai = ai
        self.name = name
        self.space = space or Scope(agent=name)  # its own memory namespace
        self._allowed: Optional[set[str]] = set(tools) if tools is not None else None
        self.system = system
        self.model = model
        self.recall_limit = recall_limit

    # --- memory namespace (isolated) ----------------------------------------

    def remember(self, content: str, **kwargs: Any) -> MemoryRecord:
        return self.ai.remember(content, scope=self.space, **kwargs)

    def recall(self, query: str, limit: Optional[int] = None) -> list[MemoryRecord]:
        return self.ai.recall(query, scope=self.space, limit=limit or self.recall_limit)

    def history(self, limit: int = 20) -> list[MemoryRecord]:
        return self.ai.memory.history(self.space, limit=limit)

    # --- tool slice (granted subset of the exposure map) --------------------

    def tools(self) -> list[str]:
        names = self.ai.tools.names()
        return names if self._allowed is None else [n for n in names if n in self._allowed]

    def call_tool(self, name: str, *, confirm: bool = False, **kwargs: Any) -> Any:
        if self._allowed is not None and name not in self._allowed:
            raise PermissionError(f"agent {self.name!r} may not call tool {name!r}")
        return self.ai.call_tool(name, confirm=confirm, **kwargs)

    # --- reasoning (scoped to this agent) -----------------------------------

    def chat(self, message: str, **kwargs: Any) -> Iterator[str]:
        if self.ai.provider is None:
            raise RuntimeError("agent chat needs an LLM provider")
        from .server.agent import run_chat

        prefix = (self.system + "\n\n") if self.system else ""
        return run_chat(
            self.ai.memory,
            self.ai.provider,
            message,
            self.space,
            limit=self.recall_limit,
            system_prefix=prefix,
            **kwargs,
        )
