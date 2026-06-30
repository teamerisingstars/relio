# relio/mcp_server.py
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
