from __future__ import annotations

from typing import Optional

from fastapi import FastAPI

from ..memory import Memory
from .auth import AuthHook, anonymous_auth
from .config import Settings
from .llm.base import LLMProvider
from .routes.chat import build_chat_router
from .routes.graph import build_graph_router
from .routes.history import build_history_router
from .routes.memory import build_memory_router
from .static import mount_frontend


def create_app(
    memory: Memory,
    provider: Optional[LLMProvider] = None,
    settings: Optional[Settings] = None,
    frontend_dir: Optional[str] = None,
    auth: AuthHook = anonymous_auth,
) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Relio")

    @app.get("/api/health", operation_id="health")
    def health():
        return {"status": "ok"}

    app.include_router(build_memory_router(memory, auth))
    app.include_router(build_history_router(memory, auth))
    app.include_router(build_graph_router(memory))
    # The LLM is optional: chat only exists when a provider is supplied.
    if provider is not None:
        app.include_router(build_chat_router(memory, provider, settings, auth))
    app.state.relio_memory = memory
    app.state.relio_provider = provider
    app.state.relio_settings = settings
    if frontend_dir is not None:
        mount_frontend(app, frontend_dir)  # catch-all registered last
    return app
