# relio/aiapp/app.py
from __future__ import annotations

from typing import Any, Optional

from ..ai import RelioAI


class AIApp:
    """Opinionated, batteries-included framework for AI applications.

    Composes a `RelioAI` (memory + LLM), a set of **bounded agents**, and a ready
    HTTP server (chat, memory, graph, and per-agent endpoints). Build a full
    AI-first backend in a few lines::

        app = AIApp(provider=ClaudeProvider())
        app.agent("assistant", system="You are helpful.")
        asgi = app.build()          # uvicorn app:asgi
    """

    def __init__(
        self,
        ai: Optional[RelioAI] = None,
        *,
        provider: Optional[object] = None,
        path: str = "relio.db",
        embedder: Optional[object] = None,
        database_url: Optional[str] = None,
        settings: Optional[object] = None,
        auth: Optional[object] = None,
    ) -> None:
        self.ai = ai or RelioAI(
            provider=provider, path=path, embedder=embedder, database_url=database_url
        )
        self._agents: dict[str, Any] = {}
        self._settings = settings
        self._auth = auth

    def agent(self, name: str, **kwargs: Any):
        """Register a bounded agent (own memory namespace + tool slice + config)."""
        agent = self.ai.agent(name, **kwargs)
        self._agents[name] = agent
        return agent

    def tool(self, fn=None, *, name: Optional[str] = None, description: Optional[str] = None):
        """Register an exposure-map tool the agents may call."""
        return self.ai.tool(fn, name=name, description=description)

    @property
    def agents(self) -> dict[str, Any]:
        return dict(self._agents)

    def build(self):
        """Return the FastAPI app: base Relio routes + a per-agent router."""
        from ..server.app import create_app
        from ..server.auth import anonymous_auth
        from .routes import build_agents_router

        auth = self._auth or anonymous_auth
        app = create_app(
            self.ai.memory, self.ai.provider, settings=self._settings, auth=auth
        )
        app.include_router(build_agents_router(self._agents))
        return app
