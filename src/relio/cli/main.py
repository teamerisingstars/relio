# src/relio/cli/main.py
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Callable, Optional

from .dockerfile import render_dockerfile
from .scaffold import write_scaffold

Runner = Callable[..., int]
Spawn = Callable[..., "subprocess.Popen[bytes]"]


def run(cmd: list[str], cwd: Optional[str] = None) -> int:
    return subprocess.call(cmd, cwd=cwd)


def spawn(cmd: list[str], cwd: Optional[str] = None) -> "subprocess.Popen[bytes]":
    return subprocess.Popen(cmd, cwd=cwd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relio", description="Relio framework CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="scaffold a new memory-native app")
    new.add_argument("name")

    sub.add_parser("dev", help="run backend + frontend dev servers")
    sub.add_parser("build", help="build the React frontend")

    serve = sub.add_parser("serve", help="serve API + built frontend on one port")
    serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("dockerfile", help="write the production Dockerfile")
    sub.add_parser("deploy", help="build the Docker image")
    return parser


def cmd_new(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    write_scaffold(args.name, args.name)
    return 0


def cmd_dev(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    # Start the backend (auto-reload) in the background, then run the Vite dev
    # server in the foreground (it proxies /api to the backend). Stop the backend
    # when the dev server exits.
    backend = spawner(["uvicorn", "app:app", "--reload"])
    try:
        return runner(["npm", "--prefix", "frontend", "run", "dev"])
    finally:
        backend.terminate()


def cmd_build(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    return runner(["npm", "--prefix", "frontend", "run", "build"])


def cmd_serve(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    return runner(["uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(args.port)])


def cmd_dockerfile(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    Path("Dockerfile").write_text(render_dockerfile())
    return 0


def cmd_deploy(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    return runner(["docker", "build", "-t", "relio-app", "."])


_HANDLERS: dict[str, Callable[[argparse.Namespace, Runner, Spawn], int]] = {
    "new": cmd_new,
    "dev": cmd_dev,
    "build": cmd_build,
    "serve": cmd_serve,
    "dockerfile": cmd_dockerfile,
    "deploy": cmd_deploy,
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
