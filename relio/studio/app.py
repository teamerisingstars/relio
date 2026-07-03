# relio/studio/app.py
"""The Relio Studio FastAPI app — a local control panel for creating and
controlling Relio projects.

Thin wiring only: it maps HTTP routes onto the registry (project tracking), the
process manager (running commands), and the scaffold/check functions the CLI
already uses. Registry and manager are injectable so the whole app is testable
without touching the real home directory or spawning real processes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from ..cli.check import check_project
from ..cli.scaffold import write_ai_scaffold, write_scaffold
from .actions import ACTIONS, action_command, app_url
from .process import ProcessManager
from .registry import Registry

# Kinds the "New Project" dialog offers, mapped to scaffold behaviour.
_SCAFFOLD_KINDS = {"app", "web", "mobile", "desktop", "ai"}


def _default_web_dir() -> str:
    return str(Path(__file__).parent / "web")


class CreateProject(BaseModel):
    name: str
    parent_dir: str
    kind: str = "app"


class ImportProject(BaseModel):
    path: str


class ScanFolder(BaseModel):
    folder: str


def _scaffold(kind: str, target: str, name: str) -> None:
    if kind == "ai":
        write_ai_scaffold(target, name)
    else:
        write_scaffold(
            target, name,
            web=(kind == "web"), mobile=(kind == "mobile"), desktop=(kind == "desktop"),
        )


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def create_studio_app(
    registry: Optional[Registry] = None,
    manager: Optional[object] = None,
    web_dir: Optional[str] = None,
    token: Optional[str] = None,
) -> FastAPI:
    reg = registry or Registry()
    mgr = manager or ProcessManager()
    web = web_dir or _default_web_dir()

    app = FastAPI(title="Relio Studio")
    app.state.registry = reg
    app.state.manager = mgr
    app.state.token = token

    if token is not None:
        # Hardened mode (the real `relio gui`): even though Studio binds loopback,
        # a malicious web page or a DNS-rebinding attack could otherwise drive these
        # process-spawning endpoints. Require a per-launch token AND a loopback Host.
        @app.middleware("http")
        async def _guard(request, call_next):
            if request.url.path.startswith("/api/"):
                host = request.headers.get("host", "").rsplit(":", 1)[0]
                if host not in _LOOPBACK_HOSTS:
                    return JSONResponse({"detail": "bad host"}, status_code=403)
                if request.headers.get("x-relio-studio-token") != token:
                    return JSONResponse({"detail": "forbidden"}, status_code=403)
            return await call_next(request)

    def _require(project_id: str):
        rec = reg.get(project_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="project not found")
        return rec

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/projects")
    def list_projects():
        out = []
        for rec in reg.list():
            d = rec.as_dict()
            d["status"] = mgr.status(rec.id)
            out.append(d)
        return out

    @app.post("/api/projects")
    def create_project(body: CreateProject):
        if body.kind not in _SCAFFOLD_KINDS:
            raise HTTPException(status_code=400, detail=f"unknown kind: {body.kind}")
        target = Path(body.parent_dir) / body.name
        if target.exists():
            raise HTTPException(status_code=409, detail="target already exists")
        try:
            _scaffold(body.kind, str(target), body.name)
        except Exception as exc:  # scaffold failure -> a clean 400, not a 500
            raise HTTPException(status_code=400, detail=f"scaffold failed: {exc}")
        return reg.add(str(target), body.name, body.kind).as_dict()

    @app.post("/api/projects/import")
    def import_project(body: ImportProject):
        if reg.detect(body.path) is None:
            raise HTTPException(status_code=400, detail="not a Relio project")
        return reg.add(body.path).as_dict()

    @app.post("/api/projects/scan")
    def scan_folder(body: ScanFolder):
        return {"found": reg.scan(body.folder)}

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str):
        if not reg.remove(project_id):
            raise HTTPException(status_code=404, detail="project not found")
        return {"removed": project_id}

    @app.post("/api/projects/{project_id}/actions/{action}")
    def start_action(project_id: str, action: str, params: Optional[dict] = None):
        rec = _require(project_id)
        params = params or {}
        try:
            cmd = action_command(action, params)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        mgr.start(rec.id, action, cmd, cwd=rec.path)
        return {"action": action, "running": True, "url": app_url(action, params)}

    @app.post("/api/projects/{project_id}/stop/{action}")
    def stop_action(project_id: str, action: str):
        rec = _require(project_id)
        return {"stopped": mgr.stop(rec.id, action)}

    @app.get("/api/projects/{project_id}/logs/{action}")
    def get_logs(project_id: str, action: str, since: int = 0):
        rec = _require(project_id)
        nxt, lines = mgr.logs(rec.id, action, since)
        status = mgr.status(rec.id).get(action, {})
        return {
            "next": nxt,
            "lines": lines,
            "running": status.get("running", False),
            "returncode": status.get("returncode"),
        }

    @app.get("/api/projects/{project_id}/check")
    def check(project_id: str):
        rec = _require(project_id)
        violations = [{"path": v.path, "missing": v.missing} for v in check_project(rec.path)]
        return {"violations": violations}

    _mount_web(app, web, token)
    return app


def _mount_web(app: FastAPI, web_dir: str, token: Optional[str]) -> None:
    """Serve the no-build Studio frontend, with an index fallback for the SPA."""
    web = Path(web_dir)
    index = web / "index.html"
    base = web.resolve()

    def _serve_index():
        # Inject the per-launch token so app.js can authenticate its /api calls.
        html = index.read_text(encoding="utf-8")
        if token is not None:
            inject = f'<script>window.__RELIO_TOKEN__={token!r};</script>'
            html = html.replace("</head>", inject + "</head>", 1) if "</head>" in html \
                else inject + html
        return HTMLResponse(html)

    @app.get("/")
    def root():
        if index.is_file():
            return _serve_index()
        raise HTTPException(status_code=404, detail="studio frontend not built")

    @app.get("/{asset:path}")
    def asset(asset: str):
        if asset.startswith("api/") or asset == "api":
            raise HTTPException(status_code=404, detail="not found")
        # Confine to the web dir — `..%2f` percent-decodes to `..` without
        # normalization, so an unconfined join would allow arbitrary file reads.
        candidate = (web / asset).resolve()
        if asset and candidate.is_file() and candidate.is_relative_to(base):
            return FileResponse(str(candidate))
        if index.is_file():
            return _serve_index()
        raise HTTPException(status_code=404, detail="not found")
