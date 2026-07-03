# relio/cli/main.py
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from .dockerfile import render_dockerfile
from .scaffold import write_scaffold

Runner = Callable[..., int]
Spawn = Callable[..., "subprocess.Popen[bytes]"]


def _npm() -> str:
    """Windows ships npm as `npm.cmd`; a bare `"npm"` isn't found by CreateProcess
    (→ WinError 2). Resolve it, falling back to the platform-correct name."""
    return shutil.which("npm") or ("npm.cmd" if os.name == "nt" else "npm")


def _missing_server_extra() -> bool:
    """True if FastAPI/uvicorn aren't installed (the `server` extra is absent)."""
    import importlib.util

    return any(importlib.util.find_spec(m) is None for m in ("uvicorn", "fastapi"))


def _needs_server_extra() -> bool:
    """Preflight: print an install hint and signal failure if the extra is missing."""
    if _missing_server_extra():
        print(
            'This command needs the server extra: pip install "relio[server]"',
            file=sys.stderr,
        )
        return True
    return False


def run(cmd: list[str], cwd: Optional[str] = None) -> int:
    return subprocess.call(cmd, cwd=cwd)


def spawn(cmd: list[str], cwd: Optional[str] = None) -> "subprocess.Popen[bytes]":
    return subprocess.Popen(cmd, cwd=cwd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relio", description="Relio framework CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="scaffold a new memory-native app")
    new.add_argument("name")
    new.add_argument(
        "--web", action="store_true", help="scaffold a React + Vite app (with generated SDK)"
    )
    new.add_argument(
        "--mobile", action="store_true", help="scaffold a React Native / Expo app"
    )
    new.add_argument(
        "--desktop", action="store_true", help="scaffold a Tauri desktop app"
    )

    sub.add_parser("dev", help="run backend + frontend dev servers")
    sub.add_parser("build", help="build the React frontend")

    serve = sub.add_parser("serve", help="serve API + built frontend on one port")
    serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("dockerfile", help="write the production Dockerfile")
    deploy = sub.add_parser("deploy", help="build the Docker image, or write free-host deploy config")
    deploy.add_argument("--name", default="relio-app", help="image/app name (default: relio-app)")
    deploy.add_argument(
        "--target",
        choices=["docker", "fly", "render", "hf", "vercel", "lambda", "netlify"],
        default="docker",
        help="docker: build the image (default). fly/render/hf: container hosts. "
             "vercel/lambda/netlify: serverless (needs pooled Postgres + hosted "
             "embedder; use POST /api/chat/complete instead of SSE).",
    )

    sdk = sub.add_parser("sdk", help="generate TS + Python client SDKs from the API")
    sdk.add_argument("--out", default="sdk", help="output directory (default: sdk)")
    sdk.add_argument(
        "--app", default="app:app",
        help="your FastAPI app as module:attr (default: app:app) — so the SDK "
             "covers your custom endpoints",
    )

    develop = sub.add_parser("develop", help="drive Claude Code to build the app")
    develop.add_argument("prompt", nargs="?", help="what to build (optional)")

    test = sub.add_parser("test", help="run the project's test suites")
    test.add_argument("--coverage", action="store_true", help="enforce a coverage threshold")
    test.add_argument("--min", type=int, default=80, help="minimum coverage %% (with --coverage)")

    check = sub.add_parser("check", help="fail if any module lacks a test or a doc")
    check.add_argument("--path", default=".", help="project root to check (default: .)")

    migrate = sub.add_parser(
        "migrate", help="copy a memory store between backends (e.g. SQLite -> Postgres)"
    )
    migrate.add_argument("--from", dest="src", required=True, help="source: SQLite path or postgres:// URL")
    migrate.add_argument("--to", dest="dst", required=True, help="destination: SQLite path or postgres:// URL")
    migrate.add_argument(
        "--no-embed", action="store_true",
        help="structured-only copy: skip re-embedding (recall won't work until re-embedded)",
    )

    gui = sub.add_parser("gui", help="open Relio Studio: a local GUI to create and control projects")
    gui.add_argument("--port", type=int, default=4000, help="port to serve Studio on (default: 4000)")
    gui.add_argument("--host", default="127.0.0.1", help="host to bind (default: 127.0.0.1, local only)")
    gui.add_argument("--no-open", action="store_true", help="don't open the browser automatically")

    ai = sub.add_parser("ai", help="AI-application framework (AIApp) commands")
    ai_sub = ai.add_subparsers(dest="ai_command", required=True)
    ai_new = ai_sub.add_parser("new", help="scaffold an AI-first app (agent + memory)")
    ai_new.add_argument("name")
    return parser


def cmd_new(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    write_scaffold(
        args.name,
        args.name,
        web=getattr(args, "web", False),
        mobile=getattr(args, "mobile", False),
        desktop=getattr(args, "desktop", False),
    )
    return 0


def cmd_dev(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    if _needs_server_extra():
        return 1
    # The default (non-web) scaffold has no vite dev server — running npm would
    # just error. Detect that and run the backend alone.
    if not Path("web/package.json").exists():
        return runner([sys.executable, "-m", "uvicorn", "app:app", "--reload"])
    # Web scaffold: start the backend (auto-reload) in the background, then run the
    # Vite dev server in the foreground (it proxies /api to the backend). Stop the
    # backend when the dev server exits.
    backend = spawner([sys.executable, "-m", "uvicorn", "app:app", "--reload"])
    try:
        return runner([_npm(), "--prefix", "web", "run", "dev"])
    finally:
        backend.terminate()


def cmd_build(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    return runner([_npm(), "--prefix", "web", "run", "build"])


def cmd_serve(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    if _needs_server_extra():
        return 1
    return runner(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(args.port)]
    )


def cmd_dockerfile(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    Path("Dockerfile").write_text(render_dockerfile(web=Path("web/package.json").exists()))
    return 0


# Container targets build from a Dockerfile; serverless targets don't.
_CONTAINER_TARGETS = {"fly", "render", "hf"}

_DEPLOY_NEXT_STEPS = {
    "fly": "Next: `fly launch --copy-config --no-deploy`, `fly secrets set "
           "ANTHROPIC_API_KEY=… DATABASE_URL=…`, then `fly deploy`.",
    "render": "Next: push to GitHub, then in Render pick New + > Blueprint. Set "
              "ANTHROPIC_API_KEY and DATABASE_URL as secrets in the dashboard.",
    "hf": "Next: create a Docker Space and push this repo; set ANTHROPIC_API_KEY, "
          "DATABASE_URL, RELIO_EMBEDDER under the Space's Variables & secrets.",
    "vercel": "Next: `vercel` to deploy. Set DATABASE_URL (Neon *pooled* URL), "
              "ANTHROPIC_API_KEY, and RELIO_EMBEDDER=openai|gemini as env vars. "
              "Serverless buffers SSE — clients should POST /api/chat/complete.",
    "lambda": "Next: add `mangum` to requirements.txt, then `serverless deploy`. "
              "Use a pooled DATABASE_URL and RELIO_EMBEDDER=openai|gemini. "
              "Clients should POST /api/chat/complete (SSE degrades on Lambda).",
    "netlify": "Next: set the backend host in netlify.toml's /api/* redirect, then "
               "`netlify deploy`. Netlify serves the frontend; the Python backend "
               "runs on Vercel/Lambda/a container.",
}


def cmd_deploy(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    from .deploytargets import files_for

    name = getattr(args, "name", "relio-app")
    target = getattr(args, "target", "docker")
    if target == "docker":
        if shutil.which("docker") is None:
            print(
                "Docker not found. Install Docker, or write a free-host config "
                "instead: relio deploy --target render|fly|hf|vercel|lambda",
                file=sys.stderr,
            )
            return 1
        return runner(["docker", "build", "-t", name, "."])

    # Container targets need a Dockerfile for the platform to build; serverless
    # ones don't. Write the platform config, creating parent dirs (e.g. api/).
    # Never clobber an existing file (e.g. a project's README) — print it instead.
    if target in _CONTAINER_TARGETS and not Path("Dockerfile").exists():
        # Match the project shape so a web app's frontend actually gets built.
        Path("Dockerfile").write_text(
            render_dockerfile(web=Path("web/package.json").exists())
        )
        print("wrote Dockerfile")
    for fname, content in files_for(target, name).items():
        path = Path(fname)
        if path.exists():
            print(f"{fname} already exists — add this yourself:\n\n{content}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"wrote {fname}")
    print(_DEPLOY_NEXT_STEPS.get(target, ""))
    return 0


def cmd_sdk(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    from relio.sdkgen import app_schema, generate_all

    app_spec = getattr(args, "app", "app:app")
    try:
        schema = app_schema(app_spec)
    except Exception as exc:  # import error, missing attr, bad app — don't ship a partial SDK
        print(
            f"relio sdk: couldn't load your app '{app_spec}': {exc}\n"
            f"Run this from your project root, or pass --app module:attr.",
            file=sys.stderr,
        )
        return 1
    files = generate_all(schema)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content)
    return 0


def cmd_develop(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    # Drive the Claude Code CLI to build the app, feeding the governance gate's
    # current violations back in so the agent closes test/doc gaps as it works.
    from .check import check_project

    prompt = args.prompt or ""
    violations = check_project(".")
    if violations:
        gaps = "; ".join(f"{v.path} missing {v.missing}" for v in violations)
        prompt = (
            prompt
            + "\n\nGovernance gate (`relio check`): every module needs a test and a "
            f"doc. Current gaps to fix: {gaps}"
        ).strip()
    cmd = ["claude"]
    if prompt:
        cmd += ["-p", prompt]
    try:
        return runner(cmd)
    except FileNotFoundError:
        print("Claude Code CLI ('claude') not found. Install it to use `relio develop`.")
        return 1


def cmd_test(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    # `sys.executable -m pytest` always resolves; a bare "pytest" isn't reliably
    # on PATH (esp. in venvs / on Windows → WinError 2).
    pytest_cmd = [sys.executable, "-m", "pytest"]
    if getattr(args, "coverage", False):
        pytest_cmd += ["--cov=.", f"--cov-fail-under={args.min}"]
    rc = runner(pytest_cmd)
    if Path("web/package.json").exists():
        rc = runner([_npm(), "--prefix", "web", "test"]) or rc
    return rc


def cmd_check(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    from .check import check_project

    violations = check_project(args.path)
    for v in violations:
        print(f"{v.path}: missing {v.missing}")
    if violations:
        print(f"{len(violations)} violation(s): every module needs a test and a doc.")
        return 1
    print("OK: every module has a test and a doc.")
    return 0


def cmd_migrate(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    from ..migrate import migrate_records, open_backend

    embed = not args.no_embed
    if embed:
        from ..embedding.local import LocalEmbedder

        embedder = LocalEmbedder()
    else:
        # No vectors requested — a zero-cost stand-in just supplies the dim.
        from ..embedding.base import DeterministicEmbedder

        embedder = DeterministicEmbedder()
    src = open_backend(args.src, dim=embedder.dim)
    dst = open_backend(args.dst, dim=embedder.dim)
    try:
        n = migrate_records(src, dst, embedder, embed=embed)
    finally:
        src.close()
        dst.close()
    how = "re-embedded" if embed else "without vectors"
    print(f"migrated {n} records from {args.src} to {args.dst} ({how})")
    return 0


def _open_browser(url: str) -> None:
    # Best-effort: never let a missing/blocked browser stop the server.
    import webbrowser

    try:
        webbrowser.open(url)
    except Exception:
        pass


def cmd_gui(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    # Serve Relio Studio via uvicorn (shelling out mirrors `relio serve`, so it's
    # testable through the injected runner). Open the browser first — it'll connect
    # once the server is up a moment later.
    if _needs_server_extra():
        return 1
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 4000)
    if not getattr(args, "no_open", False):
        _open_browser(f"http://{host}:{port}")
    return runner(
        [sys.executable, "-m", "uvicorn", "relio.studio.launch:app",
         "--host", host, "--port", str(port)]
    )


def cmd_ai(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    if args.ai_command == "new":
        from .scaffold import write_ai_scaffold

        write_ai_scaffold(args.name, args.name)
        return 0
    return 1


_HANDLERS: dict[str, Callable[[argparse.Namespace, Runner, Spawn], int]] = {
    "new": cmd_new,
    "gui": cmd_gui,
    "ai": cmd_ai,
    "dev": cmd_dev,
    "build": cmd_build,
    "serve": cmd_serve,
    "dockerfile": cmd_dockerfile,
    "deploy": cmd_deploy,
    "sdk": cmd_sdk,
    "develop": cmd_develop,
    "test": cmd_test,
    "check": cmd_check,
    "migrate": cmd_migrate,
}


def main(
    argv: Optional[list[str]] = None,
    runner: Runner = run,
    spawner: Spawn = spawn,
) -> int:
    args = build_parser().parse_args(argv)
    return _HANDLERS[args.command](args, runner, spawner)


if __name__ == "__main__":
    raise SystemExit(main())
