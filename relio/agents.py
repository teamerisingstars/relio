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
        # This agent's space is its principal — injected into scope-aware tools.
        return self.ai.call_tool(name, scope=self.space, confirm=confirm, **kwargs)

    # --- reasoning (scoped to this agent) -----------------------------------

    def run(self, task: str, max_steps: int = 6) -> str:
        """Autonomous loop: the LLM picks tools from this agent's slice, we execute
        them, feed results back, and repeat until it returns a final answer.
        Destructive tools are never auto-run — they're blocked pending confirmation.
        """
        from .server.llm.base import CapabilityError, Message

        if self.ai.provider is None:
            raise RuntimeError("agent.run needs an LLM provider")
        if not self.ai.provider.supports("complete_with_tools"):
            raise CapabilityError(
                f"the {type(self.ai.provider).__name__} provider does not support "
                "tool-calling ('complete_with_tools'), which agent.run requires"
            )
        tool_defs = [t for t in self.ai.list_tools() if self._allowed is None or t["name"] in self._allowed]
        messages = [Message(role="user", content=task)]
        for _ in range(max_steps):
            step = self.ai.provider.complete_with_tools(messages, self.system, tool_defs)
            if "text" in step and "tool_calls" not in step:
                return step["text"]
            for call in step.get("tool_calls", []):
                name, args = call["name"], call.get("arguments", {})
                spec = self.ai.tools._tools.get(name)
                if self._allowed is not None and name not in self._allowed:
                    output = f"[tool {name} denied: not in this agent's tools]"
                elif spec is not None and spec.destructive:
                    output = f"[tool {name} blocked: destructive, needs human confirmation]"
                else:
                    output = self.ai.call_tool(name, scope=self.space, **args)
                messages.append(Message(role="assistant", content=f"calling {name}"))
                messages.append(Message(role="user", content=f"[tool {name}] result: {output}"))
        return step.get("text", "[max steps reached]")

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
