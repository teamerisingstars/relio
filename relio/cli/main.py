# relio/cli/main.py
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
    sub.add_parser("deploy", help="build the Docker image")

    sdk = sub.add_parser("sdk", help="generate TS + Python client SDKs from the API")
    sdk.add_argument("--out", default="sdk", help="output directory (default: sdk)")

    develop = sub.add_parser("develop", help="drive Claude Code to build the app")
    develop.add_argument("prompt", nargs="?", help="what to build (optional)")

    test = sub.add_parser("test", help="run the project's test suites")
    test.add_argument("--coverage", action="store_true", help="enforce a coverage threshold")
    test.add_argument("--min", type=int, default=80, help="minimum coverage %% (with --coverage)")

    check = sub.add_parser("check", help="fail if any module lacks a test or a doc")
    check.add_argument("--path", default=".", help="project root to check (default: .)")

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
    # Start the backend (auto-reload) in the background, then run the Vite dev
    # server in the foreground (it proxies /api to the backend). Stop the backend
    # when the dev server exits.
    backend = spawner(["uvicorn", "app:app", "--reload"])
    try:
        return runner(["npm", "--prefix", "web", "run", "dev"])
    finally:
        backend.terminate()


def cmd_build(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    return runner(["npm", "--prefix", "web", "run", "build"])


def cmd_serve(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    return runner(["uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(args.port)])


def cmd_dockerfile(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    Path("Dockerfile").write_text(render_dockerfile())
    return 0


def cmd_deploy(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    return runner(["docker", "build", "-t", "relio-app", "."])


def cmd_sdk(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    from relio.sdkgen import app_schema, generate_all

    files = generate_all(app_schema())
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
    pytest_cmd = ["pytest"]
    if getattr(args, "coverage", False):
        pytest_cmd += ["--cov=.", f"--cov-fail-under={args.min}"]
    rc = runner(pytest_cmd)
    if Path("web/package.json").exists():
        rc = runner(["npm", "--prefix", "web", "test"]) or rc
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


def cmd_ai(args: argparse.Namespace, runner: Runner, spawner: Spawn) -> int:
    if args.ai_command == "new":
        from .scaffold import write_ai_scaffold

        write_ai_scaffold(args.name, args.name)
        return 0
    return 1


_HANDLERS: dict[str, Callable[[argparse.Namespace, Runner, Spawn], int]] = {
    "new": cmd_new,
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
