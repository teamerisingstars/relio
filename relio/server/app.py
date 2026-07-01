from __future__ import annotations

import time
from typing import Optional, Sequence

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..memory import Memory
from .auth import AuthHook, anonymous_auth
from .config import Settings
from .llm.base import LLMProvider
from .routes.chat import build_chat_router
from .routes.graph import build_graph_router
from .routes.history import build_history_router
from .routes.memory import build_memory_router
from .security import RateLimiter
from .static import mount_frontend


def create_app(
    memory: Memory,
    provider: Optional[LLMProvider] = None,
    settings: Optional[Settings] = None,
    frontend_dir: Optional[str] = None,
    auth: AuthHook = anonymous_auth,
    *,
    extra_routers: Optional[Sequence[object]] = None,
    rate_limit: Optional[tuple[int, float]] = None,
    max_body_bytes: Optional[int] = None,
    cors_origins: Optional[Sequence[str]] = None,
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
    # App routers must register BEFORE the SPA catch-all (mounted last), or the
    # frontend would shadow them.
    for router in extra_routers or []:
        app.include_router(router)

    app.state.relio_memory = memory
    app.state.relio_provider = provider
    app.state.relio_settings = settings

    _apply_security(
        app, rate_limit=rate_limit, max_body_bytes=max_body_bytes, cors_origins=cors_origins
    )
    if frontend_dir is not None:
        mount_frontend(app, frontend_dir)  # catch-all registered last
    return app


def _apply_security(
    app: FastAPI,
    *,
    rate_limit: Optional[tuple[int, float]],
    max_body_bytes: Optional[int],
    cors_origins: Optional[Sequence[str]],
) -> None:
    if cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if max_body_bytes:
        @app.middleware("http")
        async def _limit_body_size(request: Request, call_next):
            cl = request.headers.get("content-length")
            if cl is not None and cl.isdigit() and int(cl) > max_body_bytes:
                return JSONResponse({"detail": "request too large"}, status_code=413)
            return await call_next(request)

    if rate_limit:
        limiter = RateLimiter(rate_limit[0], rate_limit[1])

        @app.middleware("http")
        async def _rate_limit(request: Request, call_next):
            key = request.client.host if request.client else "?"
            if not limiter.allow(key, time.time()):
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
            return await call_next(request)
