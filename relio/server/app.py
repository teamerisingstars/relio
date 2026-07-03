from __future__ import annotations

import time
from typing import Optional, Sequence

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from ..logs import get_logger
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
    auth: Optional[AuthHook] = None,
    *,
    extra_routers: Optional[Sequence[object]] = None,  # router | (router, protected: bool)
    protect_extra_routers: bool = True,
    rate_limit: Optional[tuple[int, float]] = None,
    max_body_bytes: Optional[int] = None,
    cors_origins: Optional[Sequence[str]] = None,
    request_logging: bool = False,
) -> FastAPI:
    settings = settings or Settings()
    # No auth hook wired = every request gets a wildcard scope, so query/search/
    # history read ACROSS all tenants and writes have empty scope. Keep the
    # zero-config default working, but warn loudly so it isn't shipped unnoticed.
    if auth is None:
        auth = anonymous_auth
        get_logger("server.app").warning(
            "create_app() has no auth= hook: all requests use a wildcard scope "
            "(cross-tenant reads/writes). Pass auth=ApiKeyAuth(...)/JWTAuth(...) "
            "for production, or auth=anonymous_auth to silence this."
        )
    app = FastAPI(title="Relio")

    if request_logging:
        _log = get_logger("server.request")

        @app.middleware("http")
        async def _log_requests(request: Request, call_next):
            started = time.time()
            response = await call_next(request)
            _log.info(
                "%s %s -> %s (%.1fms)",
                request.method, request.url.path, response.status_code,
                (time.time() - started) * 1000,
                extra={"relio": {
                    "method": request.method, "path": request.url.path,
                    "status": response.status_code,
                    "ms": round((time.time() - started) * 1000, 1),
                }},
            )
            return response

    @app.get("/api/health", operation_id="health")
    def health():
        return {"status": "ok"}

    app.include_router(build_memory_router(memory, auth))
    app.include_router(build_history_router(memory, auth))
    app.include_router(build_graph_router(memory, auth))
    # The LLM is optional: chat only exists when a provider is supplied.
    if provider is not None:
        app.include_router(build_chat_router(memory, provider, settings, auth))
    # App routers must register BEFORE the SPA catch-all (mounted last), or the
    # frontend would shadow them. They're protected by the SAME `auth` hook as the
    # built-ins by default — otherwise `create_app(auth=...)` would give a false
    # sense of security while leaving your own endpoints wide open.
    #
    # Per-router control: an item may be a bare router (uses the app-wide
    # `protect_extra_routers` default) OR a `(router, protected: bool)` tuple. Mount
    # a PUBLIC auth router (register/login) as `(accounts_router, False)` while the
    # rest stay protected — keeping the safe default without an app-wide opt-out.
    for item in extra_routers or []:
        router, protected = item if isinstance(item, tuple) else (item, protect_extra_routers)
        app.include_router(router, dependencies=[Depends(auth)] if protected else [])

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
